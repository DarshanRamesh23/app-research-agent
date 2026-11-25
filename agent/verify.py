import csv, glob, json, os
from concurrent.futures import ThreadPoolExecutor
from agent.llm import call
from agent.fetch import fetch
from agent.research import _json, quote_on_page, enum_or_unknown, FIELDS
from agent.schema import Auth, Access, ApiType

SRC, OUT = "data/pass1_frozen", "data/final"
VERIFIER = "gemini-3.5-flash"
UNK = ("unknown", ["unknown"], None, "")
NAMES = {r["id"]: r["name"] for r in csv.DictReader(open("data/apps.csv", encoding="utf-8"))}
ALLOWED = """auth_methods: list of oauth2, api_key, basic, bearer_token, jwt, none, other, unknown
access_test, access_ship: free_self_serve, free_trial, paid_plan, admin_approval, partner_gated, no_api, unknown
api_type: rest, graphql, both, sdk_only, cli_only, none, unknown
api_breadth: narrow, medium, broad, unknown
official_mcp: yes, no, community, unknown"""

def ask(prompt):
    try:
        return call(prompt, model=VERIFIER)
    except RuntimeError:
        return call(prompt)

def clean(f, v):
    if f == "auth_methods":
        v = v if isinstance(v, list) else [v]
        return [enum_or_unknown(Auth, x).value for x in v] or ["unknown"]
    if f in ("access_test", "access_ship"):
        return enum_or_unknown(Access, v).value
    if f == "api_type":
        return enum_or_unknown(ApiType, v).value
    if f == "api_breadth":
        return v if v in ("narrow", "medium", "broad") else "unknown"
    if f == "official_mcp":
        return v if v in ("yes", "no", "community") else "unknown"
    return v

def l2(name, rec):
    claims, urls = {}, []
    for f in FIELDS:
        if rec[f] in UNK:
            continue
        ev = rec["evidence"].get(f, {})
        claims[f] = {"value": rec[f], "quote": ev.get("quote", "")}
        if ev.get("url") and ev["url"] not in urls:
            urls.append(ev["url"])
    if not claims:
        return {}, None
    pages = "\n\n".join(f"[PAGE {u}]\n{fetch(u)['text'][:6000]}" for u in urls)
    prompt = f'''You are a strict fact-checker for the app "{name}". Judge each claim using ONLY the pages below.
supported = pages directly show the value. contradicted = pages show a different value.
unverifiable = pages do not settle it.
Rules: access_test = can a developer get credentials to test. access_ship = can an integration
be published or used by real customers (app review, partner program, paid plan). A free sandbox
or pricing for other features does not prove access_ship. official_mcp "yes" needs an MCP server
published by the vendor itself; third-party means "community".
Return ONLY JSON: {{"<field>": {{"verdict": "supported|contradicted|unverifiable", "reason": "one sentence"}}}}

CLAIMS:
{json.dumps(claims, indent=1)}

{pages}'''
    txt, model = ask(prompt)
    return _json(txt), model

def reresearch(name, bad, source_urls):
    pages = [fetch(u) for u in source_urls]
    pages = [p for p in pages if p["status"] == 200 and p["text"]]
    ctx = "\n\n".join(f"[SOURCE {p['url']}]\n{p['text'][:10000]}" for p in pages)
    prompt = f'''App "{name}". A reviewer rejected these answers: {json.dumps(bad)}
Re-answer ONLY those fields using ONLY the sources below. Give value, source url and a VERBATIM
quote (15+ chars) copied from that source. If the sources do not show it, value is "unknown", quote "".
Allowed values:
{ALLOWED}
Return ONLY JSON: {{"<field>": {{"value": ..., "url": "", "quote": ""}}}}

{ctx}'''
    txt, _ = call(prompt)
    return _json(txt), {p["url"]: p["text"] for p in pages}

def derive(r):
    t, s, a = r["access_test"], r["access_ship"], r["api_type"]
    if a in ("cli_only", "none") or t == "no_api":
        return "blocked", "no_public_api"
    if t == "partner_gated":
        return "blocked", "partner_program"
    if t == "unknown" or a == "unknown":
        return "unknown", None
    if t == "paid_plan" or s == "paid_plan":
        return "buildable_with_caveat", "paid_plan"
    if t == "admin_approval" or s == "admin_approval":
        return "buildable_with_caveat", "app_review"
    if s == "partner_gated":
        return "buildable_with_caveat", "partner_program"
    if t == "free_trial":
        return "buildable_with_caveat", "trial_only"
    if a == "sdk_only":
        return "buildable_with_caveat", "sdk_only"
    if s == "unknown":
        return "buildable_with_caveat", "ship_path_unverified"
    return "buildable_now", None

def process(path):
    aid = os.path.basename(path)[:-5]
    out = f"{OUT}/{aid}.json"
    if os.path.exists(out):
        return aid
    d = json.load(open(path, encoding="utf-8"))
    rec = d["record"]
    if not rec:
        json.dump(d, open(out, "w", encoding="utf-8"), indent=2)
        return aid
    name, changes, model = NAMES.get(aid, aid), [], None
    rec["verdict_pass1"] = rec["verdict"]
    try:
        l2v, model = l2(name, rec)
    except Exception as e:
        l2v = {}
        changes.append({"field": "*", "action": "l2_error", "reason": str(e)[:80]})
    bad = {f: v for f, v in l2v.items()
           if f in FIELDS and v.get("verdict") in ("contradicted", "unverifiable")}
    if bad:
        try:
            data, texts = reresearch(
                name, {f: {"old": rec[f], "reason": v.get("reason", "")} for f, v in bad.items()},
                d["sources"])
        except Exception:
            data, texts = {}, {}
        for f, v in bad.items():
            old, e = rec[f], (data.get(f) or {})
            u = e.get("url", "")
            ok = quote_on_page(e.get("quote", ""), texts.get(u, ""))
            new = clean(f, e.get("value")) if ok else (["unknown"] if f == "auth_methods" else "unknown")
            if not ok:
                action = "to_unknown"
            elif new == old:
                action = "confirmed_after_recheck"
            else:
                action = "corrected"
            rec[f] = new
            rec["evidence"][f] = {"url": u, "quote": e.get("quote", ""), "confidence": 1.0 if ok else 0.0}
            changes.append({"field": f, "before": old, "after": new, "l2": v["verdict"],
                            "reason": v.get("reason", ""), "action": action})
    rec["verdict"], rec["blocker"] = derive(rec)
    json.dump({"record": rec, "l2": l2v, "l2_model": model, "changes": changes,
               "flags": d["flags"], "sources": d["sources"]},
              open(out, "w", encoding="utf-8"), indent=2)
    return aid

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    paths = sorted(glob.glob(f"{SRC}/*.json"))
    with ThreadPoolExecutor(3) as ex:
        for i, aid in enumerate(ex.map(process, paths), 1):
            print(f"[{i}/{len(paths)}] {aid}")