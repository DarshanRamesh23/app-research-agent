import glob, json, collections

act, l2 = collections.Counter(), collections.Counter()
errors = 0
for f in glob.glob("data/final/*.json"):
    d = json.load(open(f, encoding="utf-8"))
    for c in d.get("changes", []):
        if c["action"] == "l2_error":
            errors += 1
        else:
            act[c["action"]] += 1
    for v in (d.get("l2") or {}).values():
        l2[v.get("verdict")] += 1
print("L2 judgments:", dict(l2))
print("after re-research:", dict(act))
print("L2 call errors:", errors)