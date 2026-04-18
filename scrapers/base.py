"""
Base scraper interface for AfDB-Platform pluggable scraper system.
Every job source must implement this class.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class JobRecord:
    """Normalized job record returned by every scraper."""
    job_id: str           # Source-scoped unique ID (e.g. "VAC-001")
    source_id: str        # Source identifier (e.g. "afdb", "worldbank")
    title: str
    location: str
    contract_type: str
    deadline: str         # ISO 8601 date string or empty
    description_raw: str
    url: str
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    extra: dict[str, Any] = field(default_factory=dict)  # Source-specific extra fields

    @property
    def cosmos_id(self) -> str:
        """Composite Cosmos DB document ID: source_id|job_id."""
        return f"{self.source_id}|{self.job_id}"

    def to_dict(self) -> dict:
        return {
            "id": self.cosmos_id,
            "job_id": self.job_id,
            "source_id": self.source_id,
            "title": self.title,
            "location": self.location,
            "contract_type": self.contract_type,
            "deadline": self.deadline,
            "description_raw": self.description_raw,
            "url": self.url,
            "scraped_at": self.scraped_at,
            **self.extra,
        }


class BaseScraper(ABC):
    """
    Abstract base class for all job source scrapers.

    To add a new source:
    1. Create scrapers/{source_id}/scraper.py
    2. Subclass BaseScraper and implement scrape()
    3. Set source_id and display_name class attributes
    4. Enable the source in scrapers/config/sources.yaml
    """

    source_id: str = ""           # e.g. "afdb", "worldbank"
    display_name: str = ""        # e.g. "African Development Bank"

    def __init__(self, config: dict):
        """
        Args:
            config: Source config dict from sources.yaml (rate_limit_seconds, etc.)
        """
        self.config = config
        self.rate_limit_seconds: float = config.get("rate_limit_seconds", 2.0)
        self.max_pages: int = config.get("max_pages", 10)
        self.user_agent: str = config.get(
            "user_agent", "AfDB-Platform-Tracker/1.0"
        )

    @abstractmethod
    async def scrape(self, known_ids: set[str]) -> list[JobRecord]:
        """
        Scrape new jobs from the source.

        Args:
            known_ids: Set of job_id strings already in the database.
                       Stop paginating early if all jobs on a page are known.

        Returns:
            List of JobRecord objects for NEW jobs only.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source_id={self.source_id!r}>"
