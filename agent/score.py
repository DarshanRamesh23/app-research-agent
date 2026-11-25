"""
Score pass1 / final_v2 / final_v3 against a gold file.

  python -m agent.score                                   (gold = verification/gold.json)
  python -m agent.score --gold verification/gold_before.json --tag before

Metrics (fixed before rescoring, do not tune):
  strict        exact match (auth lists compared as sets); abstain/missing record = not correct
  lenient       auth passes if the answer contains ALL gold methods (extras allowed); other fields = strict
  answered-only correct / (correct + wrong), abstentions excluded
A missing record counts as an abstention (the agent gave no answer).
"""
import argparse, csv, json, os

ap = argparse.ArgumentParser()
ap.add_argument("--gold", default="verification/gold.json")
ap.add_argument("--tag", default="")
a = ap.parse_args()

GOLD = json.load(open(a.gold, encoding="utf-8"))
F = ["auth_methods", "access_test", "access_ship", "api_type", "official_mcp"]
STAGES = (("pass1", "data/pass1_frozen"), ("final_v2", "data/final_v2"), ("final_v3", "data/final_v3"))
UNK = ("unknown", ["unknown"], [], None, "")


def load(folder, aid):
    p = f"{folder}/{aid}.json"
    if not os.path.exists(p):
        return None, {}
    d = json.load(open(p, encoding="utf-8"))
    return d.get("record"), d


def norm(v):
    return sorted(v) if isinstance(v, list) else v


def cell(rec, f, g):
    """-> (strict_result, lenient_ok)"""
    ans = rec.get(f) if rec else None
    if ans in UNK:
        return "abstain", False
    strict = norm(ans) == norm(g)
    lenient = set(g) <= set(ans) if isinstance(g, list) and isinstance(ans, list) else strict
    return ("correct" if strict else "wrong"), lenient


report = {}
for stage, folder in STAGES:
    t = {f: {"correct": 0, "wrong": 0, "abstain": 0, "lenient": 0} for f in F}
    for aid, g in GOLD.items():
        rec, _ = load(folder, aid)
        for f in F:
            if g.get(f) in UNK:
                continue
            res, len_ok = cell(rec, f, g[f])
            t[f][res] += 1
            t[f]["lenient"] += int(len_ok)
    report[stage] = t

names = [s for s, _ in STAGES]
print(f"gold: {a.gold}  ({len(GOLD)} apps)")
print(f"{'field':14}" + "".join(f"{n:>11}" for n in names) + "   strict correct / graded")
for f in F:
    cells = []
    for s in names:
        t = report[s][f]
        cells.append(f"{t['correct']}/{t['correct'] + t['wrong'] + t['abstain']}")
    print(f"{f:14}" + "".join(f"{c:>11}" for c in cells))

print()
for s in names:
    c = sum(report[s][f]["correct"] for f in F)
    w = sum(report[s][f]["wrong"] for f in F)
    ab = sum(report[s][f]["abstain"] for f in F)
    le = sum(report[s][f]["lenient"] for f in F)
    n = c + w + ab
    print(f"{s:9} strict {c}/{n} = {100*c/max(n,1):.0f}% | lenient {le}/{n} = {100*le/max(n,1):.0f}% | "
          f"answered-only {c}/{c+w} = {100*c/max(c+w,1):.0f}% | wrong {w} | abstained {ab}")

rows = []
for aid, g in GOLD.items():
    recs = {s: load(f, aid) for s, f in STAGES}
    for f in F:
        if g.get(f) in UNK:
            continue
        res = {s: cell(recs[s][0], f, g[f])[0] for s in names}
        if all(r == "correct" for r in res.values()):
            continue
        said = {s: (recs[s][0] or {}).get(f, "") for s in names}
        l2 = recs["final_v3"][1].get("l2", {}).get(f, {})
        rows.append([aid, f, g[f]] + [said[s] for s in names] + [res[s] for s in names]
                    + [l2.get("verdict", ""), l2.get("reason", "")])

suffix = f"_{a.tag}" if a.tag else ""
with open(f"verification/misses{suffix}.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["app", "field", "truth"] + [f"{s}_said" for s in names] + [f"{s}_result" for s in names]
               + ["l2_verdict", "l2_reason"])
    w.writerows(rows)
json.dump(report, open(f"verification/report{suffix}.json", "w", encoding="utf-8"), indent=2)
print(f"\n{len(rows)} rows written to verification/misses{suffix}.csv and report{suffix}.json")