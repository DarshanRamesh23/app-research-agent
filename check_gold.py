import json

OK = {
 "auth_methods": {"oauth2","api_key","basic","bearer_token","jwt","none","other"},
 "access_test": {"free_self_serve","free_trial","paid_plan","admin_approval","partner_gated","no_api"},
 "access_ship": {"free_self_serve","free_trial","paid_plan","admin_approval","partner_gated","no_api"},
 "api_type": {"rest","graphql","both","sdk_only","cli_only","none"},
 "official_mcp": {"yes","no","community"},
}
SKIP = ("", [], "unknown", ["unknown"])
g = json.load(open("verification/gold.json", encoding="utf-8"))
bad = 0
for app, row in g.items():
    for f, allowed in OK.items():
        v = row[f]
        if v in SKIP:
            continue
        if f == "auth_methods":
            if not isinstance(v, list) or any(x not in allowed for x in v):
                print(f"{app}.{f}: {v!r} (must be a list of {sorted(allowed)})"); bad += 1
        elif v not in allowed:
            print(f"{app}.{f}: {v!r} not allowed"); bad += 1
    if any(row[f] not in SKIP for f in OK) and (not row["source"] or row["source"].endswith("...")):
        print(f"{app}.source: missing or placeholder"); bad += 1
print("gold check:", "OK" if bad == 0 else f"{bad} problems")