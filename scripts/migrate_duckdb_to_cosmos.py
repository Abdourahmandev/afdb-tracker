"""
scripts/migrate_duckdb_to_cosmos.py
────────────────────────────────────────────────────────────────────────────────
One-time migration: copy legacy DuckDB data → Cosmos DB.

What it does
────────────
1. Reads every row from DuckDB `jobs`       → upserts to Cosmos `jobs` container
2. Reads every row from DuckDB `evaluations` → upserts to Cosmos `evaluations`
   container, mapped to a target user (looked up by --email or --user-id).

Why
────
The legacy single-tenant pipeline (LEGACY_MODE=true) stored evaluations with no
user_id. The new multi-tenant pipeline skips re-evaluation by calling
get_evaluated_job_ids_for_user(user_id). Without this migration, it would
re-evaluate every historical job for the first time it runs — wasting Gemini
tokens. After this script runs, the pipeline will only evaluate *new* jobs.

Usage
─────
# Set your Cosmos DB connection first:
export COSMOS_CONNECTION_STRING="AccountEndpoint=https://..."  # local dev
# OR
export COSMOS_ENDPOINT="https://cosmos-afdb-dev.documents.azure.com:443/"  # managed identity

# Then run — pass either --email or --user-id:
python scripts/migrate_duckdb_to_cosmos.py --email your@email.com
python scripts/migrate_duckdb_to_cosmos.py --user-id user-abc123

Options
───────
--email        Email of the Cosmos DB user to map DuckDB evaluations to
--user-id      Direct Cosmos DB user_id (alternative to --email)
--db-path      Path to the DuckDB file (default: data/jobs.duckdb)
--dry-run      Print what would be upserted without writing anything
--jobs-only    Only migrate jobs, skip evaluations
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make sure project root is on the path so src/ and scripts/ imports work
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import duckdb

import src.cosmos_db as cosmos_db


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts(value) -> str:
    """Convert a DuckDB timestamp to an ISO 8601 string."""
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    # datetime / date objects
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


# ── Migration steps ───────────────────────────────────────────────────────────

def migrate_jobs(conn: duckdb.DuckDBPyConnection, dry_run: bool) -> int:
    """Copy every row from DuckDB jobs → Cosmos jobs container."""
    rows = conn.execute(
        "SELECT job_id, title, location, contract_type, deadline, "
        "description_raw, url, scraped_at FROM jobs"
    ).fetchall()

    cols = ["job_id", "title", "location", "contract_type", "deadline",
            "description_raw", "url", "scraped_at"]

    migrated = 0
    skipped  = 0

    for row in rows:
        job = dict(zip(cols, row))
        doc = {
            "job_id":          job["job_id"],
            "source_id":       "afdb",          # legacy pipeline was AfDB-only
            "title":           job["title"] or "",
            "location":        job["location"] or "",
            "contract_type":   job["contract_type"] or "",
            "deadline":        str(job["deadline"] or ""),
            "description_raw": job["description_raw"] or "",
            "url":             job["url"] or "",
            "scraped_at":      _ts(job["scraped_at"]),
        }

        if dry_run:
            print(f"  [DRY-RUN] job  {doc['job_id']}: {doc['title'][:60]}")
        else:
            cosmos_db.upsert_job(doc)

        migrated += 1

    action = "Would migrate" if dry_run else "Migrated"
    print(f"  {action} {migrated} jobs ({skipped} skipped — already existed)")
    return migrated


def migrate_evaluations(
    conn: duckdb.DuckDBPyConnection,
    user_id: str,
    dry_run: bool,
) -> int:
    """Copy every row from DuckDB evaluations → Cosmos evaluations container."""
    rows = conn.execute(
        "SELECT job_id, score, summary, evaluated_at, email_sent FROM evaluations"
    ).fetchall()

    cols = ["job_id", "score", "summary", "evaluated_at", "email_sent"]
    migrated = 0

    for row in rows:
        ev = dict(zip(cols, row))

        # Skip failed evaluations (score=0 means Gemini returned an error)
        if ev["score"] == 0:
            continue

        doc = {
            "id":           f"{user_id}|{ev['job_id']}",
            "user_id":      user_id,
            "job_id":       ev["job_id"],
            "source_id":    "afdb",
            "score":        int(ev["score"]),
            "summary":      ev["summary"] or "",
            "email_sent":   bool(ev["email_sent"]),
            "evaluated_at": _ts(ev["evaluated_at"]),
        }

        if dry_run:
            print(f"  [DRY-RUN] eval {doc['job_id']}: score={doc['score']}")
        else:
            cosmos_db._evals().upsert_item(body=doc)

        migrated += 1

    action = "Would migrate" if dry_run else "Migrated"
    print(f"  {action} {migrated} evaluations → user {user_id}")
    return migrated


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy DuckDB data to Cosmos DB."
    )
    parser.add_argument(
        "--email",
        help="Email of the Cosmos DB user to map evaluations to",
    )
    parser.add_argument(
        "--user-id",
        dest="user_id",
        help="Direct Cosmos DB user_id (alternative to --email)",
    )
    parser.add_argument(
        "--db-path",
        default=str(ROOT / "data" / "jobs.duckdb"),
        help="Path to the DuckDB file (default: data/jobs.duckdb)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be migrated without writing to Cosmos DB",
    )
    parser.add_argument(
        "--jobs-only",
        action="store_true",
        help="Only migrate jobs — skip evaluations",
    )
    args = parser.parse_args()

    # ── Resolve user ──────────────────────────────────────────────────────────
    user_id = None

    if not args.jobs_only:
        if not args.email and not args.user_id:
            print("ERROR: Provide --email or --user-id to map evaluations to a user.")
            print("       Use --jobs-only to migrate only jobs without a user mapping.")
            sys.exit(1)

        if args.user_id:
            user_id = args.user_id
            user = cosmos_db.get_user_by_id(user_id)
            if not user:
                print(f"ERROR: No user found in Cosmos DB with id={user_id!r}")
                sys.exit(1)
        else:
            user = cosmos_db.get_user_by_email(args.email)
            if not user:
                print(f"ERROR: No user found in Cosmos DB with email={args.email!r}")
                print("       Register on the website first, then run this script.")
                sys.exit(1)
            user_id = user["id"]

        print(f"Target user: {user.get('name')} <{user.get('email')}> (id: {user_id})")

    # ── Open DuckDB ───────────────────────────────────────────────────────────
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"ERROR: DuckDB file not found: {db_path}")
        sys.exit(1)

    print(f"Source: {db_path}")
    conn = duckdb.connect(str(db_path), read_only=True)

    job_count  = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    eval_count = conn.execute("SELECT COUNT(*) FROM evaluations WHERE score > 0").fetchone()[0]
    print(f"DuckDB contains: {job_count} jobs, {eval_count} evaluations (score > 0)\n")

    if args.dry_run:
        print("*** DRY RUN — nothing will be written to Cosmos DB ***\n")

    # ── Migrate ───────────────────────────────────────────────────────────────
    print("-- Step 1: Jobs -------------------------------------------------------")
    migrate_jobs(conn, args.dry_run)

    if not args.jobs_only:
        print("\n-- Step 2: Evaluations ------------------------------------------------")
        migrate_evaluations(conn, user_id, args.dry_run)

    conn.close()

    print("\nDone. Migration complete.")
    if not args.dry_run and not args.jobs_only:
        print(
            f"\nNext step: run the pipeline — it will now skip all {eval_count} "
            "already-evaluated jobs and only process new ones."
        )


if __name__ == "__main__":
    main()
