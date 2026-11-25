import json, webbrowser, urllib.parse

ORDER = ["github", "stripe", "notion", "twilio", "shopify", "cloudflare", "zendesk",
         "jira", "telegram", "firecrawl", "sherlock", "mermaid_cli", "hubspot", "dealcloud",
         "mailchimp", "google_ads", "ecwid", "plain", "pitchbook", "notebooklm"]
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

for app in ORDER:
    row = g.get(app)
    if row and any(row[f] in ("", []) for f in F):
        q = lambda t: "https://www.google.com/search?q=" + urllib.parse.quote(t)
        webbrowser.open(START[app])
        webbrowser.open(q(f"{app} API authentication OAuth API key"))
        webbrowser.open(q(f"{app} official MCP server"))
        print(f"NEXT: {app}")
        print("blank:", [f for f in F if row[f] in ("", [])], "+ source")
        break
else:
    print("all apps filled")