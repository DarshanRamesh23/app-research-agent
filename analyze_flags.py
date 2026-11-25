import glob, json, re, collections
from agent.fetch import fetch

def norm(s): return re.sub(r"\s+", " ", s).strip().lower()

kinds = collections.Counter()
by_field = collections.Counter()
examples = []

for f in glob.glob("data/pass1/*.json"):
    d = json.load(open(f, encoding="utf-8"))
    rec = d["record"]
    if not rec: continue
    for field, ev in rec["evidence"].items():
        q, u = norm(ev["quote"]), ev["url"]
        if ev["confidence"] == 1.0 or len(q) < 15:
            continue
        by_field[field] += 1
        if u not in d["sources"]:
            kind = "url_not_a_fetched_source"
        else:
            page = norm(fetch(u)["text"])
            if q[:30] in page:
                kind = "partial_match (model altered the end)"
            else:
                kind = "not_on_page (fabricated or paraphrased)"
        kinds[kind] += 1
        if len(examples) < 8:
            examples.append((rec["id"], field, kind, ev["quote"][:90]))

print("\nBY KIND:", dict(kinds))
print("BY FIELD:", dict(by_field))
print()
for e in examples:
    print(e)

print("\nNO SOURCES:")
for f in glob.glob("data/pass1/*.json"):
    d = json.load(open(f, encoding="utf-8"))
    if "no_sources" in d["flags"]:
        print(" ", f.split("\\")[-1][:-5])