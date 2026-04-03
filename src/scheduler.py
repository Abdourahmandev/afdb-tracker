"""
scheduler.py — Docker ENTRYPOINT.

Reads RUN_DAY and RUN_HOUR from environment, then schedules the pipeline
to run once a week at that time. Runs indefinitely.

Default: every Monday at 08:00 UTC.
"""

import logging
import os
import time

import schedule

from main import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")

RUN_DAY_MAP = {
    "monday":    schedule.every().monday,
    "tuesday":   schedule.every().tuesday,
    "wednesday": schedule.every().wednesday,
    "thursday":  schedule.every().thursday,
    "friday":    schedule.every().friday,
    "saturday":  schedule.every().saturday,
    "sunday":    schedule.every().sunday,
}


def main() -> None:
    run_day = os.environ.get("RUN_DAY", "monday").lower().strip()
    run_hour = os.environ.get("RUN_HOUR", "08").zfill(2)
    run_time = f"{run_hour}:00"

    day_scheduler = RUN_DAY_MAP.get(run_day)
    if day_scheduler is None:
        logger.error(
            "Invalid RUN_DAY='%s'. Choose from: %s",
            run_day, ", ".join(RUN_DAY_MAP.keys()),
        )
        raise SystemExit(1)

    day_scheduler.at(run_time).do(run_pipeline)

    logger.info(
        "Scheduler started — pipeline will run every %s at %s UTC.",
        run_day.capitalize(), run_time,
    )
    logger.info("Tip: set RUN_NOW=1 to trigger an immediate run on startup.")

    # Optional: run immediately on startup for testing
    if os.environ.get("RUN_NOW", "").strip() == "1":
        logger.info("RUN_NOW=1 detected — running pipeline immediately.")
        run_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
