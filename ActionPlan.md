# AfDB Job Tracker — Action Plan

## Project Overview
A standalone, fully Dockerized pipeline that:
1. Scrapes the African Development Bank (AfDB) careers portal weekly for **data-related jobs**
2. Evaluates each **new** job against your personal profile using Google Gemini (free AI API)
3. Emails you a scored summary for any job that scores ≥ your threshold — so you decide whether to apply

---

## Target URL
`https://afdb1.fcp.eu.fieldglass.cloud.sap/job_search_basic.do`
Keyword searched: **"data"** (covers Data Engineer, Data Analyst, Data Scientist, etc.)

---

## Tech Stack

| Concern         | Tool                                | Notes                                 |
|-----------------|-------------------------------------|---------------------------------------|
| Scraping        | **Playwright** (Python)             | SAP Fieldglass is JS-rendered; needs real browser |
| LLM             | **Google Gemini** `gemini-2.0-flash-lite` | Free tier: 1M tokens/day, 15 req/min |
| Email           | **Gmail SMTP** + App Password       | No 3rd-party service required         |
| Storage         | **DuckDB**                          | Lightweight, file-based               |
| Scheduler       | **Python `schedule` lib**           | Weekly cron inside Docker, no Airflow |
| Container       | **Single Docker image**             | Fully self-contained, portable        |

---

## Project Structure

```
afdb_job_tracker/
├── Dockerfile              ← single image: Python + Playwright Chromium + all deps
├── .env.example            ← copy to .env and fill in secrets
├── .gitignore
├── profile.md              ← YOUR background — fill via ChatGPT
├── ActionPlan.md           ← this file
├── README.md               ← setup, run, troubleshoot, transfer guide
└── src/
    ├── scheduler.py        ← Docker ENTRYPOINT; weekly cron via `schedule`
    ├── main.py             ← pipeline orchestrator
    ├── scraper.py          ← Playwright: search → paginate → detail scrape
    ├── db.py               ← DuckDB: schema + queries
    ├── evaluator.py        ← Gemini API: score + match summary
    └── notifier.py         ← Gmail SMTP HTML email sender
data/                       ← volume-mounted; contains jobs.duckdb
```

---

## Pipeline Flow (every Monday at 8am by default)

```
Playwright: search "data" on AfDB
  └─► paginate all result pages → list of (job_id, title, url)
        └─► check DuckDB: skip job_ids already seen
              └─► scrape detail page → structured job dict (JSON)
                    └─► INSERT into `jobs` table
                          └─► Gemini: score 1-10 + match summary vs profile.md
                                └─► INSERT into `evaluations` table
                                      └─► score ≥ SCORE_THRESHOLD?
                                            ├─ YES → send Gmail alert + mark email_sent=true
                                            └─ NO  → log and skip
```

---

## DuckDB Schema

### Table: `jobs`
| Column           | Type      | Description                          |
|------------------|-----------|--------------------------------------|
| job_id           | VARCHAR   | Unique ID from AfDB/Fieldglass        |
| title            | VARCHAR   | Job title                            |
| location         | VARCHAR   | Listed location                      |
| contract_type    | VARCHAR   | Contract/employment type             |
| deadline         | VARCHAR   | Application deadline                 |
| description_raw  | VARCHAR   | Full job description text            |
| url              | VARCHAR   | Direct link to job detail page       |
| scraped_at       | TIMESTAMP | When this record was scraped         |

### Table: `evaluations`
| Column       | Type      | Description                              |
|--------------|-----------|------------------------------------------|
| job_id       | VARCHAR   | Foreign key → jobs.job_id                |
| score        | INTEGER   | Gemini match score (1–10)                |
| summary      | VARCHAR   | LLM-generated match explanation          |
| evaluated_at | TIMESTAMP | When evaluation was run                  |
| email_sent   | BOOLEAN   | Whether an email alert was sent          |

---

## Environment Variables (`.env`)

| Variable           | Description                                         |
|--------------------|-----------------------------------------------------|
| `GEMINI_API_KEY`   | From https://aistudio.google.com/app/apikey         |
| `GMAIL_USER`       | Your Gmail address                                  |
| `GMAIL_APP_PASSWORD` | 16-character App Password (not your regular password) |
| `RECIPIENT_EMAIL`  | Where to receive alerts (can be same as GMAIL_USER) |
| `SCORE_THRESHOLD`  | Minimum score to send email (default: 7)            |
| `RUN_DAY`          | Day to run weekly (default: monday)                 |
| `RUN_HOUR`         | Hour to run in 24h format (default: 08)             |

---

## Implementation Phases

### Phase 1 — Scaffold ✅
- Folder structure, `requirements.txt`, `.env.example`, `.gitignore`
- `ActionPlan.md` (this file), `profile.md` template

### Phase 2 — Database (`db.py`)
- DuckDB init, create tables if not exist
- `is_new_job(job_id)` → bool
- `insert_job(job_dict)`
- `insert_evaluation(job_id, score, summary, email_sent)`

### Phase 3 — Scraper (`scraper.py`)
- Playwright: load AfDB search, submit "data" keyword
- Paginate all result pages → list of `(job_id, title, url)`
- For each new job_id: scrape detail page → structured dict

### Phase 4 — LLM Evaluator (`evaluator.py`)
- Load `profile.md`; build Gemini prompt
- Returns JSON `{score: int, summary: str}`
- Retry logic for API errors / malformed JSON

### Phase 5 — Email Notifier (`notifier.py`)
- Gmail SMTP with App Password
- HTML email: score badge + match summary + key details + apply link

### Phase 6 — Orchestrator (`main.py`)
- Wires: scrape → DB filter → evaluate → notify

### Phase 7 — Scheduler (`scheduler.py`)
- `schedule` lib: `run_pipeline()` every configured day at configured hour
- Docker ENTRYPOINT

### Phase 8 — Docker
- `Dockerfile`: Python 3.12-slim + Playwright Chromium + pip deps
- Volume mount `./data:/app/data`
- `README.md`: full setup + transfer guide

---

## Machine Transfer (Portable Docker Image)

### Save on this computer
```bash
docker build -t afdb-tracker .
docker save afdb-tracker | gzip > afdb-tracker.tar.gz
```

### Load on new computer (only Docker needed)
```bash
docker load < afdb-tracker.tar.gz
# Copy your .env and data/ folder too, then:
docker run -d --env-file .env -v ./data:/app/data --name afdb-tracker afdb-tracker
```

---

## Key Reference Docs
- [Gmail App Passwords](https://support.google.com/accounts/answer/185833)
- [Google Gemini API free tier](https://ai.google.dev/gemini-api/docs/models/gemini)
- [Get Gemini API key](https://aistudio.google.com/app/apikey)
- [Playwright Python docs](https://playwright.dev/python/docs/intro)
- [Python `schedule` library](https://schedule.readthedocs.io/)
- [DuckDB Python docs](https://duckdb.org/docs/api/python/overview)
