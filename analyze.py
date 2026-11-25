import argparse, glob, json, os
import pandas as pd

SRC = "data/final_v2"
OUT = "site/patterns"

# Enum guesses: run `python analyze.py --counts` and fix these to match your schema.
SELF_SERVE = {"free_self_serve", "free_trial"}
GATED = {"paid_plan", "partner_gated", "approval_required", "admin_approval", "enterprise_only"}
NO_API = {"no_api"}
WIDE = {"medium", "broad"}
KNOWN_ACCESS = SELF_SERVE | GATED | NO_API | {"unknown"}
VERDICT_MAP = {"buildable_now": "green", "buildable_with_caveat": "yellow", "unknown": "unknown"}
FIELDS = ("access_test", "access_ship", "api_type", "api_breadth", "official_mcp")


def verdict_norm(v):
    v = str(v or "").lower()
    return VERDICT_MAP.get(v, "red" if v else "unknown")


def load_categories(path):
    """CSV or JSON with columns/keys: id, category. Optional."""
    if not path:
        return {}
    if path.endswith(".json"):
        d = json.load(open(path, encoding="utf-8"))
        if isinstance(d, dict):
            return {str(k): v for k, v in d.items()}
        return {str(x["id"]): x["category"] for x in d}
    c = pd.read_csv(path)
    return dict(zip(c["id"].astype(str), c["category"]))


def load(cats):
    rows, empty = [], []
    for p in sorted(glob.glob(os.path.join(SRC, "*.json"))):
        fid = os.path.splitext(os.path.basename(p))[0]
        d = json.load(open(p, encoding="utf-8"))
        r = d.get("record") if isinstance(d, dict) else None
        if not isinstance(r, dict):
            empty.append(fid)
            r = {}
        auth = r.get("auth_methods") or []
        auth = [auth] if isinstance(auth, str) else list(auth)
        rid = r.get("id") or fid
        row = {"id": rid, "category": cats.get(rid) or cats.get(fid) or "uncategorized",
               "auth_methods": auth,
               "verdict": verdict_norm(r.get("verdict")) if r else "unknown",
               "blocker": (r.get("blocker") or "none") if r else "unknown"}
        for f in FIELDS:
            row[f] = r.get(f) or "unknown"
        rows.append(row)
    return pd.DataFrame(rows), empty


