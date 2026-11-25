import csv, json, os, sys
from concurrent.futures import ThreadPoolExecutor
from agent.research import research_app

def run(app):
    path = f"data/pass1/{app['id']}.json"
    if os.path.exists(path):
        return app["id"], "cached"
    try:
        out = research_app(app["id"], app["name"], app.get("hint", ""))
    except Exception as e:
        out = {"record": None, "flags": [f"error:{str(e)[:80]}"], "sources": [], "model": None}
    json.dump(out, open(path, "w", encoding="utf-8"), indent=2)
    return app["id"], "done"

if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/apps.csv"
    os.makedirs("data/pass1", exist_ok=True)
    apps = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    with ThreadPoolExecutor(3) as ex:
        for i, (aid, st) in enumerate(ex.map(run, apps), 1):
            print(f"[{i}/{len(apps)}] {aid} {st}")