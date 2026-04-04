# AfDB Job Tracker

Automatically scrapes data-related jobs from the African Development Bank careers portal weekly, scores each new posting against your profile using Google Gemini AI, sends you an email alert for high-scoring matches, and publishes a **live HTML dashboard** to Azure Blob Storage.

**Live dashboard:** https://afdbtracker4990.z13.web.core.windows.net/

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
