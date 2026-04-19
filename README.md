# AfDB-Platform

A multi-tenant SaaS platform that automatically scrapes jobs from international organizations (AfDB, World Bank, UNDP, IMF), scores each posting against your career profile using Google Gemini AI, and delivers personalized weekly alerts via email and a live web dashboard.

**Live platform (prod):** https://gray-ground-0b9535b0f.2.azurestaticapps.net
**Legacy single-user dashboard:** https://afdbtracker4990.z13.web.core.windows.net/

> **Phase I — Complete.** The platform is live in production: weekly pipeline runs automatically, Entra External ID login is working, and real users can register, receive scored job alerts, and browse their personalized dashboard.
> **Phase II — In progress.** Full UI redesign (Sprint 7) — see [Phase II Roadmap](#phase-ii--sprint-7--ui-redesign) below.

---

## How It Works

1. **Every Monday at 08:00 UTC**, an Azure Logic App fires and starts the pipeline container
2. The container opens the AfDB job board with Playwright (headless Chrome), searches for "data", and paginates all results
3. New jobs (not seen before) are scraped in detail and saved to a DuckDB database stored on **Azure Files** (persistent across runs)
4. Google Gemini reads each job + your `profile.md` and returns a **score from 1 to 10** with a match explanation
5. If the score is ≥ your threshold (default: 7), you receive an **HTML email** with the score, match summary, key details, and a direct apply link
6. Jobs are never re-evaluated once stored — only new postings trigger notifications
7. After every run, a **static HTML report** is uploaded to Azure Blob Storage and publicly accessible at the URL above

---

## Prerequisites

- An **Azure account** ([portal.azure.com](https://portal.azure.com))
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) installed
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed (for building/pushing images)
- A **Gmail account** with an [App Password](https://support.google.com/accounts/answer/185833) set up
- A **Google Gemini API key** (free at [aistudio.google.com](https://aistudio.google.com/app/apikey))

---

## Azure Infrastructure

| Resource | Name | Purpose |
|---|---|---|
| Resource Group | `afdb-tracker-rg` | Container for all resources |
| Storage Account | `afdbtracker4990` | Azure Files (DB) + Blob static website (report) |
| Azure Files share | `afdb-data` | Persistent `/app/data` — survives container restarts |
| Container Registry | `afdbtrackercr` | Hosts the Docker image |
| Container Instance | `afdb-container` | Runs the pipeline (starts, runs, stops) |
| Logic App | `afdb-weekly-trigger` | CRON: every Monday 08:00 UTC → starts ACI |

---

## Setup

### Step 1 — Fill in your profile

Open `profile.md` and fill in your background, skills, and preferences.

> **Tip**: Paste the template to ChatGPT and say: *"Fill this in based on what you know about me."*

### Step 2 — Configure `.env`

Edit `.env` with your secrets:

```env
GEMINI_API_KEY=your_key_here
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop   # 16-char App Password
RECIPIENT_EMAIL=your_email@gmail.com
SCORE_THRESHOLD=7
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...  # from Azure Portal
```

#### How to get a Gmail App Password
1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** if not already on
3. Search for **"App Passwords"**, create one named "AfDB Tracker"
4. Copy the 16-character password into `GMAIL_APP_PASSWORD`

### Step 3 — Build and push the Docker image

```powershell
az acr login --name afdbtrackercr
docker build -t afdbtrackercr.azurecr.io/afdb-tracker:latest .
docker push afdbtrackercr.azurecr.io/afdb-tracker:latest
```

### Step 4 — Upload your DB (first time or after local runs)

```powershell
$CONN = az storage account show-connection-string --name afdbtracker4990 --resource-group afdb-tracker-rg --query connectionString -o tsv
az storage file upload --connection-string $CONN --share-name afdb-data --source .\data\jobs.duckdb --path jobs.duckdb
```

---

## Run the Pipeline Manually

Start the ACI container on demand (it runs once and stops automatically):

```powershell
az container start --name afdb-container --resource-group afdb-tracker-rg
```

Watch live logs:

```powershell
az container logs --name afdb-container --resource-group afdb-tracker-rg --follow
```

Check last run result:

```powershell
az container show --name afdb-container --resource-group afdb-tracker-rg `
  --query "{state:instanceView.state, exitCode:containers[0].instanceView.currentState.exitCode}" -o table
```

---

## Change Schedule

The schedule is defined in the Logic App `afdb-weekly-trigger`. To change it, update the recurrence in the Azure Portal:

**Portal → afdb-tracker-rg → afdb-weekly-trigger → Logic app designer → Weekly_Monday_0800_UTC trigger**

Or via CLI (replace cron expression as needed — standard 5-field UTC cron):

```powershell
# Example: change to Wednesday at 09:00 UTC
# Update the Logic App definition in the Portal designer
```

---

## Inspect the Database

Your job history lives in `data/jobs.duckdb`. You can query it with:

```python
import duckdb
con = duckdb.connect("data/jobs.duckdb")
print(con.execute("SELECT job_id, title, scraped_at FROM jobs ORDER BY scraped_at DESC LIMIT 20").fetchdf())
print(con.execute("SELECT job_id, score, email_sent FROM evaluations ORDER BY evaluated_at DESC LIMIT 20").fetchdf())
print(con.execute("SELECT * FROM run_history ORDER BY run_at DESC LIMIT 10").fetchdf())
```

---

## HTML Dashboard

After each pipeline run, the report is automatically uploaded to:

**https://afdbtracker4990.z13.web.core.windows.net/**

A local copy is also saved to `data/report.html` on the Azure Files share.

**Features:**
- **Stats bar** — total jobs, evaluated, emails sent, average score, top scorers
- **Weekly Scan History** (collapsible) — every run logged with trigger type, new jobs found, duration, and status
- **Jobs table** — sortable columns, color-coded score badges, collapsible AI summary + full description per job, direct apply links
- Score colors: 🟢 9–10 excellent · 🔵 7–8 good · ⚪ ≤6 weak · 🟡 not evaluated

To download the current report locally:

```powershell
$CONN = az storage account show-connection-string --name afdbtracker4990 --resource-group afdb-tracker-rg --query connectionString -o tsv
az storage file download --connection-string $CONN --share-name afdb-data --path report.html --dest .\data\report.html
```

---

## Deploying Code Changes

After modifying source code, rebuild and push the image to ACR:

```powershell
az acr login --name afdbtrackercr
docker build -t afdbtrackercr.azurecr.io/afdb-tracker:latest .
docker push afdbtrackercr.azurecr.io/afdb-tracker:latest
```

ACI always pulls `:latest` on the next start — no container restart needed.

---

## Scoring Guide

| Score | Meaning |
|-------|---------|
| 9–10  | Excellent match — definitely apply |
| 7–8   | Good match — worth applying (`SCORE_THRESHOLD` default) |
| 5–6   | Partial match — missing some requirements |
| 3–4   | Weak match — significant gaps |
| 1–2   | Not relevant |

---

## Project Structure

```
afdb_job_tracker/
├── Dockerfile              ← single image: Python + Playwright + all deps
├── .env                    ← secrets (never commit this)
├── .gitignore
├── profile.md              ← YOUR profile (fill this in!)
├── README.md               ← this file
├── requirements.txt        ← Python deps incl. azure-storage-blob
└── src/
    ├── main.py             ← pipeline entrypoint (ACI runs this directly)
    ├── scheduler.py        ← local-only: weekly cron loop for Docker Desktop
    ├── scraper.py          ← Playwright scraper (--no-sandbox for Linux containers)
    ├── db.py               ← DuckDB operations (jobs, evaluations, run_history)
    ├── evaluator.py        ← Gemini AI scorer
    ├── notifier.py         ← Gmail email sender
    └── report_generator.py ← HTML dashboard + Azure Blob upload
data/                       ← mounted from Azure Files share (afdb-data)
├── jobs.duckdb             ← persisted job + evaluation + run history
└── report.html             ← auto-generated; also published to Azure Blob
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `GEMINI_API_KEY` error | Check key in `.env` and re-push image |
| `SMTPAuthenticationError` | Use App Password, not your real Gmail password |
| No jobs scraped | AfDB site may have changed; check ACI logs |
| ACI container stuck in Running | Check logs: `az container logs --name afdb-container --resource-group afdb-tracker-rg` |
| Email in spam | Add your `GMAIL_USER` address to contacts |
| `run_history` table missing | Runs automatically on first `init_db()` call |
| Report not updating at URL | Check ACI logs for Azure upload errors; verify `AZURE_STORAGE_CONNECTION_STRING` |
| Image not updating after push | ACI pulls `:latest` on each start — just push and trigger a new run |
| Logic App not firing | Check **Portal → afdb-weekly-trigger → Runs history** for errors |

---

## Reference Docs

- [Gmail App Passwords](https://support.google.com/accounts/answer/185833)
- [Google Gemini API free tier](https://ai.google.dev/gemini-api/docs/models/gemini)
- [Playwright Python docs](https://playwright.dev/python/docs/intro)
- [Python `schedule` library](https://schedule.readthedocs.io/)
- [DuckDB Python docs](https://duckdb.org/docs/api/python/overview)

---

## SaaS Platform Setup (Multi-Tenant)

> This section covers bootstrapping a fresh **AfDB-Platform** environment (dev or prod) from scratch.
> The legacy single-user pipeline above remains fully functional — `LEGACY_MODE=true` preserves it.

### Architecture

```
[Weekly Container Apps Job]  ← pipeline_v2.py + Playwright scraper
        ↓
[Azure Cosmos DB — NoSQL]    ← jobs | users | evaluations (free tier)
        ↓
[Azure Functions — FastAPI]  ← /register /verify /jobs /profile /sources
        ↓
[Azure Static Web Apps]      ← dashboard | profile | signup (vanilla JS)
        ↓
[Microsoft Entra External ID] ← MSAL.js SPA auth
```

### Prerequisites

- Azure CLI `az` (v2.50+) — `az login` before starting
- Bicep CLI — installed automatically by `az bicep build`
- GitHub CLI `gh` — for setting Actions secrets
- Python 3.11+ and `pip`
- A Gmail account with an App Password for notification emails
- A Google Gemini API key (free tier works)
- A Microsoft Entra External ID tenant (free) — see `docs/entra-setup.md`

### Step 1 — Deploy Azure Infrastructure

```bash
# Dev environment (australiacentral, B1 Function App, Cosmos DB free tier)
az deployment sub create \
  --location australiacentral \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/main.parameters.dev.json \
  --parameters entraExternalTenantId="<your-tenant-id>" entraClientId="<your-client-id>"

# Prod environment (same region — scraperImageTag left empty on first deploy)
az deployment sub create \
  --location australiacentral \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/main.parameters.prod.json \
  --parameters entraExternalTenantId="<your-tenant-id>" entraClientId="<your-client-id>"
```

Outputs: `resourceGroupName`, `functionsUrl`, `staticWebAppUrl`, `keyVaultName`.

### Step 2 — Seed Key Vault Secrets

```bash
# Assign yourself KV Secrets Officer first
KV_NAME=kv-afdb-dev   # or kv-afdb-prod
MY_ID=$(az ad signed-in-user show --query id -o tsv)
az role assignment create --role "Key Vault Secrets Officer" \
  --assignee "$MY_ID" --scope "$(az keyvault show --name $KV_NAME --query id -o tsv)"

# Set secrets
az keyvault secret set --vault-name $KV_NAME --name gemini-api-key    --value "<key>"
az keyvault secret set --vault-name $KV_NAME --name gmail-app-password --value "<password>"
az keyvault secret set --vault-name $KV_NAME --name gmail-user         --value "<email>"
az keyvault secret set --vault-name $KV_NAME --name EntraExternalTenantId --value "<tenant-id>"
az keyvault secret set --vault-name $KV_NAME --name EntraApiClientId   --value "<client-id>"
```

### Step 3 — Configure Function App

```bash
FUNC_NAME=func-afdb-dev   # or func-afdb-prod
RG=rg-afdb-dev            # or rg-afdb-prod
COSMOS_ENDPOINT=$(az cosmosdb show --name cosmos-afdb-dev --resource-group $RG \
  --query documentEndpoint -o tsv)

az functionapp config appsettings set --name $FUNC_NAME --resource-group $RG --settings \
  "GEMINI_API_KEY=@Microsoft.KeyVault(VaultName=${KV_NAME};SecretName=gemini-api-key)" \
  "GMAIL_APP_PASSWORD=@Microsoft.KeyVault(VaultName=${KV_NAME};SecretName=gmail-app-password)" \
  "GMAIL_USER=@Microsoft.KeyVault(VaultName=${KV_NAME};SecretName=gmail-user)" \
  "COSMOS_ENDPOINT=$COSMOS_ENDPOINT" \
  "COSMOS_DATABASE=afdb-platform" \
  "SKIP_AUTH=false"

# Enable Always On (required for B1 plan — prevents cold-start timeouts)
az functionapp config set --name $FUNC_NAME --resource-group $RG --always-on true
```

### Step 4 — Assign Cosmos DB Data Contributor Role

```bash
FUNC_IDENTITY=$(az functionapp identity show --name $FUNC_NAME --resource-group $RG \
  --query principalId -o tsv)
COSMOS_ID=$(az cosmosdb show --name cosmos-afdb-dev --resource-group $RG --query id -o tsv)

MSYS_NO_PATHCONV=1 az cosmosdb sql role assignment create \
  --account-name cosmos-afdb-dev --resource-group $RG \
  --role-definition-id "00000000-0000-0000-0000-000000000002" \
  --principal-id "$FUNC_IDENTITY" --scope "$COSMOS_ID"
```

### Step 5 — Deploy API

```bash
zip -r func-deploy.zip function_app.py host.json requirements.txt api/ src/ scrapers/config/
az functionapp stop  --name $FUNC_NAME --resource-group $RG
az functionapp deployment source config-zip --name $FUNC_NAME --resource-group $RG \
  --src func-deploy.zip --build-remote true --timeout 300
az functionapp start --name $FUNC_NAME --resource-group $RG

# Verify
curl https://${FUNC_NAME}.azurewebsites.net/api/health
# → {"status":"ok","version":"0.2.0"}
```

### Step 6 — Seed Cosmos DB

```bash
# Migrate 43 historical jobs + evaluations from local DuckDB → Cosmos DB
COSMOS_CONN="AccountEndpoint=<endpoint>;AccountKey=<key>;"
COSMOS_CONNECTION_STRING="$COSMOS_CONN" COSMOS_DATABASE="afdb-platform" \
  python scripts/migrate_duckdb_to_cosmos.py --jobs-only

# Then migrate evaluations once a user is registered:
COSMOS_CONNECTION_STRING="$COSMOS_CONN" COSMOS_DATABASE="afdb-platform" \
  python scripts/migrate_duckdb_to_cosmos.py --email your@email.com
```

### Step 7 — Set GitHub Actions Secrets

```bash
# SWA deployment tokens
gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_DEV  \
  --body "$(az staticwebapp secrets list --name swa-afdb-dev  --query 'properties.apiKey' -o tsv)"
gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PROD \
  --body "$(az staticwebapp secrets list --name swa-afdb-prod --query 'properties.apiKey' -o tsv)"

# Azure credentials (service principal JSON)
gh secret set AZURE_CREDENTIALS --body "$(cat azure-sp.json)"

# Function App names
gh variable set AZURE_FUNCTION_APP_NAME      --body "func-afdb-dev"
gh variable set AZURE_FUNCTION_APP_NAME_PROD --body "func-afdb-prod"
```

After setting secrets, push to `DEV` → deploys to dev. Push/merge to `main` → deploys to prod.

### Step 8 — Entra External ID

Follow `docs/entra-setup.md` for the one-time tenant + app registration steps.
Key URLs needed in `frontend/js/env.js`:
- `ENTRA_TENANT_ID` — from Azure Portal → Entra External ID tenant → Overview
- `ENTRA_CLIENT_ID` — from the SPA app registration → Overview

### SaaS Resource Summary

| Resource | Dev name | Prod name | Cost |
|---|---|---|---|
| Resource Group | `rg-afdb-dev` | `rg-afdb-prod` | free |
| Cosmos DB (NoSQL) | `cosmos-afdb-dev` | `cosmos-afdb-prod` | free tier |
| Key Vault | `kv-afdb-dev` | `kv-afdb-prod` | ~$0 |
| App Service Plan (B1) | `asp-afdb-dev` | `asp-afdb-prod` | ~$13/mo |
| Function App | `func-afdb-dev` | `func-afdb-prod` | included in B1 |
| Static Web App | `swa-afdb-dev` | `swa-afdb-prod` | free |
| Container Registry | `acrafdbdev` | `acrafdbprod` | ~$5/mo (when used) |

---

## Phase II · Sprint 7 — UI Redesign

> **Goal:** Replace the functional Phase I frontend with a polished, professional product that converts real users and can be shown to investors.
> The backend, API, pipeline, and auth are untouched — this is a pure frontend sprint.

### Why this matters

Phase I proved the platform works end-to-end. Phase II makes it a product people are proud to use and willing to recommend.

The current UI is a developer's test page. A professional landing on it today — referred by a colleague or finding it on LinkedIn — would not trust it with their job search or their email address. Sprint 7 fixes that.

### What changes for users

| Feature | What it delivers |
|---|---|
| **New landing page** | Clear value proposition, feature highlights, social proof, single CTA. A visitor understands the product in 5 seconds and signs up. |
| **Animated job cards** | Source branding badge (AfDB, World Bank…), visual match score ring (e.g. "91% match"), hover states. The difference between a spreadsheet and a product. |
| **Dashboard redesign** | Split-pane layout, advanced filters sidebar (source, score threshold, category), saved searches. Browse 50 scored jobs without scrolling a flat list. |
| **Profile editor redesign** | Rich text career profile field, drag-and-drop source ordering, live score preview. The platform visibly learns the user. |
| **Mobile-first responsive layout** | Dashboard fully usable on a 375px phone screen. Professionals check job alerts on the go, not at a desk. |
| **Dark mode** | System preference detection + manual toggle. Table stakes for any modern SaaS. |
| **Loading skeletons + micro-animations** | Skeleton cards appear instantly while the API responds. Smooth transitions signal a maintained, polished product. |
| **Onboarding redesign** | Step progress indicator, inline validation, tooltips on score threshold. Drop-off between registration step 1 and step 3 goes down. |
| **Accessibility (WCAG 2.1 AA)** | Screen reader support, keyboard navigation, sufficient color contrast throughout. |

### What stays the same

- All API endpoints (`/api/jobs`, `/api/profile`, `/api/register`, `/api/sources`) — backend untouched
- MSAL authentication (Entra External ID) — same tokens, same flow
- Deployment: same SWA + GitHub Actions CI/CD pipeline
- Weekly Container Apps Job pipeline — unaffected

### Sprint 7 checklist

- [ ] Design system: typography scale, color palette, spacing tokens, component library
- [ ] New landing page — hero section, feature highlights, social proof, CTA
- [ ] Animated job cards with source branding and match score ring indicator
- [ ] Dashboard redesign: split-pane layout, advanced filters sidebar, saved searches
- [ ] Profile editor redesign: rich text career profile, drag-and-drop source ordering
- [ ] Responsive mobile-first layout (dashboard usable on phone)
- [ ] Dark mode support
- [ ] Micro-animations and loading skeletons
- [ ] Onboarding flow redesign: step progress indicator, inline validation, tooltips
- [ ] Accessibility audit: WCAG 2.1 AA compliance

### After Sprint 7

- **Sprint 8:** World Bank scraper — doubles the job feed for every registered user
- **Sprint 9+:** UNDP, IMF, ADB scrapers; multi-source deduplication
- **Sprint 10+:** Profile-tag matching engine — replaces per-user Gemini scoring at scale (critical above ~50 users)
