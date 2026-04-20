"""
test_api.py — Integration tests for the AfDB-Platform REST API.

Uses FastAPI TestClient — no real Cosmos DB, Gemini, or SMTP calls.
All external dependencies are mocked.

Run with:
    python -m pytest tests/test_api.py -v
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Patch auth before importing the app so SKIP_AUTH takes effect
import os
os.environ["SKIP_AUTH"] = "true"
os.environ["DEV_USER_EMAIL"] = "alice@example.com"

from api.main import app

client = TestClient(app)

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_USER = {
    "id": "dev-user-001",
    "email": "alice@example.com",
    "name": "Alice",
    "profile_text": "Senior data engineer with 10 years experience.",
    "score_threshold": 7,
    "enabled_sources": ["afdb"],
    "notification_email": "alice@example.com",
    "verified": True,
}

MOCK_JOBS = [
    {
        "job_id": "VAC-001",
        "source_id": "afdb",
        "title": "Senior Data Engineer",
        "location": "Abidjan",
        "contract_type": "Regular Staff",
        "deadline": "2025-06-30",
        "url": "https://afdb.example.com/VAC-001",
        "scraped_at": "2025-01-01T08:00:00Z",
    },
    {
        "job_id": "VAC-002",
        "source_id": "afdb",
        "title": "Finance Officer",
        "location": "Tunis",
        "contract_type": "Short Term",
        "deadline": "2025-05-15",
        "url": "https://afdb.example.com/VAC-002",
        "scraped_at": "2025-01-01T08:00:00Z",
    },
]


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Sources ───────────────────────────────────────────────────────────────────

def test_get_sources_returns_list():
    r = client.get("/api/sources")
    assert r.status_code == 200
    data = r.json()
    assert "sources" in data
    source_ids = [s["source_id"] for s in data["sources"]]
    assert "afdb" in source_ids
    assert "worldbank" in source_ids

def test_afdb_source_is_enabled():
    r = client.get("/api/sources")
    afdb = next(s for s in r.json()["sources"] if s["source_id"] == "afdb")
    assert afdb["enabled"] is True

def test_worldbank_source_is_disabled():
    r = client.get("/api/sources")
    wb = next(s for s in r.json()["sources"] if s["source_id"] == "worldbank")
    assert wb["enabled"] is False


# ── Register ──────────────────────────────────────────────────────────────────

@patch("api.main.cosmos_db.get_user_by_email", return_value=None)
@patch("api.main.cosmos_db.upsert_user")
@patch("api.main._send_verification_email")
def test_register_creates_user(mock_email, mock_upsert, mock_get):
    r = client.post("/api/register", json={
        "email": "newuser@example.com",
        "name": "New User",
        "profile_text": "Data engineer with 5 years experience in Python and SQL.",
        "score_threshold": 7,
        "enabled_sources": ["afdb"],
    })
    assert r.status_code == 201
    data = r.json()
    assert "user_id" in data
    assert len(data["user_id"]) > 0
    mock_upsert.assert_called_once()
    mock_email.assert_called_once_with("newuser@example.com", "New User", mock_upsert.call_args[0][0]["verification_token"])

@patch("api.main.cosmos_db.get_user_by_email", return_value=MOCK_USER)
def test_register_duplicate_email_returns_409(mock_get):
    r = client.post("/api/register", json={
        "email": "alice@example.com",
        "name": "Alice Again",
        "profile_text": "Data engineer with 5 years experience in Python and SQL.",
    })
    assert r.status_code == 409

def test_register_short_profile_returns_422():
    r = client.post("/api/register", json={
        "email": "x@example.com",
        "name": "X",
        "profile_text": "Too short",
    })
    assert r.status_code == 422


# ── Verify ────────────────────────────────────────────────────────────────────

@patch("api.main.cosmos_db.get_user_by_verification_token")
@patch("api.main.cosmos_db.upsert_user")
def test_verify_email_sets_verified(mock_upsert, mock_get_token):
    unverified = {**MOCK_USER, "verified": False, "verification_token": "abc123token"}
    mock_get_token.return_value = unverified

    r = client.get("/api/verify?token=abc123token")
    assert r.status_code == 200
    assert "verified" in r.json()["message"].lower()

    saved = mock_upsert.call_args[0][0]
    assert saved["verified"] is True
    assert "verification_token" not in saved

@patch("api.main.cosmos_db.get_user_by_verification_token", return_value=None)
def test_verify_invalid_token_returns_404(mock_get):
    r = client.get("/api/verify?token=badtoken123456789")
    assert r.status_code == 404


# ── Jobs ─────────────────────────────────────────────────────────────────────

@patch("api.main.cosmos_db.get_user_by_id", return_value=MOCK_USER)
@patch("api.main.cosmos_db.get_jobs_for_sources", return_value=MOCK_JOBS)
@patch("api.main.cosmos_db.get_evaluated_job_ids_for_user", return_value={"VAC-001"})
@patch("api.main.cosmos_db._evals")
def test_get_jobs_returns_paginated(mock_evals, mock_ev_ids, mock_jobs, mock_user):
    mock_container = MagicMock()
    mock_container.query_items.return_value = [
        {"job_id": "VAC-001", "score": 9, "summary": "Excellent match."}
    ]
    mock_evals.return_value = mock_container

    r = client.get("/api/jobs", headers={"Authorization": "Bearer mock-token"})
    assert r.status_code == 200
    data = r.json()
    assert "jobs" in data
    assert data["total"] == 2
    # VAC-001 scored 9 should appear first
    assert data["jobs"][0]["job_id"] == "VAC-001"
    assert data["jobs"][0]["score"] == 9

@patch("api.main.cosmos_db.get_user_by_id", return_value=MOCK_USER)
@patch("api.main.cosmos_db.get_jobs_for_sources", return_value=MOCK_JOBS)
@patch("api.main.cosmos_db.get_evaluated_job_ids_for_user", return_value=set())
@patch("api.main.cosmos_db._evals")
def test_get_jobs_min_score_filter(mock_evals, mock_ev_ids, mock_jobs, mock_user):
    mock_container = MagicMock()
    mock_container.query_items.return_value = []
    mock_evals.return_value = mock_container

    # With min_score=7 and no evaluations, all jobs have score=None → excluded
    r = client.get("/api/jobs?min_score=7", headers={"Authorization": "Bearer mock"})
    assert r.status_code == 200
    assert r.json()["total"] == 0

@patch("api.main.cosmos_db.get_user_by_id", return_value=None)
@patch("api.main.cosmos_db.get_user_by_email", return_value=None)
def test_get_jobs_unknown_user_returns_404(mock_email, mock_user):
    r = client.get("/api/jobs", headers={"Authorization": "Bearer mock"})
    assert r.status_code == 404


# ── Profile ───────────────────────────────────────────────────────────────────

@patch("api.main.cosmos_db.get_user_by_id", return_value={**MOCK_USER})
@patch("api.main.cosmos_db.upsert_user")
def test_update_profile_name(mock_upsert, mock_user):
    r = client.put("/api/profile",
                   json={"name": "Alice Updated"},
                   headers={"Authorization": "Bearer mock"})
    assert r.status_code == 200
    assert r.json()["name"] == "Alice Updated"

@patch("api.main.cosmos_db.get_user_by_id", return_value={**MOCK_USER})
@patch("api.main.cosmos_db.upsert_user")
def test_update_profile_invalid_source_returns_422(mock_upsert, mock_user):
    r = client.put("/api/profile",
                   json={"enabled_sources": ["afdb", "nonexistent_source"]},
                   headers={"Authorization": "Bearer mock"})
    assert r.status_code == 422
