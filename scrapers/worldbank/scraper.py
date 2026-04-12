"""
World Bank Group job scraper — PLACEHOLDER

TODO (Sprint 1+):
  1. Confirm the correct World Bank careers portal URL
  2. Implement scrape() using Playwright or the public API if one exists
  3. Set enabled: true in scrapers/config/sources.yaml
"""
from scrapers.base import BaseScraper, JobRecord


class WorldBankScraper(BaseScraper):
    source_id = "worldbank"
    display_name = "World Bank Group"

    async def scrape(self, known_ids: set[str]) -> list[JobRecord]:
        raise NotImplementedError("WorldBankScraper is not yet implemented.")
