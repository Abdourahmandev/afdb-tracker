# AfDB Job Tracker

Automatically scrapes data-related jobs from the African Development Bank careers portal weekly, scores each new posting against your profile using Google Gemini AI, sends you an email alert for high-scoring matches, and generates a self-contained **HTML dashboard** with the full job list and run history.

---

## How It Works

1. **Every Monday at 08:00 UTC**, the pipeline wakes up inside Docker
2. It opens the AfDB job board with Playwright (headless Chrome), searches for "data", and paginates all results
3. New jobs (not seen before) are scraped in detail and saved to a local DuckDB database
4. Google Gemini reads each job + your `profile.md` and returns a **score from 1 to 10** with a match explanation
5. If the score is ≥ your threshold (default: 7), you receive an **HTML email** with the score, match summary, key details, and a direct apply link
6. Jobs are never re-evaluated once stored — only new postings trigger notifications
7. After every run, a **static HTML report** (`data/report.html`) is regenerated with the full job table and weekly scan history

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed
- A **Gmail account** with an [App Password](https://support.google.com/accounts/answer/185833) set up
- A **Google Gemini API key** (free at [aistudio.google.com](https://aistudio.google.com/app/apikey))

---

## Setup (5 minutes)

### Step 1 — Fill in your profile

Open `profile.md` and fill in your background, skills, and preferences.

> **Tip**: Paste the template to ChatGPT and say: *"Fill this in based on what you know about me."*

### Step 2 — Create your `.env` file

```bash
cp .env.example .env
```

Then edit `.env`:

```env
GEMINI_API_KEY=your_key_here
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop   # 16-char App Password
RECIPIENT_EMAIL=your_email@gmail.com
SCORE_THRESHOLD=7
RUN_DAY=monday
RUN_HOUR=08
```

#### How to get a Gmail App Password
1. Go to your Google Account → **Security**
2. Under "How you sign in to Google", enable **2-Step Verification** if not already enabled
3. Search for **"App Passwords"** in the Security page search bar
4. Create a new App Password named "AfDB Tracker"
5. Copy the 16-character password into `GMAIL_APP_PASSWORD`

### Step 3 — Build the Docker image

```bash
docker build -t afdb-tracker .
```

This downloads Python, installs Chromium, and packages everything. Takes ~3–5 minutes the first time.

### Step 4 — Run the container

```bash
docker run -d \
  --name afdb-tracker \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  afdb-tracker
```

On Windows (PowerShell):
```powershell
docker run -d `
  --name afdb-tracker `
  --env-file .env `
  -v "${PWD}/data:/app/data" `
  afdb-tracker
```

The container will run silently in the background and execute the pipeline every Monday at 08:00 UTC.

---

## Run the Pipeline Immediately (for testing)

Add `RUN_NOW=1` to trigger a run as soon as the container starts:

```bash
docker run -d \
  --name afdb-tracker-test \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  -e RUN_NOW=1 \
  afdb-tracker
```

---

## View Logs

```bash
docker logs -f afdb-tracker
```

---

## Stop / Restart

```bash
docker stop afdb-tracker
docker start afdb-tracker    # resumes — schedule continues
```

---

## Change Schedule

Edit `.env`:
```env
RUN_DAY=wednesday   # any day: monday–sunday
RUN_HOUR=10          # 24h format
```

Then recreate the container:
```bash
docker stop afdb-tracker && docker rm afdb-tracker
docker run -d --name afdb-tracker --env-file .env -v "${PWD}/data:/app/data" afdb-tracker
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

After each pipeline run, a self-contained file is written to `data/report.html`.  
Open it in any browser — no server, no dependencies.

**Features:**
- **Stats bar** — total jobs, evaluated, emails sent, average score, top scorers
- **Weekly Scan History** (collapsible) — every run logged with trigger type, new jobs found, duration, and status
- **Jobs table** — sortable columns, color-coded score badges, collapsible AI summary + full description per job, direct apply links
- Score colors: 🟢 9–10 excellent · 🔵 7–8 good · ⚪ ≤6 weak · 🟡 not evaluated

To regenerate the report manually without running the full pipeline:

```powershell
# From the project root (local)
$env:DATA_DIR=".\data"; $env:PYTHONPATH=".\src"
python -c "from db import init_db; from report_generator import generate_report; init_db(); print(generate_report())"
```

---

## Transfer to Another Computer

### Option A — GitHub clone (recommended)

```bash
git clone https://github.com/Abdourahmandev/afdb-tracker.git
cd afdb-tracker
docker build -t afdb-tracker .
```

Copy your `.env` and `data/jobs.duckdb` to the new machine, then run:

```powershell
docker run -d --name afdb-tracker --restart unless-stopped `
  --env-file .env `
  -v C:\afdb-tracker\data:/app/data `
  afdb-tracker
```

### Option B — Save/load image (no internet needed)

```bash
# This computer
docker save afdb-tracker | gzip > afdb-tracker.tar.gz

# New computer (only Docker needed — no Python, no pip)
docker load < afdb-tracker.tar.gz
```

Then copy your `.env` and `data/` folder and run the container as above.

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
├── .env.example            ← copy to .env and fill secrets
├── .gitignore
├── profile.md              ← YOUR profile (fill this in!)
├── README.md               ← this file
└── src/
    ├── scheduler.py        ← Docker entrypoint, weekly cron
    ├── main.py             ← pipeline orchestrator
    ├── scraper.py          ← Playwright scraper
    ├── db.py               ← DuckDB operations (jobs, evaluations, run_history)
    ├── evaluator.py        ← Gemini AI scorer
    ├── notifier.py         ← Gmail email sender
    └── report_generator.py ← static HTML dashboard generator
data/
├── jobs.duckdb             ← persisted job + evaluation + run history (volume-mounted)
└── report.html             ← auto-generated dashboard (open in any browser)
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `GEMINI_API_KEY` error | Check key in `.env`; get one at aistudio.google.com |
| `SMTPAuthenticationError` | Use App Password, not your real Gmail password |
| No jobs scraped | AfDB site may have changed; check `docker logs` for Playwright errors |
| Container stops immediately | Check `docker logs afdb-tracker` for Python errors |
| Email in spam | Add your `GMAIL_USER` address to contacts |
| `run_history` table missing | Run `init_db()` once — happens automatically on first pipeline run |
| Docker build fails (credential error) | Run `docker login` on the machine or use `docker cp` to update files without rebuilding |

---

## Reference Docs

- [Gmail App Passwords](https://support.google.com/accounts/answer/185833)
- [Google Gemini API free tier](https://ai.google.dev/gemini-api/docs/models/gemini)
- [Playwright Python docs](https://playwright.dev/python/docs/intro)
- [Python `schedule` library](https://schedule.readthedocs.io/)
- [DuckDB Python docs](https://duckdb.org/docs/api/python/overview)
