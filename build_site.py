"""Build site/index.html + site/data.json + site/llms.txt from data/final_v3 and verification reports.
Run: python build_site.py"""
import csv, json, os
from collections import Counter, defaultdict

REPO = "https://github.com/DarshanRamesh23/app-research-agent"   # change if your repo name differs
SRC = "data/final_v3"
SELF, GATED = {"free_self_serve", "free_trial"}, {"paid_plan", "admin_approval", "partner_gated"}
os.makedirs("site", exist_ok=True)

rows = []
for a in csv.DictReader(open("data/apps.csv", encoding="utf-8-sig")):
    p, rec = f"{SRC}/{a['id']}.json", None
    if os.path.exists(p):
        rec = json.load(open(p, encoding="utf-8")).get("record")
    r = rec or {}
    ev = r.get("evidence") or {}
    rows.append(dict(id=a["id"], name=a.get("name") or a["id"], category=a.get("category") or "unknown",
                     one=r.get("one_liner", ""), auth=r.get("auth_methods") or [], test=r.get("access_test", "unknown"),
                     ship=r.get("access_ship", "unknown"), api=r.get("api_type", "unknown"),
                     breadth=r.get("api_breadth", "unknown"), mcp=r.get("official_mcp", "unknown"),
                     verdict=(r.get("verdict") or "unknown") if rec else "no_data", blocker=r.get("blocker") or "",
                     ev={k: v["url"] for k, v in ev.items() if isinstance(v, dict) and v.get("url")}))

ok = [x for x in rows if x["verdict"] != "no_data"]
N, V = len(rows), Counter(x["verdict"] for x in rows)
auth = Counter(m for x in ok for m in (x["auth"] or ["unknown"]))
blk = Counter(x["blocker"] for x in ok if x["blocker"])
mcp = Counter(x["mcp"] for x in ok)
gap = [x["name"] for x in ok if x["test"] in SELF and x["ship"] in GATED]
quad = defaultdict(list)
for x in ok:
    if x["test"] in SELF | GATED and x["breadth"] in ("narrow", "medium", "broad"):
        quad[("self" if x["test"] in SELF else "gated") + ("_narrow" if x["breadth"] == "narrow" else "_wide")].append(x["name"])
top = lambda c, n=3: ", ".join(f"{k} ({v})" for k, v in c.most_common(n)) or "none recorded"
heads = [f"{V['buildable_now']} of {N} apps are buildable today; {V['buildable_with_caveat']} more with a caveat; {V['blocked']} blocked; "
         f"{V['unknown']} unknown; {V['no_data']} not resolved by the agent.",
         f"Most common auth: {top(auth)}.",
         f"Most common blockers: {top(blk)}.",
         f"{len(gap)} apps are free to test but gated to ship publicly (two-layer gate): {', '.join(gap[:6]) or 'none'}.",
         f"Official MCP found for {mcp['yes']} apps (community {mcp['community']}). 'No' means 'not found', not proven absent."]

cats = sorted({x["category"] for x in ok})
AUTHS = ["oauth2", "api_key", "basic", "bearer_token", "jwt", "other", "none", "unknown"]
hm = {c: Counter(m for x in ok if x["category"] == c for m in (x["auth"] or ["unknown"])) for c in cats}
mx = max([v for c in hm.values() for v in c.values()] + [1])
heat = "<table class=hm><tr><th></th>" + "".join(f"<th>{m}</th>" for m in AUTHS) + "</tr>" + "".join(
    f"<tr><td>{c}</td>" + "".join(f"<td style='background:rgba(37,99,235,{hm[c][m]/mx:.2f})'>{hm[c][m] or ''}</td>" for m in AUTHS) + "</tr>"
    for c in cats) + "</table>"
bar = lambda c, col="#2563eb": "".join(
    f"<div class=b><span>{k}</span><i style='width:{100*v/max(max(c.values()),1):.0f}%;background:{col}'></i><b>{v}</b></div>" for k, v in c.most_common())
qd = lambda k, t: f"<div class=q><h4>{t} ({len(quad[k])})</h4><small>{', '.join(quad[k][:14])}</small></div>"
quad_html = ("<div class=qg>" + qd("self_wide", "Easy wins: self-serve, wide API") + qd("gated_wide", "Outreach: gated, wide API")
             + qd("self_narrow", "Self-serve, narrow API") + qd("gated_narrow", "Gated, narrow API") + "</div>")

