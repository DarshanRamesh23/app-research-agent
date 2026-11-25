"""
Write seed_urls into data/apps.csv.

  python add_seeds.py --check   -> fetch every seed URL and report size / JS-shell warning. Writes nothing.
  python add_seeds.py           -> write seeds to data/apps.csv (backup saved to data/apps.csv.bak)

Fill SEEDS with REAL URLs only. Prefer API reference pages, OpenAPI/Swagger JSON, or raw GitHub markdown.
"""
import csv, os, re, shutil, sys, urllib.request

CSV_PATH = "data/apps.csv"

SEEDS = {
    # "app_id": ["https://...", "https://..."],
    "binance": ["https://developers.binance.com/docs/binance-spot-api-docs/rest-api/spot-account-trade",
                "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/user-data-stream-endpoints"],
    "gumroad": ["https://gumroad.com/api",
                "https://gumroad.com/help/article/280-create-application-api"],
    "pumble": ["https://pumble.com/help/integrations/api-keys-integration"],
    "lark_larksuite": ["https://open.larksuite.com/document/ukTMukTMukTM/ukDNz4SO0MjL5QzM/auth-v3/auth/tenant_access_token_internal.md"],
    "notebooklm": [],
    "attio": ["https://docs.attio.com/rest-api/guides/authentication",
              "https://docs.attio.com/rest-api/guides/authentication.md"],
    "ecwid": ["https://api-docs.ecwid.com/reference/access-tokens",
              "https://docs.ecwid.com/get-started/make-your-first-api-request"],
    "liveagent": [],
    "mongodb_atlas": ["https://www.mongodb.com/docs/atlas/api/api-authentication.md",
                      "https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/2023-01-01"],
    "neo4j": ["https://neo4j.com/docs/aura/api/authentication",
              "https://neo4j.com/docs/aura/platform/api/authentication"],
    "pinterest": [],
    "pylon": ["https://docs.usepylon.com/pylon-docs/developer/api/authentication",
              "https://docs.usepylon.com/pylon-docs/developer/api"],
}

PLACEHOLDER = re.compile(r"^\s*URL\d*\b", re.I)


def valid(u):
    return u.startswith(("http://", "https://")) and " " not in u and not PLACEHOLDER.match(u) and "URL1" not in u


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (seed-check)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read(400_000).decode("utf-8", "ignore")
        return r.status, body


def visible_text_len(html):
    html = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html)
    return len(re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html)).strip())


def check(urls_by_app):
    for app, urls in urls_by_app.items():
        for u in urls:
            try:
                status, body = fetch(u)
                n = visible_text_len(body)
                warn = ""
                if n < 1500 or re.search(r"enable javascript|you need to enable js", body, re.I):
                    warn = "  <-- likely JS shell / thin page, replace"
                print(f"{app:16} {status} {n:>7} chars  {u}{warn}")
            except Exception as e:
                print(f"{app:16} FAIL {type(e).__name__}: {str(e)[:80]}  {u}")


with open(CSV_PATH, encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))
cols = list(rows[0].keys())
ids = {r["id"] for r in rows}

bad_ids = [a for a in SEEDS if a not in ids]
if bad_ids:
    print("not in apps.csv, ignored:", bad_ids)

clean = {}
for app, urls in SEEDS.items():
    if app not in ids:
        continue
    good = [u.strip() for u in urls if valid(u.strip())]
    dropped = [u for u in urls if not valid(u.strip())]
    if dropped:
        print(f"{app}: invalid URLs dropped: {dropped}")
    if good:
        clean[app] = good

if "--check" in sys.argv:
    if not clean:
        print("no valid URLs in SEEDS yet")
    check(clean)
    sys.exit(0)

if "seed_urls" not in cols:
    cols.append("seed_urls")
shutil.copy(CSV_PATH, CSV_PATH + ".bak")

cleared = []
for r in rows:
    cur = (r.get("seed_urls") or "").strip()
    if r["id"] in clean:
        r["seed_urls"] = "|".join(clean[r["id"]])          # new seeds replace old ones for that app
    elif cur and any(PLACEHOLDER.match(p) or "URL1" in p for p in cur.split("|")):
        r["seed_urls"] = ""                                 # remove stale placeholder text
        cleared.append(r["id"])
    else:
        r["seed_urls"] = cur                                # keep whatever was there

with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)

print("seeded:", sorted(clean))
if cleared:
    print("cleared placeholder seeds:", cleared)