def serve_class(a):
    if a in SELF_SERVE: return "self_serve"
    if a in NO_API: return "no_api"
    if a == "unknown": return "unknown"
    return "gated"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", action="store_true", help="print enum value counts and exit")
    ap.add_argument("--categories", help="CSV/JSON mapping id -> category")
    a = ap.parse_args()

    df, empty = load(load_categories(a.categories))
    n = len(df)
    if n == 0:
        raise SystemExit("no records found")

    if a.counts:
        for c in FIELDS + ("verdict", "blocker"):
            print(c, df[c].value_counts().to_dict())
        return

    os.makedirs(OUT, exist_ok=True)
    print(f"{n} apps loaded from {SRC}; {len(empty)} with no record: {empty}")

    odd = sorted(set(df.access_ship) | set(df.access_test) - KNOWN_ACCESS)
    odd = [v for v in odd if v not in KNOWN_ACCESS]
    if odd:
        print("WARNING: access values not in SELF_SERVE/GATED/NO_API, fix the sets:", odd)

    has_cat = (df.category != "uncategorized").any()
    ex = df.explode("auth_methods").fillna({"auth_methods": "none"})

    # 1. auth x category, 2. access x category (only if categories supplied)
    if has_cat:
        pd.crosstab(ex["category"], ex["auth_methods"]).to_csv(f"{OUT}/auth_by_category.csv")
        pd.crosstab(df["category"], df["access_ship"]).to_csv(f"{OUT}/access_by_category.csv")
    pd.crosstab(ex["auth_methods"], ex["category"]).sum(axis=1).to_csv(
        f"{OUT}/auth_counts.csv", header=["count"])

    # 3. test vs ship gap
    pd.crosstab(df["access_test"], df["access_ship"]).to_csv(f"{OUT}/test_vs_ship.csv")
    test_ok = df.access_test.isin(SELF_SERVE)
    gap = int((test_ok & df.access_ship.isin(GATED)).sum())

    # 4. blockers (non-green, known only)
    blk = df[~df.verdict.isin(["green", "unknown"])]["blocker"].value_counts()
    blk.to_csv(f"{OUT}/blockers.csv", header=["count"])

    # 5. quadrant
    df["serve"] = df.access_ship.map(serve_class)
    df["width"] = df.api_breadth.map(lambda b: "unknown" if b == "unknown" else ("wide" if b in WIDE else "narrow"))
    quad = (df.groupby(["serve", "width"])["id"].apply(list).reset_index()
              .rename(columns={"id": "apps"}))
    quad["count"] = quad["apps"].map(len)
    quad.to_json(f"{OUT}/quadrant.json", orient="records", indent=2)
    easy = df[(df.serve == "self_serve") & (df.width == "wide")]["id"].tolist()
    outreach = df[df.serve == "gated"]["id"].tolist()

    # 6. MCP coverage (no vs unknown kept separate)
    mcp = df.official_mcp.value_counts()
    mcp.to_csv(f"{OUT}/mcp_coverage.csv", header=["count"])
    m = lambda k: int(mcp.get(k, 0))

    vc = df.verdict.value_counts()
    g, y, r_, u = (int(vc.get(k, 0)) for k in ("green", "yellow", "red", "unknown"))
    top_auth = ex[ex.auth_methods != "none"]["auth_methods"].value_counts()

    heads = [f"{g} of {n} apps are buildable now, {y} with a caveat, {r_} blocked, {u} unknown."]
    if len(top_auth):
        s = f"{top_auth.index[0]} is the most common auth method ({int(top_auth.iloc[0])} apps)"
        if len(top_auth) > 1:
            s += f", then {top_auth.index[1]} ({int(top_auth.iloc[1])})"
        heads.append(s + ".")
    if has_cat:
        known = df[df.serve.isin(["self_serve", "gated"])]
        gc = (known.assign(g=known.serve == "gated").groupby("category")["g"].agg(["mean", "size"]))
        gc = gc[gc["size"] >= 3].sort_values("mean", ascending=False)
        if len(gc):
            heads.append(f"Most gated category: {gc.index[0]} ({gc['mean'].iloc[0]:.0%} of {int(gc['size'].iloc[0])} apps).")
    if len(blk):
        heads.append(f"Top blocker: {blk.index[0]} ({int(blk.iloc[0])} apps).")
    heads += [
        f"{len(easy)} apps are easy wins (self-serve, medium/broad API); {len(outreach)} are gated and need outreach.",
        f"{gap} apps are free to test but gated to ship.",
        f"Official MCP: {m('yes')} yes, {m('community')} community, {m('no')} no, {m('unknown')} unknown "
        f"(L2 cannot prove a negative, so treat 'no' as 'not found').",
    ]
    open(f"{OUT}/headlines.txt", "w", encoding="utf-8").write("\n".join(heads))

    json.dump({
        "n": n, "no_record": empty,
        "verdicts": {"green": g, "yellow": y, "red": r_, "unknown": u},
        "blockers": blk.to_dict(), "mcp": mcp.to_dict(),
        "test_free_ship_gated": gap,
        "easy_wins": easy, "outreach": outreach, "headlines": heads,
    }, open(f"{OUT}/patterns.json", "w", encoding="utf-8"), indent=2)

    print("\n".join("- " + h for h in heads))
    print(f"\nwrote tables to {OUT}/")
    cov = 1 - (df.api_type == "unknown").mean()
    print(f"coverage (api_type known): {cov:.0%}")
    print("unknown counts:", {c: int((df[c] == "unknown").sum()) for c in FIELDS})
    if cov < 0.8:
        print("WARNING: coverage <80%. Fix the pipeline before publishing.")


if __name__ == "__main__":
    main()