"""
AfDB (African Development Bank) scraper.
Wraps the existing src/scraper.py Playwright logic into the BaseScraper interface.

LEGACY NOTE: src/scraper.py remains unchanged and is used by the legacy DuckDB pipeline
when LEGACY_MODE=true. This file adapts it for the multi-tenant pipeline.
"""
import asyncio
import sys
from pathlib import Path

# Allow importing from legacy src/ when running as part of multi-tenant pipeline
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from scrapers.base import BaseScraper, JobRecord


class AfDBScraper(BaseScraper):
    source_id = "afdb"
    display_name = "African Development Bank (AfDB)"

    async def scrape(self, known_ids: set[str]) -> list[JobRecord]:
        """
        Delegate to the existing Playwright-based AfDB scraper (src/scraper.py).
        Adapts the returned list[dict] into list[JobRecord].
        """
        # Import legacy scraper (Playwright-based, synchronous)
        from scraper import scrape_job_listings  # type: ignore[import]

        # Run synchronous legacy scraper in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        raw_jobs: list[dict] = await loop.run_in_executor(
            None, scrape_job_listings, known_ids
        )

        return [self._adapt(job) for job in raw_jobs]

    def _adapt(self, raw: dict) -> JobRecord:
        """Convert legacy scraper dict to normalized JobRecord."""
        return JobRecord(
            job_id=str(raw.get("job_id", "")),
            source_id=self.source_id,
            title=raw.get("title", ""),
            location=raw.get("location", ""),
            contract_type=raw.get("contract_type", ""),
            deadline=str(raw.get("deadline", "")),
            description_raw=raw.get("description_raw", ""),
            url=raw.get("url", ""),
            scraped_at=str(raw.get("scraped_at", "")),
        )
