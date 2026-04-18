"""
AfDB-Platform pluggable scraper system.

Usage:
    from scrapers import load_enabled_scrapers

    scrapers = load_enabled_scrapers()
    for scraper in scrapers:
        jobs = await scraper.scrape(known_ids=existing_job_ids)
"""
import importlib
from pathlib import Path

import yaml

from scrapers.base import BaseScraper, JobRecord

__all__ = ["BaseScraper", "JobRecord", "load_enabled_scrapers"]

_SOURCES_CONFIG = Path(__file__).parent / "config" / "sources.yaml"


def load_enabled_scrapers() -> list[BaseScraper]:
    """Load and instantiate all enabled scrapers from sources.yaml."""
    with open(_SOURCES_CONFIG) as f:
        config = yaml.safe_load(f)

    scrapers: list[BaseScraper] = []
    for source_id, source_config in config.get("sources", {}).items():
        if not source_config.get("enabled", False):
            continue

        scraper_class_path: str = source_config["scraper_class"]
        module_path, class_name = scraper_class_path.rsplit(".", 1)

        try:
            module = importlib.import_module(module_path)
            scraper_cls: type[BaseScraper] = getattr(module, class_name)
            scrapers.append(scraper_cls(config=source_config))
        except (ImportError, AttributeError) as e:
            print(f"[scrapers] WARNING: Could not load scraper for '{source_id}': {e}")

    return scrapers
