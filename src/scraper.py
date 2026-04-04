"""
scraper.py — Playwright-based scraper for the AfDB SAP Fieldglass job board.

Flow:
1. Open the search page and submit keyword "data"
2. Paginate through all result pages, collecting (job_id, title, url) per listing
3. For each job_id provided as new: open the detail page and scrape full details
4. Return a list of job dicts
"""

import json
import logging
import re
from pathlib import Path
from typing import Generator

from playwright.sync_api import Page, sync_playwright

SEARCH_URL = "https://afdb1.fcp.eu.fieldglass.cloud.sap/job_search_basic.do"
BASE_URL = "https://afdb1.fcp.eu.fieldglass.cloud.sap"
SEARCH_KEYWORD = "data"

logger = logging.getLogger(__name__)


def scrape_job_listings(known_job_ids: set[str]) -> list[dict]:
    """
    Scrape all 'data' job listings from AfDB and return full details
    for jobs not in known_job_ids.
    """
    results: list[dict] = []

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
            listing_stubs = list(_collect_all_listings(page))
            logger.info("Found %d total listings for keyword '%s'", len(listing_stubs), SEARCH_KEYWORD)

            new_stubs = [s for s in listing_stubs if s["job_id"] not in known_job_ids]
            logger.info("%d new jobs to scrape", len(new_stubs))

            for stub in new_stubs:
                try:
                    detail = _scrape_detail(page, stub)
                    results.append(detail)
                    logger.info("Scraped: [%s] %s", detail["job_id"], detail["title"])
                except Exception as exc:
                    logger.warning("Failed to scrape detail for %s: %s", stub["url"], exc)

        finally:
            browser.close()

    return results


def _collect_all_listings(page: Page) -> Generator[dict, None, None]:
    """Submit search and extract all job stubs by parsing the embedded JS data object."""
    logger.info("Loading search page: %s", SEARCH_URL)
    page.goto(SEARCH_URL, wait_until="load", timeout=60_000)
    page.wait_for_timeout(3_000)

    # Fill keyword and submit
    keyword_input = page.locator("input[name='what'], input[type='text']").first
    keyword_input.wait_for(state="visible", timeout=30_000)
    keyword_input.fill(SEARCH_KEYWORD)
    logger.info("Filled keyword: %s", SEARCH_KEYWORD)

    page.locator("input.btn[value='Search'], button.btn:has-text('Search'), input[value='Search']").first.click()
    logger.info("Submitted search.")

    # Wait for results to appear
    try:
        page.wait_for_selector("a.archiveLink", timeout=30_000)
        logger.info("Results loaded.")
    except Exception:
        logger.warning("Timed out waiting for a.archiveLink — no results or slow page.")
        return

    page.wait_for_timeout(1_000)

    # ── Strategy 1: extract ALL results directly from the browser JS context ──
    rows = _extract_rows_from_js(page)
    if rows:
        logger.info("Extracted %d rows from embedded JS data.", len(rows))
        yield from rows
        return

    # ── Strategy 2: fallback — paginate through a.archiveLink elements ────────
    logger.info("JS extraction failed — falling back to pagination.")
    yield from _paginate_archivelinks(page)


