import json, re, sys, os, time
from agent.llm import call
from agent.fetch import fetch
from agent.schema import *

FIELDS = ["auth_methods", "access_test", "access_ship",
          "api_type", "api_breadth", "official_mcp"]


def _json(text):
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", t, flags=re.S)  # first JSON block inside chatter
        if not m:
            raise
        return json.loads(m.group(1))


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def squash(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def quote_on_page(quote, page_text):
    """Quote may contain '...' joins; every fragment of 15+ chars must be on the page."""
    frags = [f for f in re.split(r"\.\.\.|…", quote or "") if len(squash(f)) >= 15]
    if not frags:
        return False
    page = squash(page_text or "")
    return all(squash(f) in page for f in frags)


def enum_or_unknown(E, v):
    try:
        return E(v)
    except (ValueError, TypeError):
        return E.unknown


def _call_json(prompt, tries=3):
    """Call the LLM, parse JSON, retry with backoff. Logs the real error each time."""
    last = None
    for i in range(tries):
        try:
            txt, model = call(prompt)
            return _json(txt), model
        except Exception as e:
            last = e
            print(f"   try {i + 1}/{tries} failed: {type(e).__name__}: {str(e)[:200]}")
            if i < tries - 1:
                time.sleep(5 * (2 ** i))  # 5s, 10s
    raise last


def discover(name, hint="", seeds=()):
    urls = list(seeds)
    if len(urls) < 3:
        p = (f'List up to 6 official developer documentation URLs for the app "{name}" {hint}. '
             "Cover: authentication (OAuth / API keys), getting started or pricing/access, "
             "API reference, and an MCP server if one exists. Only URLs on the app's own "
             "domain or its GitHub org. Return ONLY a JSON list of strings. "
             "If unsure, return fewer. Never invent URLs.")
        try:
            more, _ = _call_json(p)
            if isinstance(more, list):
                urls += [u for u in more if isinstance(u, str)]
        except Exception as e:
            print("   discover failed:", f"{type(e).__name__}: {str(e)[:200]}")
    seen, pages = set(), []
    for u in urls[:8]:
        if u in seen:
            continue
        seen.add(u)
        try:
            r = fetch(u)
        except Exception as e:
            print("   fetch failed:", u, type(e).__name__)
            continue
        if r.get("status") == 200 and r.get("text"):
            pages.append(r)
    return pages


def extract(name, pages):
    ctx = "\n\n".join(f"[SOURCE {i}] {p['url']}\n{p['text'][:12000]}"
                      for i, p in enumerate(pages))
    p = f'''You research the app "{name}" for an API-integration team.
Use ONLY the sources below. For each field give value, the source url, and a
VERBATIM quote (copied exactly, 15+ chars) from that source that supports it.
If the sources do not show it, value must be "unknown" with empty quote. Never guess.

Allowed values:
auth_methods: list of oauth2, api_key, basic, bearer_token, jwt, none, other, unknown
access_test (can a dev get credentials to test?) and access_ship (can you ship publicly?):
  free_self_serve, free_trial, paid_plan, admin_approval, partner_gated, no_api, unknown
api_type: rest, graphql, both, sdk_only, cli_only, none, unknown
api_breadth: narrow, medium, broad, unknown
official_mcp: yes, no, community, unknown

Return ONLY JSON with this shape:
{{"one_liner": "...",
  "auth_methods": {{"value": [...], "url": "", "quote": ""}},
  "access_test": {{"value": "", "url": "", "quote": ""}},
  "access_ship": {{"value": "", "url": "", "quote": ""}},
  "api_type": {{"value": "", "url": "", "quote": ""}},
  "api_breadth": {{"value": "", "url": "", "quote": ""}},
  "official_mcp": {{"value": "", "url": "", "quote": ""}},
  "verdict": "buildable_now | buildable_with_caveat | blocked | unknown",
  "blocker": "short phrase or null"}}

SOURCES:
{ctx}'''
    return _call_json(p)


def _research_app(app_id, name, hint="", seeds=()):
    pages = discover(name, hint, seeds)
    flags = []
    if not pages:
        rec = AppRecord(id=app_id, one_liner="", auth_methods=[Auth.unknown],
                        access_test=Access.unknown, access_ship=Access.unknown,
                        api_type=ApiType.unknown, api_breadth="unknown",
                        official_mcp="unknown", verdict=Verdict.unknown,
                        blocker="no_sources_found")
        return {"record": rec.model_dump(mode="json"), "flags": ["no_sources"],
                "sources": [], "model": None}

    data, model = extract(name, pages)
    if not isinstance(data, dict):
        raise ValueError("extract returned non-object JSON")
    text_by_url = {p["url"]: p["text"] for p in pages}
    evidence = {}
    for f in FIELDS:
        e = data.get(f)
        if not isinstance(e, dict):
            e = {}
        u = e.get("url", "") or ""
        quote_ok = quote_on_page(e.get("quote", ""), text_by_url.get(u, ""))
        absence = f == "official_mcp" and e.get("value") == "no"
        if not quote_ok and not absence:
            if e.get("value") not in (None, "", "unknown", ["unknown"]):
                flags.append(f"{f}:quote_not_found:{e.get('value')}")
            e["value"] = ["unknown"] if f == "auth_methods" else "unknown"
        if absence and not quote_ok:
            flags.append("official_mcp:absence_claim")
        data[f] = e
        evidence[f] = Evidence(url=u, quote=e.get("quote", "") or "",
                               confidence=1.0 if quote_ok else 0.0)

    auth_vals = data["auth_methods"].get("value") or ["unknown"]
    if isinstance(auth_vals, str):
        auth_vals = [auth_vals]
    rec = AppRecord(
        id=app_id, one_liner=data.get("one_liner", "") or "",
        auth_methods=[enum_or_unknown(Auth, v) for v in auth_vals],
        access_test=enum_or_unknown(Access, data["access_test"].get("value")),
        access_ship=enum_or_unknown(Access, data["access_ship"].get("value")),
        api_type=enum_or_unknown(ApiType, data["api_type"].get("value")),
        api_breadth=data["api_breadth"].get("value") or "unknown",
        official_mcp=data["official_mcp"].get("value") or "unknown",
        verdict=enum_or_unknown(Verdict, data.get("verdict", "unknown")),
        blocker=data.get("blocker"), evidence=evidence)
    return {"record": rec.model_dump(mode="json"), "flags": flags,
            "sources": [p["url"] for p in pages], "model": model}


def research_app(app_id, name, hint="", seeds=()):
    """Never raises. On failure, record is None and flags holds the real error."""
    try:
        return _research_app(app_id, name, hint, seeds)
    except Exception as e:
        return {"record": None,
                "flags": [f"error:{type(e).__name__}:{str(e)[:250]}"],
                "sources": [], "model": None}


if __name__ == "__main__":
    app_id, name = sys.argv[1], sys.argv[2]
    out = research_app(app_id, name)
    os.makedirs("data/single", exist_ok=True)
    json.dump(out, open(f"data/single/{app_id}.json", "w", encoding="utf-8"), indent=2)
    print(json.dumps(out, indent=2))