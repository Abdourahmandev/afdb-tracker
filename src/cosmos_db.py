"""
cosmos_db.py — Cosmos DB client for the multi-tenant pipeline.

Auth:
  - Local dev: set COSMOS_CONNECTION_STRING in .env
  - Production: set COSMOS_ENDPOINT — uses DefaultAzureCredential (managed identity)
"""
import logging
import os
from datetime import datetime, timezone

from azure.cosmos import CosmosClient, exceptions
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

_client: CosmosClient | None = None
_database = None


def _get_client() -> CosmosClient:
    global _client
    if _client is not None:
        return _client

    conn_str = os.environ.get("COSMOS_CONNECTION_STRING")
    endpoint = os.environ.get("COSMOS_ENDPOINT")

    if conn_str:
        _client = CosmosClient.from_connection_string(conn_str)
        logger.info("Cosmos DB: connected via connection string (local dev)")
    elif endpoint:
        _client = CosmosClient(url=endpoint, credential=DefaultAzureCredential())
        logger.info("Cosmos DB: connected via DefaultAzureCredential")
    else:
        raise ValueError(
            "Set COSMOS_CONNECTION_STRING (local) or COSMOS_ENDPOINT (production) in environment."
        )
    return _client


def _db():
    global _database
    if _database is None:
        db_name = os.environ.get("COSMOS_DATABASE", "afdb-platform")
        _database = _get_client().get_database_client(db_name)
    return _database


def _jobs():
    return _db().get_container_client("jobs")


def _users():
    return _db().get_container_client("users")


def _evals():
    return _db().get_container_client("evaluations")


# ── Jobs ──────────────────────────────────────────────────────────────────────

def get_known_job_ids(source_id: str) -> set[str]:
    """Return all job_ids already stored for a given source."""
    try:
        items = _jobs().query_items(
            query="SELECT c.job_id FROM c WHERE c.source_id = @s",
            parameters=[{"name": "@s", "value": source_id}],
            partition_key=source_id,
        )
        return {item["job_id"] for item in items}
    except exceptions.CosmosHttpResponseError as e:
        logger.error("get_known_job_ids(%s) failed: %s", source_id, e)
        return set()


def upsert_job(job: dict) -> None:
    """Upsert a job document. Idempotent — safe to call on duplicates."""
    doc = {
        "id": f"{job['source_id']}|{job['job_id']}",
        "job_id": job["job_id"],
        "source_id": job["source_id"],
        "title": job.get("title", ""),
        "location": job.get("location", ""),
        "contract_type": job.get("contract_type", ""),
        "deadline": str(job.get("deadline", "")),
        "description_raw": job.get("description_raw", ""),
        "url": job.get("url", ""),
        "scraped_at": job.get("scraped_at", datetime.now(timezone.utc).isoformat()),
    }
    _jobs().upsert_item(body=doc)


def get_jobs_for_sources(source_ids: list[str]) -> list[dict]:
    """Return all job documents for the given source IDs."""
    if not source_ids:
        return []
    placeholders = ", ".join(f"@s{i}" for i in range(len(source_ids)))
    params = [{"name": f"@s{i}", "value": sid} for i, sid in enumerate(source_ids)]
    try:
        return list(_jobs().query_items(
            query=f"SELECT * FROM c WHERE c.source_id IN ({placeholders})",
            parameters=params,
            enable_cross_partition_query=True,
        ))
    except exceptions.CosmosHttpResponseError as e:
        logger.error("get_jobs_for_sources(%s) failed: %s", source_ids, e)
        return []


# ── Users ─────────────────────────────────────────────────────────────────────

def get_all_active_users() -> list[dict]:
    """Return all verified, active users."""
    try:
        return list(_users().query_items(
            query="SELECT * FROM c WHERE c.verified = true",
            enable_cross_partition_query=True,
        ))
    except exceptions.CosmosHttpResponseError as e:
        logger.error("get_all_active_users() failed: %s", e)
        return []


def upsert_user(user: dict) -> None:
    """Upsert a user document."""
    if "id" not in user:
        user["id"] = user.get("user_id", user.get("email", ""))
    _users().upsert_item(body=user)


# ── Evaluations ───────────────────────────────────────────────────────────────

def get_evaluated_job_ids_for_user(user_id: str) -> set[str]:
    """Return job_ids already evaluated for this user (to skip re-scoring)."""
    try:
        items = _evals().query_items(
            query="SELECT c.job_id FROM c WHERE c.user_id = @u",
            parameters=[{"name": "@u", "value": user_id}],
            partition_key=user_id,
        )
        return {item["job_id"] for item in items}
    except exceptions.CosmosHttpResponseError as e:
        logger.error("get_evaluated_job_ids_for_user(%s) failed: %s", user_id, e)
        return set()


def upsert_evaluation(
    user_id: str,
    job_id: str,
    source_id: str,
    score: int,
    summary: str,
    email_sent: bool = False,
) -> None:
    """Upsert an evaluation. Idempotent."""
    _evals().upsert_item(body={
        "id": f"{user_id}|{job_id}",
        "user_id": user_id,
        "job_id": job_id,
        "source_id": source_id,
        "score": score,
        "summary": summary,
        "email_sent": email_sent,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    })


def mark_evaluation_email_sent(user_id: str, job_id: str) -> None:
    """Flag an evaluation as emailed."""
    eval_id = f"{user_id}|{job_id}"
    try:
        item = _evals().read_item(item=eval_id, partition_key=user_id)
        item["email_sent"] = True
        _evals().upsert_item(body=item)
    except exceptions.CosmosResourceNotFoundError:
        logger.warning("Evaluation %s not found — cannot mark as sent", eval_id)


def get_user_by_email(email: str) -> dict | None:
    """Return a user document by email, or None if not found."""
    try:
        items = list(_users().query_items(
            query="SELECT * FROM c WHERE c.email = @e",
            parameters=[{"name": "@e", "value": email}],
            enable_cross_partition_query=True,
        ))
        return items[0] if items else None
    except exceptions.CosmosHttpResponseError as e:
        logger.error("get_user_by_email(%s) failed: %s", email, e)
        return None


def get_user_by_id(user_id: str) -> dict | None:
    """Return a user document by id, or None if not found."""
    try:
        return _users().read_item(item=user_id, partition_key=user_id)
    except exceptions.CosmosResourceNotFoundError:
        return None
    except exceptions.CosmosHttpResponseError as e:
        logger.error("get_user_by_id(%s) failed: %s", user_id, e)
        return None


def get_user_by_verification_token(token: str) -> dict | None:
    """Return the user with this pending verification token, or None."""
    try:
        items = list(_users().query_items(
            query="SELECT * FROM c WHERE c.verification_token = @t",
            parameters=[{"name": "@t", "value": token}],
            enable_cross_partition_query=True,
        ))
        return items[0] if items else None
    except exceptions.CosmosHttpResponseError as e:
        logger.error("get_user_by_verification_token failed: %s", e)
        return None


def get_unemailed_evaluations_for_user(user_id: str, threshold: int) -> list[dict]:
    """Return evaluations ≥ threshold that haven't been emailed yet."""
    try:
        return list(_evals().query_items(
            query=(
                "SELECT * FROM c WHERE c.user_id = @u "
                "AND c.score >= @t AND c.email_sent = false"
            ),
            parameters=[
                {"name": "@u", "value": user_id},
                {"name": "@t", "value": threshold},
            ],
            partition_key=user_id,
        ))
    except exceptions.CosmosHttpResponseError as e:
        logger.error("get_unemailed_evaluations(%s) failed: %s", user_id, e)
        return []
