"""
main.py — Pipeline orchestrator.

Steps:
  1. Init DB
  2. Scrape AfDB for "data" jobs, skip already-seen job_ids
  3. Insert new jobs into DB
  4. Evaluate each new job with Gemini
  5. Insert evaluation; send email if score >= threshold
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from dotenv import load_dotenv

# Load .env from the project root (one level up from src/) — no-op in Docker
load_dotenv(Path(__file__).parent.parent / ".env")

from db import (init_db, insert_evaluation, insert_job,
                get_unevaluated_jobs, get_unemailed_jobs, mark_email_sent,
                insert_run_history)
from evaluator import evaluate_job
from notifier import send_alert
from report_generator import generate_report
from scraper import scrape_job_listings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def _get_known_job_ids() -> set[str]:
    """Return the set of job_ids already in the database."""
    from pathlib import Path
    import duckdb as _ddb

    db_path = Path(os.environ.get("DATA_DIR", "/app/data")) / "jobs.duckdb"
    if not db_path.exists():
        return set()
    con = _ddb.connect(db_path)
    rows = con.execute("SELECT job_id FROM jobs").fetchall()
    con.close()
    return {row[0] for row in rows}


def run_pipeline() -> None:
    start = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("AfDB Job Tracker — pipeline started at %s", start.isoformat())
    logger.info("=" * 60)

    score_threshold = int(os.environ.get("SCORE_THRESHOLD", "7"))

    # ── Step 1: ensure DB tables exist ──────────────────────────────────────
    init_db()
    logger.info("Database initialised.")

    # ── Step 2: scrape ───────────────────────────────────────────────────────
    known_ids = _get_known_job_ids()
    logger.info("Known job IDs in DB: %d", len(known_ids))

    new_jobs = scrape_job_listings(known_job_ids=known_ids)
    new_jobs_count = len(new_jobs)
    total_db_jobs  = len(known_ids) + new_jobs_count
    logger.info("New jobs scraped this run: %d", new_jobs_count)

    if not new_jobs:
        logger.info("No new jobs found from scraper.")

    # ── Step 3: insert ALL new jobs into DB before evaluating any of them ───
    # This ensures jobs are never lost even if evaluation quota is exhausted.
    for job in new_jobs:
        insert_job(job)
        logger.info("Inserted job: [%s] %s", job["job_id"], job.get("title"))

    # Also pick up any jobs scraped in a previous run that failed evaluation
    unevaluated = get_unevaluated_jobs()
    if unevaluated:
        logger.info("%d previously scraped jobs still need evaluation.", len(unevaluated))

    jobs_to_evaluate = unevaluated  # already contains the new jobs we just inserted

    # ── Steps 4–5: evaluate and notify ──────────────────────────────────────
    emails_sent = 0
    evaluated_count = 0
    best_score = 0
    best_job_id = ""

    if not jobs_to_evaluate:
        logger.info("Nothing new to evaluate.")
    else:
        for job in jobs_to_evaluate:
            job_id = job["job_id"]

            # Evaluate
            try:
                result = evaluate_job(job)
                score = result["score"]
                summary = result["summary"]
                logger.info("Job %s scored %d/10", job_id, score)
                evaluated_count += 1
                if score > best_score:
                    best_score = score
                    best_job_id = job_id
            except RuntimeError as exc:
                exc_str = str(exc)
                if "daily quota exhausted" in exc_str.lower():
                    logger.warning(
                        "Gemini daily quota exhausted — stopping evaluations for this run. "
                        "%d jobs remain in DB and will be evaluated on the next run.",
                        len(jobs_to_evaluate) - evaluated_count,
                    )
                    break  # exit the loop — no point continuing
                logger.error("Evaluation failed for job %s: %s", job_id, exc)
                continue  # leave unevaluated so next run retries
            except Exception as exc:
                logger.error("Unexpected evaluation error for job %s: %s", job_id, exc)
                continue

            # Notify if score meets threshold
            email_sent = False
            if score >= score_threshold:
                try:
                    send_alert(job, score, summary)
                    email_sent = True
                    emails_sent += 1
                except Exception as exc:
                    logger.error("Failed to send email for job %s: %s", job_id, exc)

            insert_evaluation(job_id, score=score, summary=summary, email_sent=email_sent)

    # ── Step 6: send any pending emails (evaluated but not yet emailed) ─────
    # This catches jobs scored in a previous run where SMTP failed.
    pending = get_unemailed_jobs(score_threshold)
    if pending:
        logger.info("%d evaluated job(s) still need email alerts.", len(pending))
    for job in pending:
        job_id = job["job_id"]
        score = job["score"]
        summary = job["summary"]
        try:
            send_alert(job, score, summary)
            mark_email_sent(job_id)
            emails_sent += 1
            logger.info("Sent pending alert for job %s (score %d/10)", job_id, score)
        except Exception as exc:
            logger.error("Failed to send pending email for job %s: %s", job_id, exc)
            break  # if SMTP is broken, no point continuing

    end = datetime.now(timezone.utc)
    duration = (end - start).total_seconds()
    logger.info(
        "Pipeline finished in %.1fs — %d job(s) evaluated, %d email(s) sent.",
        duration, evaluated_count, emails_sent,
    )
    # ── Log run + regenerate report ──────────────────────────────────────────
    trigger = "manual" if os.environ.get("RUN_NOW") else "scheduled"
    notes = ""
    if new_jobs_count > 0 and best_score > 0:
        notes = f"{new_jobs_count} new job(s); best: {best_job_id} ({best_score}/10)"
    elif new_jobs_count > 0:
        notes = f"{new_jobs_count} new job(s) found"

    try:
        insert_run_history(
            trigger=trigger,
            jobs_in_db=total_db_jobs,
            new_jobs=new_jobs_count,
            evaluated=evaluated_count,
            emails_sent=emails_sent,
            duration_s=duration,
            status="ok",
            notes=notes,
        )
    except Exception as exc:
        logger.error("Failed to log run history: %s", exc)

    try:
        report_path = generate_report()
        logger.info("Report generated: %s", report_path)
    except Exception as exc:
        logger.error("Failed to generate report: %s", exc)

LEGACY_MODE = os.environ.get("LEGACY_MODE", "true").lower() == "true"


def run() -> None:
    """Entry point that respects LEGACY_MODE. Called by scheduler.py."""
    if LEGACY_MODE:
        run_pipeline()
    else:
        from pipeline_v2 import run_pipeline_v2
        run_pipeline_v2()


if __name__ == "__main__":
    run()
