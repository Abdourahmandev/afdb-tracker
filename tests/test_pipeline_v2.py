"""
test_pipeline_v2.py — E2E test for the multi-tenant pipeline.

Uses unittest.mock — no real Cosmos DB, Gemini, or SMTP calls made.
Tests the wiring: correct users evaluated against correct jobs, correct emails sent.

Run with:
    python -m pytest tests/test_pipeline_v2.py -v
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Allow src/ imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ── Fixtures ──────────────────────────────────────────────────────────────────

USER_A = {
    "id": "user-a",
    "email": "alice@example.com",
    "notification_email": "alice@example.com",
    "name": "Alice",
    "profile_text": "Senior data engineer with 10 years experience in Python and Azure.",
    "score_threshold": 7,
    "enabled_sources": ["afdb"],
    "verified": True,
}

USER_B = {
    "id": "user-b",
    "email": "bob@example.com",
    "notification_email": "bob@example.com",
    "name": "Bob",
    "profile_text": "Junior analyst with 2 years in Excel and basic SQL.",
    "score_threshold": 6,
    "enabled_sources": ["afdb"],
    "verified": True,
}

JOB_AFDB_1 = {
    "id": "afdb|VAC-001",
    "job_id": "VAC-001",
    "source_id": "afdb",
    "title": "Senior Data Engineer",
    "location": "Abidjan, Côte d'Ivoire",
    "contract_type": "Regular Staff",
    "deadline": "2024-12-31",
    "description_raw": "We need a senior data engineer with Python and Azure experience.",
    "url": "https://afdb.example.com/jobs/VAC-001",
    "scraped_at": "2024-10-15T08:00:00Z",
}

JOB_AFDB_2 = {
    "id": "afdb|VAC-002",
    "job_id": "VAC-002",
    "source_id": "afdb",
    "title": "Finance Officer",
    "location": "Tunis, Tunisia",
    "contract_type": "Short Term",
    "deadline": "2024-11-30",
    "description_raw": "Finance and accounting role requiring CPA qualification.",
    "url": "https://afdb.example.com/jobs/VAC-002",
    "scraped_at": "2024-10-15T08:00:00Z",
}


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestEvaluatorV2:
    """Unit tests for evaluator_v2.evaluate_job_for_user."""

    def test_evaluate_returns_score_and_summary(self):
        mock_response = MagicMock()
        mock_response.text = '{"score": 8, "summary": "Strong match for data engineering role."}'

        with patch("evaluator_v2._get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_fn.return_value = mock_client

            from evaluator_v2 import evaluate_job_for_user
            result = evaluate_job_for_user(JOB_AFDB_1, USER_A)

        assert result["score"] == 8
        assert "data engineering" in result["summary"].lower()

    def test_raises_on_missing_profile(self):
        from evaluator_v2 import evaluate_job_for_user
        user_no_profile = {**USER_A, "profile_text": ""}
        with pytest.raises(ValueError, match="no profile_text"):
            evaluate_job_for_user(JOB_AFDB_1, user_no_profile)

    def test_raises_on_daily_quota(self):
        mock_response = MagicMock()
        mock_response.text = "Error: PerDay quota exceeded"

        with patch("evaluator_v2._get_client") as mock_client_fn:
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception(
                "429: PerDay quota exhausted"
            )
            mock_client_fn.return_value = mock_client

            from evaluator_v2 import evaluate_job_for_user
            with pytest.raises(RuntimeError, match="daily quota exhausted"):
                evaluate_job_for_user(JOB_AFDB_1, USER_A)


class TestNotifierV2:
    """Unit tests for notifier_v2.send_digest."""

    def test_digest_sent_to_correct_recipient(self):
        matches = [(JOB_AFDB_1, 8, "Strong data engineering match.")]

        with patch("notifier_v2.smtplib.SMTP_SSL") as mock_smtp, \
             patch.dict("os.environ", {"GMAIL_USER": "bot@gmail.com", "GMAIL_APP_PASSWORD": "secret"}):
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            from notifier_v2 import send_digest
            send_digest(USER_A, matches)

            mock_server.sendmail.assert_called_once()
            args = mock_server.sendmail.call_args[0]
            assert args[1] == "alice@example.com"

    def test_no_email_sent_for_empty_matches(self):
        with patch("notifier_v2.smtplib.SMTP_SSL") as mock_smtp:
            from notifier_v2 import send_digest
            send_digest(USER_A, [])
            mock_smtp.assert_not_called()

    def test_subject_includes_source_label(self):
        matches = [(JOB_AFDB_1, 8, "Good match.")]
        captured_msg = {}

        def fake_sendmail(from_addr, to_addr, msg_str):
            captured_msg["subject"] = [
                line for line in msg_str.split("\n") if line.startswith("Subject:")
            ][0]

        with patch("notifier_v2.smtplib.SMTP_SSL") as mock_smtp, \
             patch.dict("os.environ", {"GMAIL_USER": "bot@gmail.com", "GMAIL_APP_PASSWORD": "secret"}):
            mock_server = MagicMock()
            mock_server.sendmail.side_effect = fake_sendmail
            mock_smtp.return_value.__enter__.return_value = mock_server

            from notifier_v2 import send_digest
            send_digest(USER_A, matches)

        assert "AfDB" in captured_msg.get("subject", "")


class TestPipelineV2Integration:
    """
    Integration test for pipeline_v2.run_pipeline_v2.
    Mocks all external calls — verifies pipeline wiring:
      - 2 users, 2 AfDB jobs
      - User A has threshold 7 — scored 8 → gets email
      - User B has threshold 6 — scored 5 → no email (below threshold)
    """

    @patch("pipeline_v2.cosmos_db")
    @patch("pipeline_v2.evaluate_job_for_user")
    @patch("pipeline_v2.send_digest")
    @patch("pipeline_v2.load_enabled_scrapers")
    def test_two_users_correct_emails(
        self, mock_scrapers, mock_send_digest, mock_evaluate, mock_cosmos
    ):
        # Scraper returns 2 new jobs
        mock_scraper = MagicMock()
        mock_scraper.source_id = "afdb"
        mock_scraper.display_name = "AfDB"

        from scrapers.base import JobRecord
        mock_scraper.scrape = MagicMock(return_value=[
            JobRecord(
                job_id=JOB_AFDB_1["job_id"],
                source_id="afdb",
                title=JOB_AFDB_1["title"],
                location=JOB_AFDB_1["location"],
                contract_type=JOB_AFDB_1["contract_type"],
                deadline=JOB_AFDB_1["deadline"],
                description_raw=JOB_AFDB_1["description_raw"],
                url=JOB_AFDB_1["url"],
            ),
        ])
        mock_scrapers.return_value = [mock_scraper]

        # Cosmos DB state
        mock_cosmos.get_known_job_ids.return_value = set()
        mock_cosmos.get_all_active_users.return_value = [USER_A, USER_B]
        mock_cosmos.get_jobs_for_sources.return_value = [JOB_AFDB_1]
        mock_cosmos.get_evaluated_job_ids_for_user.return_value = set()

        # User A gets score 8 (≥ threshold 7) → email expected
        # User B gets score 5 (< threshold 6) → no email expected
        def mock_eval(job, user):
            if user["id"] == "user-a":
                return {"score": 8, "summary": "Strong data engineering match."}
            return {"score": 5, "summary": "Weak match for finance role."}

        mock_evaluate.side_effect = mock_eval

        # Unemailed evals per user
        def mock_unemailed(user_id, threshold):
            if user_id == "user-a":
                return [{"job_id": "VAC-001", "score": 8, "summary": "Strong match."}]
            return []  # User B's score 5 < threshold 6

        mock_cosmos.get_unemailed_evaluations_for_user.side_effect = mock_unemailed

        from pipeline_v2 import run_pipeline_v2
        run_pipeline_v2()

        # User A receives 1 digest email
        assert mock_send_digest.call_count == 1
        called_user = mock_send_digest.call_args[0][0]
        assert called_user["id"] == "user-a"

        # Upsert was called for the scraped job
        mock_cosmos.upsert_job.assert_called_once()
        upserted = mock_cosmos.upsert_job.call_args[0][0]
        assert upserted["job_id"] == "VAC-001"

    @patch("pipeline_v2.cosmos_db")
    @patch("pipeline_v2.load_enabled_scrapers")
    def test_legacy_mode_not_affected(self, mock_scrapers, mock_cosmos):
        """LEGACY_MODE=true must not call pipeline_v2 at all."""
        import os
        with patch.dict(os.environ, {"LEGACY_MODE": "true"}):
            with patch("main.run_pipeline") as mock_legacy:
                from main import run
                run()
                mock_legacy.assert_called_once()
                mock_scrapers.assert_not_called()
                mock_cosmos.get_all_active_users.assert_not_called()


class TestEvaluationSkipGuard:
    """
    Non-negotiable: jobs that already have an evaluation for a user must
    never be re-evaluated (no Gemini token spend on known jobs).
    """

    @patch("pipeline_v2.cosmos_db")
    @patch("pipeline_v2.evaluate_job_for_user")
    @patch("pipeline_v2.send_digest")
    @patch("pipeline_v2.load_enabled_scrapers")
    def test_already_evaluated_jobs_are_skipped(
        self, mock_scrapers, mock_send_digest, mock_evaluate, mock_cosmos
    ):
        """evaluate_job_for_user must NOT be called for jobs already in evaluated_ids."""
        mock_scraper = MagicMock()
        mock_scraper.source_id = "afdb"
        mock_scraper.scrape = MagicMock(return_value=[])
        mock_scrapers.return_value = [mock_scraper]

        # Two jobs in Cosmos DB, both already evaluated for user-a
        mock_cosmos.get_all_active_users.return_value = [USER_A]
        mock_cosmos.get_jobs_for_sources.return_value = [JOB_AFDB_1, JOB_AFDB_2]
        mock_cosmos.get_evaluated_job_ids_for_user.return_value = {"VAC-001", "VAC-002"}
        mock_cosmos.get_unemailed_evaluations_for_user.return_value = []
        mock_cosmos.get_known_job_ids.return_value = set()

        from pipeline_v2 import run_pipeline_v2
        run_pipeline_v2()

        # No Gemini calls — both jobs were already scored
        mock_evaluate.assert_not_called()

    @patch("pipeline_v2.cosmos_db")
    @patch("pipeline_v2.evaluate_job_for_user")
    @patch("pipeline_v2.send_digest")
    @patch("pipeline_v2.load_enabled_scrapers")
    def test_only_new_jobs_are_evaluated(
        self, mock_scrapers, mock_send_digest, mock_evaluate, mock_cosmos
    ):
        """Only jobs NOT in evaluated_ids must be passed to evaluate_job_for_user."""
        mock_scraper = MagicMock()
        mock_scraper.source_id = "afdb"
        mock_scraper.scrape = MagicMock(return_value=[])
        mock_scrapers.return_value = [mock_scraper]

        # VAC-001 already evaluated, VAC-002 is new
        mock_cosmos.get_all_active_users.return_value = [USER_A]
        mock_cosmos.get_jobs_for_sources.return_value = [JOB_AFDB_1, JOB_AFDB_2]
        mock_cosmos.get_evaluated_job_ids_for_user.return_value = {"VAC-001"}
        mock_cosmos.get_unemailed_evaluations_for_user.return_value = []
        mock_cosmos.get_known_job_ids.return_value = set()
        mock_evaluate.return_value = {"score": 7, "summary": "Finance role."}

        from pipeline_v2 import run_pipeline_v2
        run_pipeline_v2()

        # evaluate_job_for_user called exactly once — for VAC-002 only
        mock_evaluate.assert_called_once()
        evaluated_job = mock_evaluate.call_args[0][0]
        assert evaluated_job["job_id"] == "VAC-002", (
            f"Expected VAC-002 to be evaluated, got {evaluated_job['job_id']!r}. "
            "Already-evaluated jobs must be skipped."
        )


class TestCosmosDbModule:
    """Unit tests for cosmos_db helper functions (no real Cosmos calls)."""

    def test_raises_if_no_env_set(self):
        import os
        with patch.dict(os.environ, {}, clear=True):
            # Clear cached client
            import cosmos_db
            cosmos_db._client = None
            cosmos_db._database = None
            with pytest.raises(ValueError, match="COSMOS_CONNECTION_STRING"):
                cosmos_db._get_client()
