"""
Merge pass1_frozen + pass1_retry -> pass1_merged. Never modifies either source folder.
Rule: retry wins only if it is strictly better than frozen (api_type known beats unknown,
then more core fields known). Ties keep frozen.
"""
import glob, json, os

SRC, RETRY, OUT = "data/pass1_frozen", "data/pass1_retry", "data/pass1_merged"
CORE = ("access_ship", "api_type", "api_breadth", "official_mcp")
UNKNOWN = (None, "unknown", ["unknown"])
os.makedirs(OUT, exist_ok=True)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rank(j):
    """(api_type known?, number of core fields known). Null or no-source records rank lowest."""
    r = j.get("record")
    if not r or r.get("blocker") == "no_sources_found":
        return (0, 0)
    known = sum(1 for f in CORE if r.get(f) not in UNKNOWN)
    return (1 if r.get("api_type") not in UNKNOWN else 0, known)


used, changed = [], []
for p in sorted(glob.glob(f"{SRC}/*.json")):
    app = os.path.basename(p)
    name = app[:-5]
    rp = f"{RETRY}/{app}"

    frozen = load(p)
    j, take_retry = frozen, False
    if os.path.exists(rp):
        retry = load(rp)
        if rank(retry) > rank(frozen):
            j, take_retry = retry, True

    if take_retry:
        j["rerun"] = True                    # page can flag these apps
        used.append(name)
        if rank(frozen)[0] == 1:             # frozen already had api_type, retry still won on more fields
            changed.append(name)

    with open(f"{OUT}/{app}", "w", encoding="utf-8") as fh:
        json.dump(j, fh, indent=2)

print(len(used), "apps taken from retry:", used)
if changed:
    print("of which frozen already had api_type (retry won on more fields):", changed)

# coverage report on the merged set
unknown_api = []
for p in sorted(glob.glob(f"{OUT}/*.json")):
    r = load(p).get("record") or {}
    if r.get("api_type") in UNKNOWN:
        unknown_api.append(os.path.basename(p)[:-5])
total = len(glob.glob(f"{OUT}/*.json"))
print(f"api_type unknown: {len(unknown_api)}/{total} (coverage {1 - len(unknown_api) / total:.0%})")