"""
pipeline_v2.py — Multi-tenant pipeline orchestrator.

Runs when LEGACY_MODE=false (default for new deployments).
Legacy DuckDB pipeline remains in main.py and is called when LEGACY_MODE=true.

Flow:
  1. Load enabled scrapers from scrapers/config/sources.yaml
  2. For each scraper: fetch known IDs from Cosmos DB → scrape new jobs → upsert
  3. Load all active users from Cosmos DB
  4. For each user: find unevaluated jobs from their enabled sources
  5. For each (user, job): score with Gemini → upsert evaluation
  6. For each user: send digest email for jobs ≥ their score_threshold
"""
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing legacy src/ modules (scraper, evaluator, etc.)
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import cosmos_db
from evaluator_v2 import evaluate_job_for_user
from notifier_v2 import send_digest

# scrapers/ is one level above src/
sys.path.insert(0, str(Path(__file__).parent.parent))
from scrapers import load_enabled_scrapers
from scrapers.base import JobRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pipeline_v2")


def _scrape_all_sources() -> dict[str, list[dict]]:
    """
    Run all enabled scrapers and upsert new jobs to Cosmos DB.
    Returns {source_id: [new_job_dicts]} for logging.
    """
    scrapers = load_enabled_scrapers()
    if not scrapers:
        logger.warning("No enabled scrapers found in sources.yaml")
        return {}

    new_by_source: dict[str, list[dict]] = {}

    for scraper in scrapers:
        source_id = scraper.source_id
        logger.info("=== Scraping source: %s ===", scraper.display_name)

        known_ids = cosmos_db.get_known_job_ids(source_id)
        logger.info("  Known IDs in Cosmos DB for %s: %d", source_id, len(known_ids))

        try:
            # Scrapers are async; run them synchronously via asyncio
            import asyncio
            records: list[JobRecord] = asyncio.run(scraper.scrape(known_ids))
        except NotImplementedError:
            logger.info("  Scraper for %s is a placeholder — skipping.", source_id)
            continue
        except Exception as exc:
            logger.error("  Scraper %s failed: %s", source_id, exc)
            continue

        logger.info("  New jobs from %s: %d", source_id, len(records))
        new_jobs: list[dict] = []

        for record in records:
            job_dict = record.to_dict()
            cosmos_db.upsert_job(job_dict)
            new_jobs.append(job_dict)
            logger.info("  Upserted: [%s] %s", record.job_id, record.title)

        new_by_source[source_id] = new_jobs

    return new_by_source


def _evaluate_and_notify_users() -> tuple[int, int]:
    """
    For each active user, evaluate unevaluated jobs and send digest emails.
    Returns (total_evaluations, total_emails_sent).
    """
    users = cosmos_db.get_all_active_users()
    if not users:
        logger.info("No active users found.")
        return 0, 0

    logger.info("Active users: %d", len(users))
    total_evals = 0
    total_emails = 0

    for user in users:
        user_id = user.get("id") or user.get("user_id", "")
        score_threshold = int(user.get("score_threshold", os.environ.get("SCORE_THRESHOLD", "7")))
        enabled_sources: list[str] = user.get("enabled_sources", ["afdb"])

        logger.info("Processing user: %s (sources: %s, threshold: %d)",
                    user_id, enabled_sources, score_threshold)

        # Get all jobs for this user's enabled sources
        all_jobs = cosmos_db.get_jobs_for_sources(enabled_sources)
        if not all_jobs:
            logger.info("  No jobs found for sources %s", enabled_sources)
            continue

        # Filter out already-evaluated jobs
        evaluated_ids = cosmos_db.get_evaluated_job_ids_for_user(user_id)
        jobs_to_evaluate = [j for j in all_jobs if j["job_id"] not in evaluated_ids]
        logger.info(
            "  Jobs to evaluate: %d (skipping %d already evaluated)",
            len(jobs_to_evaluate), len(evaluated_ids),
        )

        # Evaluate each new job
        for job in jobs_to_evaluate:
            try:
                result = evaluate_job_for_user(job, user)
                score = result["score"]
                summary = result["summary"]
                logger.info("  Scored job %s: %d/10", job["job_id"], score)
                total_evals += 1
            except RuntimeError as exc:
                if "daily quota exhausted" in str(exc).lower():
                    logger.warning("  Gemini daily quota exhausted — stopping evaluations.")
                    break
                logger.error("  Evaluation failed for job %s: %s", job.get("job_id"), exc)
                continue
            except Exception as exc:
                logger.error("  Unexpected error for job %s: %s", job.get("job_id"), exc)
                continue

            cosmos_db.upsert_evaluation(
                user_id=user_id,
                job_id=job["job_id"],
                source_id=job.get("source_id", ""),
                score=score,
                summary=summary,
                email_sent=False,
            )

        # Send digest email for all unemailed matches (including previous runs)
        unemailed = cosmos_db.get_unemailed_evaluations_for_user(user_id, score_threshold)
        if not unemailed:
            logger.info("  No new email-worthy matches for %s", user_id)
            continue

        # Build (job, score, summary) tuples by fetching jobs from Cosmos DB
        job_lookup = {j["job_id"]: j for j in all_jobs}
        matches: list[tuple[dict, int, str]] = []
        for ev in unemailed:
            job = job_lookup.get(ev["job_id"])
            if job:
                matches.append((job, ev["score"], ev["summary"]))

        matches.sort(key=lambda x: x[1], reverse=True)  # sort by score DESC

        try:
            send_digest(user, matches)
            total_emails += 1
            # Mark all as emailed
            for ev in unemailed:
                cosmos_db.mark_evaluation_email_sent(user_id, ev["job_id"])
        except Exception as exc:
            logger.error("  Failed to send digest to %s: %s", user_id, exc)

    return total_evals, total_emails


def run_pipeline_v2() -> None:
    start = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("AfDB-Platform v2 pipeline started at %s", start.isoformat())
    logger.info("=" * 60)

    # Step 1: Scrape all enabled sources
    logger.info("--- Phase 1: Scraping ---")
    new_by_source = _scrape_all_sources()
    total_new = sum(len(v) for v in new_by_source.values())
    logger.info("Total new jobs scraped across all sources: %d", total_new)

    # Step 2: Evaluate and notify users
    logger.info("--- Phase 2: Evaluate & Notify ---")
    total_evals, total_emails = _evaluate_and_notify_users()

    duration = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info(
        "Pipeline v2 complete in %.1fs — %d new job(s), %d evaluation(s), %d email(s) sent.",
        duration, total_new, total_evals, total_emails,
    )


if __name__ == "__main__":
    run_pipeline_v2()