def _extract_rows_from_js(page: Page) -> list[dict]:
    """
    SAP Fieldglass stores ALL search results in a window-level JS object whose
    name starts with 'jsonObject_search_result_positions_list1_'.
    We ask the browser to find and return that object directly — no regex needed.
    """
    try:
        raw = page.evaluate("""() => {
            for (const key of Object.keys(window)) {
                if (key.startsWith('jsonObject_search_result_positions_list1_')) {
                    return JSON.stringify(window[key]);
                }
            }
            return null;
        }""")
    except Exception as exc:
        logger.debug("page.evaluate failed: %s", exc)
        return []

    if not raw:
        logger.debug("JS object not found on window — key may differ.")
        return []

    try:
        obj = json.loads(raw)
    except Exception as exc:
        logger.debug("JSON parse error: %s", exc)
        return []

    raw_rows = obj.get("rows", [])
    results = []
    for row in raw_rows:
        columns = {col["name"]: col for col in row.get("columns", [])}
        ref_col = columns.get("job_posting_ref", {})
        job_id = ref_col.get("value", "")
        if not job_id:
            continue

        # Extract URL from the HTML field of job_posting_ref
        href_match = re.search(r'href\s*[=\\]+\s*["\\/]([^"\\>]+)', ref_col.get("html", ""))
        url = ""
        if href_match:
            raw_href = href_match.group(1).replace("\\u003d", "=").replace("\\u0026", "&").replace("\\/", "/")
            url = BASE_URL + "/" + raw_href.lstrip("/") if not raw_href.startswith("http") else raw_href

        results.append({
            "job_id":        job_id,
            "title":         columns.get("title", {}).get("value", ""),
            "location":      columns.get("location", {}).get("value", ""),
            "contract_type": columns.get("job_type_text", {}).get("value", ""),
            "deadline":      columns.get("end_date", {}).get("value", ""),
            "url":           url,
        })

    return results


def _paginate_archivelinks(page: Page) -> Generator[dict, None, None]:
    """Fallback: paginate through a.archiveLink elements page by page."""
    while True:
        links = page.locator("a.archiveLink").all()
        logger.info("Page has %d archiveLink elements.", len(links))
        for link in links:
            href = link.get_attribute("href") or ""
            full_url = href if href.startswith("http") else BASE_URL + href
            job_id = link.inner_text().strip()
            if not job_id:
                continue

            title = ""
            location = ""
            contract_type = ""
            deadline = ""
            try:
                row = link.locator("xpath=ancestor::tr").first
                tds = row.locator("td").all()
                if len(tds) > 1:
                    title = tds[1].inner_text().strip()
                if len(tds) > 2:
                    location = tds[2].inner_text().strip()
                if len(tds) > 4:
                    contract_type = tds[4].inner_text().strip()
                if len(tds) > 7:
                    deadline = tds[7].inner_text().strip()
            except Exception:
                pass

            yield {
                "job_id": job_id, "title": title, "url": full_url,
                "location": location, "contract_type": contract_type, "deadline": deadline,
            }

        # Next page — look for the pager ► button
        next_btn = page.locator(
            "a[title='Next'], span.pagerNextButton a, td.pagerNextButton, "
            "a:has-text('>'), button:has-text('Next')"
        ).first
        if next_btn.count() == 0 or not next_btn.is_visible():
            break
        try:
            next_btn.click()
            page.wait_for_selector("a.archiveLink", timeout=15_000)
            page.wait_for_timeout(1_500)
        except Exception as exc:
            logger.warning("Failed to navigate to next page: %s", exc)
            break


def _scrape_detail(page: Page, stub: dict) -> dict:
    """Open a job detail page and extract the full description."""
    logger.info("Scraping detail: %s", stub["url"])
    page.goto(stub["url"], wait_until="load", timeout=60_000)
    page.wait_for_timeout(3_000)

    def _text(selector: str) -> str:
        el = page.locator(selector).first
        return el.inner_text().strip() if el.count() > 0 and el.is_visible() else ""

    # Get full description — try common Fieldglass selectors, fallback to body
    description_raw = (
        _text(".jobDescription")
        or _text(".job-description")
        or _text("#jobDescription")
        or _text("div.description")
        or _text("td.detailsRight")
        or page.locator("body").inner_text()[:8000]
    )

    return {
        "job_id":          stub["job_id"],
        "title":           stub.get("title", ""),
        "location":        stub.get("location", ""),
        "contract_type":   stub.get("contract_type", ""),
        "deadline":        stub.get("deadline", ""),
        "description_raw": description_raw,
        "url":             stub["url"],
    }
