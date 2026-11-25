import glob, json, os
from agent.verify import derive

SRC, OUT = "data/final", "data/final_v2"
os.makedirs(OUT, exist_ok=True)

for p in glob.glob(f"{SRC}/*.json"):
    d = json.load(open(p, encoding="utf-8"))
    r, applied = d.get("record"), []
    if r:
        # R1: a tool with no API cannot have API access
        if r["api_type"] in ("cli_only", "none"):
            for f in ("access_test", "access_ship"):
                if r[f] != "no_api":
                    r[f] = "no_api"; applied.append(f"R1:{f}")
        # R2: "no MCP" is an absence claim; without a quote it becomes unknown
        ev = r["evidence"].get("official_mcp", {})
        if r["official_mcp"] == "no" and not ev.get("quote"):
            r["official_mcp"] = "unknown"; applied.append("R2:official_mcp")
        r["verdict"], r["blocker"] = derive(r)
    d["rules"] = applied
    json.dump(d, open(f"{OUT}/{os.path.basename(p)}", "w", encoding="utf-8"), indent=2)
print("done")