acc = {}
for tag in ("before", "after"):
    f = f"verification/report_{tag}.json"
    if os.path.exists(f):
        rep = json.load(open(f, encoding="utf-8"))
        acc[tag] = {s: [sum(t["correct"] for t in rep[s].values()), sum(t["correct"] + t["wrong"] + t["abstain"] for t in rep[s].values()),
                        sum(t["wrong"] for t in rep[s].values())] for s in rep}
acc_html = ""
for tag, lab in (("before", "Gold before corrections (first filled draft)"), ("after", "Gold after human corrections against vendor docs")):
    if tag in acc:
        acc_html += f"<h4>{lab}</h4>" + "".join(
            f"<div class=b><span>{s}</span><i style='width:{100*c/n:.0f}%;background:#16a34a'></i><b>{c}/{n} = {100*c/n:.0f}% (wrong {w})</b></div>"
            for s, (c, n, w) in acc[tag].items())
miss = ""
if os.path.exists("verification/misses_after.csv"):
    ms = [m for m in csv.DictReader(open("verification/misses_after.csv", encoding="utf-8")) if m["final_v3_result"] != "correct"][:20]
    miss = "<table><tr><th>app</th><th>field</th><th>truth</th><th>final said</th><th>result</th><th>L2</th></tr>" + "".join(
        f"<tr><td>{m['app']}</td><td>{m['field']}</td><td>{m['truth']}</td><td>{m['final_v3_said']}</td><td>{m['final_v3_result']}</td><td>{m['l2_verdict']}</td></tr>"
        for m in ms) + "</table>"

data = dict(source=SRC, total=N, headlines=heads, accuracy=acc, apps=rows)
json.dump(data, open("site/data.json", "w", encoding="utf-8"), indent=1)
open("site/llms.txt", "w", encoding="utf-8").write(
    f"# App research table ({N} apps)\nMachine-readable data: data.json (fields: auth, test, ship, api, breadth, mcp, verdict, blocker, ev = evidence URLs).\n"
    f"Verdict values: buildable_now, buildable_with_caveat, blocked, unknown, no_data (agent returned nothing).\nRepo: {REPO}\n\n" + "\n".join(heads) + "\n")

