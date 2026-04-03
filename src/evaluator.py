"""
evaluator.py — Score a job posting against the user's profile using Google Gemini.

Returns a dict: {score: int (1-10), summary: str}
"""

import json
import logging
import os
import re
import time
from pathlib import Path

from google import genai

PROFILE_PATH = Path(os.environ.get("PROFILE_PATH", "/app/profile.md"))
MODEL_NAME = "gemini-2.5-flash"
MAX_RETRIES = 3
RATELIMIT_DELAY = 2    # seconds between every call
RETRY_DELAY = 65       # seconds after a 429 — waits for the 1-min window to reset

logger = logging.getLogger(__name__)

_profile_cache: str | None = None
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        _client = genai.Client(api_key=api_key)
    return _client


def _load_profile() -> str:
    global _profile_cache
    if _profile_cache is None:
        if not PROFILE_PATH.exists():
            raise FileNotFoundError(
                f"profile.md not found at {PROFILE_PATH}. "
                "Please fill in your profile before running the pipeline."
            )
        _profile_cache = PROFILE_PATH.read_text(encoding="utf-8")
    return _profile_cache


def _build_prompt(job: dict, profile: str) -> str:
    job_text = (
        f"Title: {job.get('title', 'N/A')}\n"
        f"Location: {job.get('location', 'N/A')}\n"
        f"Contract Type: {job.get('contract_type', 'N/A')}\n"
        f"Application Deadline: {job.get('deadline', 'N/A')}\n"
        f"URL: {job.get('url', 'N/A')}\n\n"
        f"Full Description:\n{job.get('description_raw', '')[:6000]}"
    )

    return f"""You are a career advisor helping a professional find the best job matches.

## Candidate Profile
{profile}

## Job Posting
{job_text}

## Task
Do two things:
1. Score how well this job matches the candidate's profile (1-10).
2. Write a concise job overview covering these points (use "Not mentioned" if info is absent):
   - What the role involves (1-2 sentences)
   - Remote / on-site / hybrid: explicitly state which
   - Travel required: yes/no and how much if mentioned
   - Key skills or qualifications required
   - Contract duration if mentioned

Respond ONLY with a valid JSON object in this exact format (no markdown, no extra text):
{{
  "score": <integer from 1 to 10>,
  "summary": "<structured overview covering the 5 points above, written in plain prose, 4-6 sentences>"
}}

Scoring guide:
- 9-10: Excellent match, candidate should definitely apply
- 7-8: Good match, worth applying
- 5-6: Partial match, missing some key requirements
- 3-4: Weak match, significant gaps
- 1-2: Poor match, not relevant
"""


def evaluate_job(job: dict) -> dict:
    """
    Evaluate a job against profile.md using Gemini.
    Returns {score: int, summary: str} or raises on persistent failure.
    """
    client = _get_client()
    profile = _load_profile()
    prompt = _build_prompt(job, profile)

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(RATELIMIT_DELAY)  # proactive pacing
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
            )
            raw = response.text.strip()

            # Strip markdown code fences if present
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            parsed = json.loads(raw)
            score = int(parsed["score"])
            summary = str(parsed["summary"])

            if not (1 <= score <= 10):
                raise ValueError(f"Score out of range: {score}")

            return {"score": score, "summary": summary}

        except Exception as exc:
            last_error = exc
            exc_str = str(exc)
            is_daily_quota = "PerDay" in exc_str or "per_day" in exc_str.lower()
            is_quota = "429" in exc_str or "quota" in exc_str.lower() or "rate" in exc_str.lower()

            if is_daily_quota:
                # Daily quota is exhausted — no point retrying further or continuing this run.
                # Jobs are already in the DB; next scheduled run will pick them up.
                raise RuntimeError(
                    f"Gemini daily quota exhausted for job {job.get('job_id')}. "
                    "Evaluations will resume on the next pipeline run."
                ) from exc

            wait = RETRY_DELAY if is_quota else RATELIMIT_DELAY
            logger.warning(
                "Gemini evaluation attempt %d/%d failed for job %s: %s",
                attempt, MAX_RETRIES, job.get("job_id"), exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(wait)

    raise RuntimeError(
        f"Gemini evaluation failed after {MAX_RETRIES} attempts for job {job.get('job_id')}: {last_error}"
    )
