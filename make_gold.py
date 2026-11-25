import json, os

APPS = ["hubspot", "dealcloud", "zendesk", "plain", "twilio", "telegram",
        "google_ads", "mailchimp", "shopify", "ecwid", "firecrawl", "sherlock",
        "github", "cloudflare", "notion", "jira", "stripe", "pitchbook",
        "notebooklm", "mermaid_cli"]
FIELDS = ["auth_methods", "access_test", "access_ship", "api_type", "official_mcp"]

p = "verification/gold.json"
if os.path.exists(p):
    print("gold.json already exists, not overwriting")
else:
    g = {a: {**{f: "" for f in FIELDS}, "source": ""} for a in APPS}
    json.dump(g, open(p, "w", encoding="utf-8"), indent=2)
    print("template written:", len(g), "apps")