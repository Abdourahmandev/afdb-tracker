"""
seed_cosmos.py — Seed Cosmos DB with test users and sample jobs for local dev.

Usage:
    # Set COSMOS_CONNECTION_STRING in .env first, then:
    python scripts/seed_cosmos.py

Creates:
    - 2 verified test users (alice, bob) with different profiles and source prefs
    - 3 sample AfDB job records (no descriptions, just metadata)
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cosmos_db

TEST_USERS = [
    {
        "id": "user-test-alice",
        "email": "alice@example.com",
        "name": "Alice Dupont",
        "profile_text": (
            "Senior data engineer with 10 years of experience in Python, SQL, Azure Data Factory, "
            "Databricks, and PySpark. Strong background in data pipeline design, ETL automation, "
            "and cloud migration projects. Interested in international development organizations, "
            "remote-friendly roles, and data governance initiatives. Fluent in French and English."
        ),
        "score_threshold": 7,
        "enabled_sources": ["afdb"],
        "notification_email": "alice@example.com",
        "verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "user-test-bob",
        "email": "bob@example.com",
        "name": "Bob Martin",
        "profile_text": (
            "Junior data analyst with 2 years of experience in Excel, Power BI, and basic SQL. "
            "Background in financial analysis and reporting. Seeking entry-level data roles in "
            "international organizations. English only."
        ),
        "score_threshold": 6,
        "enabled_sources": ["afdb"],
        "notification_email": "bob@example.com",
        "verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
]

SAMPLE_JOBS = [
    {
        "job_id": "SEED-001",
        "source_id": "afdb",
        "title": "Senior Data Engineer",
        "location": "Abidjan, Côte d'Ivoire",
        "contract_type": "Regular Staff",
        "deadline": "2025-06-30",
        "description_raw": (
            "The Senior Data Engineer will design and implement data pipelines supporting "
            "the Bank's analytics platform. Required: 7+ years in data engineering, "
            "proficiency in Python, SQL, Azure, and Spark. Experience in data governance "
            "and ETL automation preferred. Hybrid work arrangement available."
        ),
        "url": "https://afdb.example.com/jobs/SEED-001",
    },
    {
        "job_id": "SEED-002",
        "source_id": "afdb",
        "title": "Finance Officer — Budget & Planning",
        "location": "Tunis, Tunisia",
        "contract_type": "Short Term Staff",
        "deadline": "2025-05-15",
        "description_raw": (
            "The Finance Officer will support the budget planning and financial reporting "
            "functions of the department. Required: degree in Finance or Accounting, "
            "3+ years of experience, CPA or equivalent preferred. On-site position."
        ),
        "url": "https://afdb.example.com/jobs/SEED-002",
    },
    {
        "job_id": "SEED-003",
        "source_id": "afdb",
        "title": "Data Governance Specialist",
        "location": "Remote / Flexible",
        "contract_type": "Consultant",
        "deadline": "2025-07-01",
        "description_raw": (
            "Seeking a Data Governance Specialist to develop and implement data quality "
            "frameworks, metadata management standards, and data lineage tooling. "
            "Required: 5+ years in data governance, experience with Collibra or Alation, "
            "strong communication skills. Fully remote role."
        ),
        "url": "https://afdb.example.com/jobs/SEED-003",
    },
]


def seed():
    print("=== AfDB-Platform — Cosmos DB Dev Seed ===\n")

    # Seed users
    print("Seeding users...")
    for user in TEST_USERS:
        cosmos_db.upsert_user(user)
        print(f"  ✓ {user['name']} ({user['email']}) — sources: {user['enabled_sources']}")

    # Seed jobs
    print("\nSeeding jobs...")
    for job in SAMPLE_JOBS:
        cosmos_db.upsert_job(job)
        print(f"  ✓ [{job['source_id'].upper()}] {job['title']}")

    print(f"\nDone. {len(TEST_USERS)} users, {len(SAMPLE_JOBS)} jobs seeded.")
    print("\nTest credentials:")
    print("  alice@example.com — score_threshold=7, sources=[afdb]")
    print("  bob@example.com   — score_threshold=6, sources=[afdb]")
    print("\nRun the pipeline against these users with:")
    print("  LEGACY_MODE=false python src/pipeline_v2.py")


if __name__ == "__main__":
    seed()
