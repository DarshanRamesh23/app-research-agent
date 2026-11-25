"""One-command run:  python -m agent run --app Attio"""
import argparse
import csv
import re
import runpy
import sys
from pathlib import Path

APPS = Path("data/apps.csv")


def resolve(query):
    q = query.strip().lower()
    if APPS.exists():
        with APPS.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if q in (row.get("id", "").lower(), row.get("name", "").lower()):
                    return row["id"], row["name"]
    slug = re.sub(r"[^a-z0-9]+", "_", q).strip("_")
    print(f"[warn] '{query}' not in {APPS}; using id '{slug}'", file=sys.stderr)
    return slug, query.strip()


def main():
    p = argparse.ArgumentParser(prog="python -m agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="research one app")
    r.add_argument("--app", required=True, help="app name or id, e.g. Attio")
    args = p.parse_args()
    app_id, name = resolve(args.app)
    sys.argv = ["agent.research", app_id, name]
    runpy.run_module("agent.research", run_name="__main__")


if __name__ == "__main__":
    main()