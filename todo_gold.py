import json

START = {
 "hubspot": "https://developers.hubspot.com", "dealcloud": "https://api.docs.dealcloud.com",
 "zendesk": "https://developer.zendesk.com", "plain": "https://www.plain.com/docs",
 "twilio": "https://www.twilio.com/docs", "telegram": "https://core.telegram.org/bots/api",
 "google_ads": "https://developers.google.com/google-ads", "mailchimp": "https://mailchimp.com/developer",
 "shopify": "https://shopify.dev", "ecwid": "https://api-docs.ecwid.com",
 "firecrawl": "https://docs.firecrawl.dev", "sherlock": "https://github.com/sherlock-project/sherlock",
 "github": "https://docs.github.com/rest", "cloudflare": "https://developers.cloudflare.com/api",
 "notion": "https://developers.notion.com", "jira": "https://developer.atlassian.com",
 "stripe": "https://stripe.com/docs/api", "pitchbook": "https://pitchbook.com",
 "notebooklm": "https://cloud.google.com/gemini", "mermaid_cli": "https://github.com/mermaid-js/mermaid-cli",
}
F = ["auth_methods", "access_test", "access_ship", "api_type", "official_mcp"]
g = json.load(open("verification/gold.json", encoding="utf-8"))
todo = [(a, [f for f in F if g[a][f] in ("", [])]) for a in g]
todo = [(a, m) for a, m in todo if m]
print(len(todo), "apps with blank fields\n")
for a, missing in todo:
    print(f"{a:12} missing {len(missing)} -> {START.get(a, '')}")