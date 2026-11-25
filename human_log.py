import csv, glob, json, os

p = "verification/human_log.csv"
rows = []
for f in sorted(glob.glob("data/pass1_frozen/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    if "no_sources" in d["flags"]:
        rows.append([os.path.basename(f)[:-5], "all_fields", "no_sources_found", "", "", ""])
if os.path.exists(p):
    print("human_log.csv exists, not overwriting")
else:
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["app", "field", "agent_said", "human_decision", "reason", "source_url"])
        w.writerows(rows)
    print(len(rows), "apps need a human decision")