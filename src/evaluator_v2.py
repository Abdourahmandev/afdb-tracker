"""
evaluator_v2.py — Per-user Gemini job scoring for the multi-tenant pipeline.

Difference from evaluator.py: takes a user dict with profile_text instead
of reading a single profile.md file. Everything else is identical.
"""
import json
import logging
import os
import re
import time

from google import genai

MODEL_NAME = "gemini-2.5-flash"
MAX_RETRIES = 3
RATELIMIT_DELAY = 2
RETRY_DELAY = 65

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        _client = genai.Client(api_key=api_key)
    return _client


def _build_prompt(job: dict, profile_text: str) -> str:
    source_label = (job.get("source_id") or "").upper() or "Job Board"
    job_text = (
        f"Source: {source_label}\n"
        f"Title: {job.get('title', 'N/A')}\n"
        f"Location: {job.get('location', 'N/A')}\n"
        f"Contract Type: {job.get('contract_type', 'N/A')}\n"
        f"Application Deadline: {job.get('deadline', 'N/A')}\n"
        f"URL: {job.get('url', 'N/A')}\n\n"
        f"Full Description:\n{job.get('description_raw', '')[:6000]}"
    )
    return f"""You are a career advisor helping a professional find the best job matches.

## Candidate Profile
{profile_text}

## Job Posting
{job_text}

## Task
Do two things:
1. Score how well this job matches the candidate's profile (1-10).
2. Write a concise job overview covering these points (use "Not mentioned" if absent):
   - What the role involves (1-2 sentences)
   - Remote / on-site / hybrid: explicitly state which
   - Travel required: yes/no and how much if mentioned
   - Key skills or qualifications required
   - Contract duration if mentioned

Respond ONLY with a valid JSON object (no markdown, no extra text):
{{
  "score": <integer from 1 to 10>,
  "summary": "<structured overview, 4-6 sentences>"
}}

Scoring guide:
- 9-10: Excellent match — should definitely apply
- 7-8: Good match — worth applying
- 5-6: Partial match — missing some requirements
- 3-4: Weak match — significant gaps
- 1-2: Poor match — not relevant
"""


def evaluate_job_for_user(job: dict, user: dict) -> dict:
    """
    Score a job against a specific user's profile.

    Args:
        job:  Job document (title, description_raw, source_id, etc.)
        user: User document (profile_text, id, email, score_threshold, etc.)

    Returns:
        {"score": int, "summary": str}

    Raises:
        RuntimeError: after MAX_RETRIES failures or on daily quota exhaustion.
    """
    profile_text = user.get("profile_text", "").strip()
    if not profile_text:
        raise ValueError(f"User {user.get('id')!r} has no profile_text.")

    client = _get_client()
    prompt = _build_prompt(job, profile_text)

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(RATELIMIT_DELAY)
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            raw = response.text.strip()
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
                raise RuntimeError(
                    f"Gemini daily quota exhausted for job {job.get('job_id')} / "
                    f"user {user.get('id')}. Will resume on next run."
                ) from exc

            wait = RETRY_DELAY if is_quota else RATELIMIT_DELAY
            logger.warning(
                "Gemini attempt %d/%d failed — job %s / user %s: %s",
                attempt, MAX_RETRIES, job.get("job_id"), user.get("id"), exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(wait)

    raise RuntimeError(
        f"Gemini failed after {MAX_RETRIES} attempts — job {job.get('job_id')} / "
        f"user {user.get('id')}: {last_error}"
    )
