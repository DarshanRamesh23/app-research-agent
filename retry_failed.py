import csv, glob, json, os, shutil, sys, time
from agent.research import research_app
from agent.llm import quota_dead

SRC, OUT = "data/pass1_frozen", "data/pass1_retry"
os.makedirs(OUT, exist_ok=True)
CORE = ("access_ship", "api_type", "api_breadth", "official_mcp")
UNKNOWN = (None, "unknown", ["unknown"])
SLEEP = 8                 # seconds between apps
MAX_CONSEC_LLM_FAIL = 3   # stop after this many "all models failed" in a row

force = [a for a in sys.argv[1:] if not a.startswith("-")]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def failed(j):
    """All four core fields unknown (or no record). Used for auto-selection."""
    r = j.get("record")
    if r is None or r.get("blocker") == "no_sources_found":
        return True
    return all(r.get(f) in UNKNOWN for f in CORE)


def api_known(j):
    return (j.get("record") or {}).get("api_type") not in UNKNOWN


def score(j):
    """How many core fields have a real value. Stops a worse rerun overwriting a better one."""
    r = j.get("record") or {}
    return sum(1 for f in CORE if r.get(f) not in UNKNOWN)


def done(j):
    """Force mode targets api_type; normal mode targets 'not all-unknown'."""
    return api_known(j) if force else not failed(j)


def llm_failure(j):
    """True if the failure came from the LLM layer (quota, outage), not the app's pages."""
    return any("all models failed" in str(f).lower() for f in (j.get("flags") or []))


# ---- inputs ----
names, seeds = {}, {}
with open("data/apps.csv", encoding="utf-8-sig") as fh:
    for row in csv.DictReader(fh):
        k = row.get("id") or row.get("app_id") or row.get("slug") or row.get("name")
        names[k] = row.get("name") or row.get("app") or k
        if row.get("seed_urls"):            # urls separated by |
            seeds[k] = [u.strip() for u in row["seed_urls"].split("|") if u.strip()]

all_apps = [os.path.basename(p)[:-5] for p in sorted(glob.glob(f"{SRC}/*.json"))]
if force:
    missing = [a for a in force if a not in all_apps]
    if missing:
        print("unknown app ids (not in pass1_frozen), ignored:", missing)
    todo = [a for a in force if a in all_apps]
else:
    todo = [a for a in all_apps if failed(load(f"{SRC}/{a}.json"))]

# seeded apps first: they fail on pages, not quota, so they are the best use of scarce calls
todo.sort(key=lambda a: (a not in seeds, a))
print(f"{len(todo)} to {'FORCE' if force else 'retry'}:", todo)
no_seed = [a for a in todo if a not in seeds]
if force and no_seed:
    print("note: no seed_urls for", no_seed, "- the same pages may be fetched again")

# ---- loop ----
consec, stopped = 0, None
for app in todo:
    dest = f"{OUT}/{app}.json"
    old = load(dest) if os.path.exists(dest) else None
    if not force and old is not None and done(old):
        continue                             # already recovered, skip on rerun

    print("->", app, "(seeded)" if app in seeds else "")
    out = research_app(app, names.get(app, app), seeds=seeds.get(app, ()))

    # regression guard: keep the better of old vs new
    if old is not None:
        shutil.copy(dest, dest + ".bak")
        if score(out) < score(old):
            print(f"    new result worse ({score(out)} < {score(old)} core fields); kept previous")
            out = old

    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    r = out.get("record") or {}
    print("   ", "OK" if done(out) else "STILL FAILED",
          f"| api_type={r.get('api_type')} | core known {score(out)}/{len(CORE)}",
          (out.get("flags") or [])[:2])

    if quota_dead():
        stopped = "daily quota exhausted on all models. Rerun after ~13:30 IST or enable billing."
        break
    if not done(out) and llm_failure(out):
        consec += 1
        if consec >= MAX_CONSEC_LLM_FAIL:
            stopped = f"{consec} consecutive 'all models failed'. Check quota/key, then rerun."
            break
    else:
        consec = 0
    time.sleep(SLEEP)

# ---- summary ----
left = []
for a in todo:
    p = f"{OUT}/{a}.json"
    if not os.path.exists(p) or not done(load(p)):
        left.append(a)
print(f"\nrecovered {len(todo) - len(left)}/{len(todo)}; still failed or not attempted: {left}")
if stopped:
    print("STOPPED EARLY:", stopped)