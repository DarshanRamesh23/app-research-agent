import json, os, glob
NULLS = ["aircall","bigcommerce","clickup","coda","fathom","hubspot","linkedin_ads",
         "mongodb_atlas","mrscraper","notebooklm","otter_ai","pitchbook","ramp",
         "salesforce_commerce_cloud","snowflake","twilio","woocommerce","zoho_cliq"]
for app in NULLS:
    out = []
    for d in ("pass1_frozen", "final", "final_v2"):
        p = f"data/{d}/{app}.json"
        if not os.path.exists(p):
            out.append(f"{d}:MISSING"); continue
        j = json.load(open(p, encoding="utf-8"))
        rec = j.get("record") if isinstance(j, dict) else None
        extra = [k for k in j if k != "record"] if isinstance(j, dict) else []
        out.append(f"{d}:{'null' if rec is None else 'ok'}{extra}")
    print(app.ljust(26), " | ".join(out))

# hollow records: exist but nothing known
hollow = []
for p in glob.glob("data/final_v2/*.json"):
    j = json.load(open(p, encoding="utf-8")); r = j.get("record")
    if r and all(r.get(f) in (None, "unknown", ["unknown"]) for f in
                 ("access_ship", "api_type", "api_breadth", "official_mcp")):
        hollow.append(os.path.basename(p)[:-5])
print("\nhollow records:", len(hollow), hollow)