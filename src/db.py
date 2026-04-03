import duckdb
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.environ.get("DATA_DIR", "/app/data")) / "jobs.duckdb"


def _connect() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def init_db() -> None:
    """Create tables if they don't already exist."""
    con = _connect()
    con.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id          VARCHAR PRIMARY KEY,
            title           VARCHAR,
            location        VARCHAR,
            contract_type   VARCHAR,
            deadline        VARCHAR,
            description_raw VARCHAR,
            url             VARCHAR,
            scraped_at      TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            job_id       VARCHAR PRIMARY KEY,
            score        INTEGER,
            summary      VARCHAR,
            evaluated_at TIMESTAMP,
            email_sent   BOOLEAN
        )
    """)
    con.close()


def is_new_job(job_id: str) -> bool:
    """Return True if this job_id has never been seen before."""
    con = _connect()
    result = con.execute(
        "SELECT COUNT(*) FROM jobs WHERE job_id = ?", [job_id]
    ).fetchone()
    con.close()
    return result[0] == 0


def get_unevaluated_jobs() -> list[dict]:
    """Return jobs with no evaluation yet, or where a previous evaluation errored (score=0)."""
    con = _connect()
    rows = con.execute("""
        SELECT j.job_id, j.title, j.location, j.contract_type,
               j.deadline, j.description_raw, j.url
        FROM jobs j
        LEFT JOIN evaluations e ON j.job_id = e.job_id
        WHERE e.job_id IS NULL OR e.score = 0
    """).fetchall()
    con.close()
    keys = ["job_id", "title", "location", "contract_type", "deadline", "description_raw", "url"]
    return [dict(zip(keys, row)) for row in rows]


def get_unemailed_jobs(score_threshold: int) -> list[dict]:
    """Return jobs that scored >= threshold but were never emailed (e.g. due to bad credentials)."""
    con = _connect()
    rows = con.execute("""
        SELECT j.job_id, j.title, j.location, j.contract_type,
               j.deadline, j.description_raw, j.url,
               e.score, e.summary
        FROM jobs j
        JOIN evaluations e ON j.job_id = e.job_id
        WHERE e.score >= ? AND e.email_sent = false
        ORDER BY e.score DESC
    """, [score_threshold]).fetchall()
    con.close()
    keys = ["job_id", "title", "location", "contract_type", "deadline", "description_raw", "url", "score", "summary"]
    return [dict(zip(keys, row)) for row in rows]


def mark_email_sent(job_id: str) -> None:
    """Mark an existing evaluation row as emailed."""
    con = _connect()
    con.execute("UPDATE evaluations SET email_sent = true WHERE job_id = ?", [job_id])
    con.close()


def insert_job(job: dict) -> None:
    """Insert a scraped job record. Silently skips if already exists."""
    con = _connect()
    con.execute(
        """
        INSERT OR IGNORE INTO jobs (job_id, title, location, contract_type, deadline,
                          description_raw, url, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            job["job_id"],
            job.get("title", ""),
            job.get("location", ""),
            job.get("contract_type", ""),
            job.get("deadline", ""),
            job.get("description_raw", ""),
            job.get("url", ""),
            datetime.utcnow(),
        ],
    )
    con.close()


def insert_evaluation(
    job_id: str, score: int, summary: str, email_sent: bool
) -> None:
    """Insert or replace a Gemini evaluation result."""
    con = _connect()
    con.execute(
        """
        INSERT OR REPLACE INTO evaluations (job_id, score, summary, evaluated_at, email_sent)
        VALUES (?, ?, ?, ?, ?)
        """,
        [job_id, score, summary, datetime.utcnow(), email_sent],
    )
    con.close()
