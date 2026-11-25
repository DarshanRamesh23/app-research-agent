import csv, json, subprocess

old = json.loads(subprocess.check_output(["git", "show", "46bd730:verification/gold.json"]).decode("utf-8"))
new = json.load(open("verification/gold.json", encoding="utf-8"))
F = ["auth_methods", "access_test", "access_ship", "api_type", "official_mcp"]
rows = []
for app in new:
    for f in F:
        a, b = old.get(app, {}).get(f), new[app][f]
        if a != b:
            rows.append([app, f, json.dumps(a), json.dumps(b), "", new[app].get("source", "")])
with open("verification/gold_corrections.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["app", "field", "before", "after", "reason_from_docs", "source_url"])
    w.writerows(rows)
print(len(rows), "gold changes since first fill")