page = """<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>100-app API research agent</title><style>
body{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:16px;color:#111}h1{margin:.2em 0}h2{margin-top:1.6em;border-bottom:1px solid #ddd}
li{margin:.3em 0}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #ddd;padding:4px 6px;text-align:left;vertical-align:top}
.hm td{text-align:center}.wrap{overflow-x:auto}.b{display:flex;align-items:center;gap:8px;margin:3px 0}.b span{width:170px;font-size:13px}.b i{height:14px;display:block;min-width:2px}
.qg{display:grid;grid-template-columns:1fr 1fr;gap:8px}.q{border:1px solid #ddd;padding:8px;border-radius:6px}.q h4{margin:0 0 4px}
.v{padding:1px 6px;border-radius:9px;color:#fff;font-size:12px;white-space:nowrap}.buildable_now{background:#16a34a}.buildable_with_caveat{background:#ca8a04}
.blocked{background:#dc2626}.unknown,.no_data{background:#6b7280}input,select{padding:5px;margin:0 6px 8px 0}code{background:#f3f4f6;padding:1px 4px}
@media(prefers-color-scheme:dark){body{background:#111;color:#eee}td,th,.q{border-color:#444}code{background:#222}}</style>
<h1>100-app API research agent</h1><p>An AI agent researched 100 apps (auth, access, API surface, MCP, buildability) with evidence URLs. Accuracy was checked against a human-checked gold set.</p>
<h2>Headline patterns</h2><ul>__HEADS__</ul>
<h2>Patterns</h2><h4>Auth method by category (count of apps)</h4><div class=wrap>__HEAT__</div>
<h4>Easy wins vs outreach (access to test x API breadth)</h4>__QUAD__
<h4>Verdicts</h4>__VBAR__<h4>Blockers</h4>__BBAR__
<h2>Table (all apps, with evidence)</h2><input id=q placeholder="search app or category"><select id=f><option value="">all verdicts</option>
<option>buildable_now</option><option>buildable_with_caveat</option><option>blocked</option><option>unknown</option><option>no_data</option></select>
<div class=wrap><table id=t><thead><tr><th>App</th><th>Category / what it does</th><th>Auth</th><th>Test / ship access</th><th>API</th><th>MCP</th><th>Verdict</th><th>Evidence</th></tr></thead><tbody></tbody></table></div>
<h2>How the agent works</h2><p>apps.csv &rarr; <b>discover</b> (official docs, pricing, partner pages) &rarr; <b>fetch + cache</b> 3-5 pages &rarr; <b>extract</b> to a fixed enum schema with a verbatim quote per claim (no quote = unknown) &rarr; <b>L1</b> code checks (enums, quote must appear on the page) &rarr; <b>L2</b> independent verifier call (supported / unverifiable / contradicted, then re-research) &rarr; rules (CLI-only apps have no API access) &rarr; this page. Pass 1 is frozen so improvement can be measured.</p>
<p><b>Where a human was needed:</b> seed URLs for apps the agent could not find docs for; the gold set (12 apps, filled from vendor docs and corrected, every change logged); resolving thin or gated apps. __NOD__ apps got no record from the agent and are shown as no_data, not guessed. L2 ran on a mixed Gemini model chain because of daily quota limits.</p>
<h2>Verification: what was right and wrong</h2>__ACC__<p>Honest read: a small but consistent gain (about 5 points strict, fewer wrong answers because the agent abstains more). The gold set is small (12 apps, 59 graded cells), and the gold was corrected after seeing agent output, so both scores are shown. Weakest fields: auth_methods and official_mcp (an absence claim cannot be proven from one page).</p>
<div class=wrap>__MISS__</div>
<h2>Proof and how to run</h2><p>Repo: <a href="__REPO__">__REPO__</a> &middot; data: <a href="data.json">data.json</a> &middot; <a href="llms.txt">llms.txt</a></p>
<p><code>pip install -r requirements.txt</code>, add <code>GEMINI_API_KEY</code> to <code>.env</code>, then <code>python -m agent run --app Attio</code> (one app) or <code>python -m agent.run_all data/apps.csv</code> (all).</p>
<script id=d type=application/json>__JSON__</script><script>
const D=JSON.parse(document.getElementById('d').textContent).apps,tb=document.querySelector('tbody');
function draw(){const q=document.getElementById('q').value.toLowerCase(),f=document.getElementById('f').value;
tb.innerHTML=D.filter(x=>(!f||x.verdict==f)&&(x.name+x.category).toLowerCase().includes(q)).map(x=>`<tr><td><b>${x.name}</b></td><td>${x.category}<br><small>${x.one}</small></td><td>${x.auth.join(', ')}</td><td>${x.test} / ${x.ship}</td><td>${x.api}, ${x.breadth}</td><td>${x.mcp}</td><td><span class="v ${x.verdict}">${x.verdict}</span><br><small>${x.blocker}</small></td><td>${Object.entries(x.ev).map(([k,u])=>`<a href="${u}">${k}</a>`).join(' ')}</td></tr>`).join('')}
document.getElementById('q').oninput=draw;document.getElementById('f').onchange=draw;draw();</script></html>"""
vb = Counter({k: V[k] for k in ("buildable_now", "buildable_with_caveat", "blocked", "unknown", "no_data") if V[k]})
for k, v in {"__HEADS__": "".join(f"<li>{h}</li>" for h in heads), "__HEAT__": heat, "__QUAD__": quad_html, "__VBAR__": bar(vb, "#16a34a"),
             "__BBAR__": bar(blk, "#dc2626") if blk else "<small>none recorded</small>", "__ACC__": acc_html, "__MISS__": miss,
             "__NOD__": str(V["no_data"]), "__REPO__": REPO, "__JSON__": json.dumps(data).replace("</", "<\\/")}.items():
    page = page.replace(k, v)
open("site/index.html", "w", encoding="utf-8").write(page)
print(f"wrote site/index.html, data.json, llms.txt  ({N} apps, {V['no_data']} no_data)")