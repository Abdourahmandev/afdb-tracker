"""
scripts/backfill_empty_jobs.py
──────────────────────────────────────────────────────────────────────────────
Re-scrapes title / location / contract_type / deadline for AfDB jobs that
were imported into Cosmos DB with empty metadata fields.

These jobs existed in DuckDB with a valid job_id and URL but empty title /
location (the SAP Fieldglass listing returned blank fields at scrape time).
This script:
  1. Queries Cosmos DB for all AfDB jobs missing a title.
  2. Re-runs the existing search-page scraper to get current listing data.
  3. For every matched job, also visits the detail page to grab description_raw.
  4. Patches the Cosmos DB document with the recovered fields.

Usage
─────
# Set your Cosmos DB connection first:
export COSMOS_CONNECTION_STRING="AccountEndpoint=https://..."

# Then run:
python scripts/backfill_empty_jobs.py
python scripts/backfill_empty_jobs.py --dry-run   # preview only
"""

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_empty_jobs() -> list[dict]:
    """Return AfDB jobs in Cosmos that have an empty title."""
    import cosmos_db
    container = cosmos_db._jobs()
    results = list(container.query_items(
        query="SELECT * FROM c WHERE c.source_id = 'afdb' AND (c.title = '' OR NOT IS_DEFINED(c.title))",
        enable_cross_partition_query=True,
    ))
    return results


def scrape_listing_data() -> dict[str, dict]:
    """
    Run the AfDB search scraper listing phase (no detail pages) and return
    a dict keyed by job_id with fields: title, location, contract_type, deadline, url.
    """
    from scraper import _collect_all_listings
    from playwright.sync_api import sync_playwright

    stubs: dict[str, dict] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        try:
            for stub in _collect_all_listings(page):
                jid = stub.get("job_id", "")
                if jid:
                    stubs[jid] = stub
            logger.info("Listing phase: found %d job stubs", len(stubs))
        finally:
            browser.close()
    return stubs


def scrape_detail(url: str, stub: dict) -> str:
    """Visit a detail page and return description_raw."""
    from scraper import _scrape_detail
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        try:
            detail = _scrape_detail(page, {**stub, "url": url})
            return detail.get("description_raw", "")
        except Exception as e:
            logger.warning("Detail scrape failed for %s: %s", url, e)
            return ""
        finally:
            browser.close()


def patch_job(doc: dict, stub: dict, description_raw: str, dry_run: bool) -> bool:
    """Patch a Cosmos DB job document with recovered fields. Returns True if updated."""
    import cosmos_db

    updated = dict(doc)
    changed = False

    for field in ("title", "location", "contract_type", "deadline"):
        new_val = stub.get(field, "").strip()
        # Reject titles that look like "JOB_ID\nClosed Job" from expired postings
        if field == "title" and (
            "Closed Job" in new_val or new_val.startswith("AFDB1JP")
        ):
            logger.info("  Skipping bad title for %s: %r", doc["job_id"], new_val[:60])
            continue
        if new_val and not doc.get(field, "").strip():
            updated[field] = new_val
            changed = True

    if description_raw and not doc.get("description_raw", "").strip():
        updated["description_raw"] = description_raw
        changed = True

    if not changed:
        logger.info("  [SKIP] %s — no new data found in listing", doc["job_id"])
        return False

    if dry_run:
        print(f"  [DRY-RUN] would patch {doc['job_id']}:")
        for field in ("title", "location", "contract_type", "deadline"):
            if updated.get(field) != doc.get(field):
                print(f"    {field}: {doc.get(field)!r} -> {updated[field]!r}")
        return True

    cosmos_db._jobs().upsert_item(body=updated)
    logger.info("  Patched %s: title=%r", doc["job_id"], updated.get("title"))
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Backfill empty title/location for AfDB jobs in Cosmos DB."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be updated without writing")
    args = parser.parse_args()

    # -- Step 1: find empty jobs ------------------------------------------
    logger.info("Querying Cosmos DB for AfDB jobs with empty title...")
    empty_jobs = get_empty_jobs()
    if not empty_jobs:
        print("No empty jobs found — nothing to do.")
        return

    print(f"Found {len(empty_jobs)} job(s) with empty title:")
    for j in empty_jobs:
        print(f"  {j['job_id']} | {j.get('url', '')[:70]}")

    if args.dry_run:
        print("\n*** DRY RUN — nothing will be written to Cosmos DB ***\n")

    # -- Step 2: re-scrape the search listing to get current metadata -------
    print("\nRe-running AfDB search listing to recover metadata...")
    listing_stubs = scrape_listing_data()

    # -- Step 3: patch each empty job ---------------------------------------
    print("\nPatching jobs:")
    patched = 0
    not_in_listing = []

    for doc in empty_jobs:
        jid = doc["job_id"]
        stub = listing_stubs.get(jid)

        if not stub:
            logger.info("  %s not found in current listing — scraping detail page", jid)
            not_in_listing.append(doc)
            continue

        # Also fetch description if it's empty
        description_raw = ""
        if not doc.get("description_raw", "").strip() and doc.get("url"):
            logger.info("  Fetching detail for %s...", jid)
            description_raw = scrape_detail(doc["url"], stub)

        if patch_job(doc, stub, description_raw, args.dry_run):
            patched += 1

    # -- Step 4: for jobs not in listing, try detail page directly ----------
    for doc in not_in_listing:
        jid = doc["job_id"]
        url = doc.get("url", "")
        if not url:
            logger.warning("  %s has no URL — skipping", jid)
            continue

        logger.info("  Scraping detail page for %s (not in listing)...", jid)
        # Build a minimal stub from the detail page title tag
        description_raw = ""
        stub_from_detail: dict = {}

        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True,
                                         args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ))
            page = browser.new_page()
            try:
                page.goto(url, wait_until="load", timeout=60_000)
                page.wait_for_timeout(3_000)

                # Try to get the title from the page
                def _text(sel):
                    el = page.locator(sel).first
                    return el.inner_text().strip() if el.count() > 0 and el.is_visible() else ""

                title = (
                    _text("h1.jobTitle") or _text("h1") or
                    _text(".jobTitle") or _text("td.detailsHeader") or
                    page.title().replace(" - SAP Fieldglass", "").strip()
                )
                location = _text(".jobLocation") or _text("td.location") or ""
                contract_type = _text(".jobType") or _text("td.contractType") or ""
                deadline = _text(".endDate") or _text("td.deadline") or ""
                description_raw = (
                    _text(".jobDescription") or _text(".job-description") or
                    _text("#jobDescription") or _text("div.description") or
                    _text("td.detailsRight") or page.locator("body").inner_text()[:8000]
                )

                stub_from_detail = {
                    "title":         title,
                    "location":      location,
                    "contract_type": contract_type,
                    "deadline":      deadline,
                }
            except Exception as e:
                logger.warning("  Detail scrape failed for %s: %s", jid, e)
            finally:
                browser.close()

        if patch_job(doc, stub_from_detail, description_raw, args.dry_run):
            patched += 1
        else:
            logger.info("  %s — could not recover any fields from detail page", jid)

    # -- Summary ------------------------------------------------------------
    action = "Would patch" if args.dry_run else "Patched"
    print(f"\n{action} {patched} / {len(empty_jobs)} jobs.")
    if patched < len(empty_jobs):
        print(
            "Jobs that could not be recovered may have been removed from the AfDB website."
        )


if __name__ == "__main__":
    main()
