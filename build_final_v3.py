"""
Build data/final_v3 without touching data/final or data/final_v2.

  1. Apps flagged rerun:true in data/pass1_merged (recovered by retry) -> L2 verify (agent.verify.process)
     + CLI rule -> data/final_v3
  2. Every other app -> copied unchanged from data/final_v2
  3. Self-check: my CLI-rule implementation is run on data/final and compared with data/final_v2.
     0 mismatches means this script's CLI rule matches the one that built final_v2.

Resumable: apps already in final_v3 are skipped. Stops cleanly on daily quota or 3 LLM failures in a row.
Run:  python build_final_v3.py
"""
import copy, glob, json, os, shutil, sys, time
from agent import verify as V
from agent.llm import AllModelsFailed, quota_dead

MERGED, V1, V2, OUT = "data/pass1_merged", "data/final", "data/final_v2", "data/final_v3"
os.makedirs(OUT, exist_ok=True)
V.OUT = OUT                      # verify.process writes to V.OUT at call time

# ---- detect LLM failures that verify.py would otherwise swallow (it turns them into 'unknown') ----
LLM_FAILED = False
_orig_call = V.call


def _flagged_call(*a, **k):
    global LLM_FAILED
    try:
        return _orig_call(*a, **k)
    except AllModelsFailed:
        LLM_FAILED = True
        raise


V.call = _flagged_call


def load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save(p, j):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(j, fh, indent=2)


def cli_rule(rec, changes=None):
    """cli_only/none -> access fields no_api, then re-derive verdict."""
    if rec.get("api_type") in ("cli_only", "none"):
        for f in ("access_test", "access_ship"):
            if rec.get(f) != "no_api":
                if changes is not None:
                    changes.append({"field": f, "before": rec.get(f), "after": "no_api", "action": "cli_rule"})
                rec[f] = "no_api"
    rec["verdict"], rec["blocker"] = V.derive(rec)


aid_of = lambda p: os.path.basename(p)[:-5]
merged = sorted(glob.glob(f"{MERGED}/*.json"))
rerun = [aid_of(p) for p in merged if load(p).get("rerun")]
others = [aid_of(p) for p in merged if aid_of(p) not in rerun]
print(f"{len(rerun)} apps to L2 (retry-recovered), {len(others)} to copy from final_v2")

# ---- self-check: does my CLI rule reproduce final_v2 from final? ----
mism = []
for a in others:
    p1, p2 = f"{V1}/{a}.json", f"{V2}/{a}.json"
    if not (os.path.exists(p1) and os.path.exists(p2)):
        continue
    r1, r2 = load(p1).get("record"), load(p2).get("record")
    if not r1 or not r2:
        continue
    r1 = copy.deepcopy(r1)
    cli_rule(r1)
    for f in ("access_test", "access_ship", "verdict", "blocker"):
        if r1.get(f) != r2.get(f):
            mism.append((a, f, r1.get(f), r2.get(f)))
print(f"self-check vs final_v2: {len(mism)} mismatches", mism[:5] if mism else "(CLI rule matches)")

# ---- copy unchanged apps ----
copied = missing = 0
for a in others:
    dst = f"{OUT}/{a}.json"
    if os.path.exists(dst):
        continue
    src = f"{V2}/{a}.json"
    if os.path.exists(src):
        shutil.copy(src, dst)
        copied += 1
    else:
        missing += 1
        print("  warning: not in final_v2:", a)
print(f"copied {copied} from final_v2" + (f", {missing} missing" if missing else ""))

# ---- L2 on retry-recovered apps ----
global_fail, consec, stopped = [], 0, None
for i, a in enumerate(rerun, 1):
    dst = f"{OUT}/{a}.json"
    if os.path.exists(dst):
        print(f"[{i}/{len(rerun)}] {a} (already done)")
        continue
    LLM_FAILED = False
    try:
        V.process(f"{MERGED}/{a}.json")
    except Exception as e:
        print(f"[{i}/{len(rerun)}] {a} ERROR {type(e).__name__}: {str(e)[:100]}")
        global_fail.append(a)
        if os.path.exists(dst):
            os.remove(dst)
        continue

    if LLM_FAILED:                           # verify.py swallowed an LLM failure: result is not trustworthy
        if os.path.exists(dst):
            os.remove(dst)
        global_fail.append(a)
        consec += 1
        print(f"[{i}/{len(rerun)}] {a} LLM failed, discarded (rerun later)")
        if quota_dead():
            stopped = "daily quota exhausted. Rerun after ~13:30 IST or enable billing."
            break
        if consec >= 3:
            stopped = "3 consecutive LLM failures. Check quota/key, then rerun."
            break
        continue
    consec = 0

    j = load(dst)
    rec = j.get("record")
    if rec:
        j.setdefault("changes", [])
        cli_rule(rec, j["changes"])
        save(dst, j)
    acts = [c.get("action") for c in (j.get("changes") or [])]
    print(f"[{i}/{len(rerun)}] {a}: " + (", ".join(sorted(set(acts))) if acts else "no changes"))
    time.sleep(2)

# ---- summary ----
done = [a for a in rerun if os.path.exists(f"{OUT}/{a}.json")]
tally = {}
for a in done:
    for c in load(f"{OUT}/{a}.json").get("changes") or []:
        tally[c.get("action")] = tally.get(c.get("action"), 0) + 1
print(f"\nL2 done on {len(done)}/{len(rerun)}; actions: {tally}")
if global_fail:
    print("not finished (rerun to retry):", global_fail)
if stopped:
    print("STOPPED EARLY:", stopped)

files = glob.glob(f"{OUT}/*.json")
unk = sum(1 for p in files if (load(p).get("record") or {}).get("api_type") in (None, "unknown"))
print(f"final_v3: {len(files)} apps, api_type unknown {unk} (coverage {1 - unk / max(len(files), 1):.0%})")