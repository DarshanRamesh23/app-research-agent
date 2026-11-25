# App research agent

Researches third-party apps for building agent toolkits: auth method, self-serve vs gated access, API surface, MCP availability, buildability verdict. Every answer carries a URL and a verbatim quote from that page. No quote found means `unknown`.

- **Results page:** <LIVE_PAGES_URL> (source: `site/index.html`; also `site/data.json`, `site/llms.txt`)
- **Final records for all 100 apps:** `data/final_v3/` (input list: `data/apps.csv`)
- **Summary counts:** `data/analysis.json`, derived from `data/final_v3/` (generated once, not by a script in this repo)

## How it works

```
apps.csv -> discover/fetch (cached in data/cache/) -> extract with quotes -> verify -> analyze -> build_site.py -> page + data.json + llms.txt
```

- **Pass 1:** the research agent fills the schema for each app. Copied to `data/pass1_frozen/` before any verification loop ran (git history can't show the order, so this is a copy, not a timestamp).
- **L1 rule checks:** enum values, evidence URL on the app's domain, quote must appear on the fetched page.
- **L2 verifier:** a separate model call sees only the claim and its evidence page and answers supported / contradicted / unverifiable.
- **Gold set:** apps checked by hand against the real docs (`verification/gold.json`, corrections in `verification/gold_corrections.csv`).
- **L5 human review:** decisions logged in `verification/human_log.csv`.

Access is recorded in two layers: `access_test` (can a developer get credentials to try it?) and `access_ship` (can a toolkit ship to users without a partnership or approval?).

## Setup

Python <VERSION> (the GitHub workflow uses the same).

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=your_key" > .env
```

## Run

One app (writes to `data/single/`, which is git-ignored):

```bash
python -m agent run --app "Attio"
```

All 100 apps (writes to `data/pass1/`):

```bash
python -m agent.run_all data/apps.csv
```

Rebuild the page from the final data:

```bash
python build_site.py
```

**Remote trigger:** GitHub Actions -> "Run research agent on one app" -> Run workflow. Needs the repo secret `GEMINI_API_KEY`. The record is saved as the `research-result` artifact.

## Results (honest version)

- Buildable today: 22 of 100. Buildable with a caveat: 17. Blocked: 1. Unknown: 53. No data: 7.
- Strict accuracy on the gold set: 44% -> 49% after the verification loops (wrong answers 22 -> 16), scored against the gold as first filled.
- After correcting 8 gold cells found during audit: 54% -> 59% (wrong 16 -> 10). Every corrected cell moved toward the agent's answer, so read the 59% with that in mind. The loop gain is about +5 points either way.
- Fixes were tuned on the same small gold set, so they may not generalize.

### Accuracy by field

<PER_FIELD_TABLE>

### Tricky apps

<APP -> what made it hard -> how the agent handled it>

## Known limits

- The agent uses Gemini plus plain page fetching. It does not use the Composio SDK or MCP tools.
- The gold set is 12 apps; the target of 20 wasn't reached.
- L2 ran on a mixed model chain (mostly the lite model). 17 apps have no L2 result and 7 have no record.
- Often only one page is fetched per app (e.g. pricing), so auth and API fields come back `unknown`. This is the main cause of the 53 unknowns.
- `mcp_url` can be empty even when `official_mcp` is `yes`. `official_mcp: no` means "not found", not proven absent.
- No browser fallback (L4) and no self-consistency loop (L3).
- Not resolved by hand: notebooklm, pitchbook, dealcloud (shown as `no_data`).

## Where a human was needed

Obscure apps with thin docs, apps with no API or an enterprise-only API, "contact sales" pages (gated vs upsell), the gold set, and the final verdict judgment calls.

## Cost per run

## Cost per run

$0. The whole project ran on the Gemini free tier (Google AI Studio, no billing enabled). The cost is limits, not money: free-tier daily quotas forced a fallback across models (`gemini-3.5-flash-lite` first), which is why L2 ran on a mixed chain and why some apps ended with no record. About <N> requests per app, about <M> for the full 100-app run.

### Tricky apps

The 8 gold cells corrected during audit show where hand-checking was itself error-prone (the gold was re-read against the docs and fixed):

| App | Field | Gold before | Gold after |
|---|---|---|---|
| Stripe | access_ship | admin_approval | free_self_serve |
| Stripe | auth_methods | api_key, bearer_token, oauth2 | api_key, basic, bearer_token |
| Shopify | access_ship | admin_approval | free_self_serve |
| Shopify | api_type | both | graphql |
| Zendesk | access_ship | admin_approval | free_trial |
| GitHub | auth_methods | oauth2, bearer_token | oauth2, bearer_token, jwt, basic |
| Jira | auth_methods | oauth2, basic, api_key | oauth2, basic, jwt |
| Firecrawl | auth_methods | api_key, bearer_token, oauth2 | api_key, oauth2 |

Pattern: "gated vs self-serve" (access_ship) and multi-value auth lists were the hardest fields to judge, for both the agent and the human.