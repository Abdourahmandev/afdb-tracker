"""
api/main.py — AfDB-Platform REST API (FastAPI).

Endpoints:
  POST /api/register     — create account, send verification email
  GET  /api/verify       — verify email with token
  GET  /api/jobs         — authenticated: paginated job list for current user
  PUT  /api/profile      — authenticated: update profile & preferences
  GET  /api/sources      — list all job sources and their status

Auth: Entra External ID Bearer token (set SKIP_AUTH=true for local dev).
DB:   Azure Cosmos DB via src/cosmos_db.py.
"""
import logging
import os
import secrets
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import yaml
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

# Allow src/ imports when running as part of the Azure Functions app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import cosmos_db
from api.auth import get_current_user, get_optional_user
from api.models import (
    JobItem,
    JobsResponse,
    MessageResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    RegisterResponse,
    SourceItem,
    SourcesResponse,
    UserProfile,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AfDB-Platform API",
    version="0.2.0",
    description="Multi-tenant job alert platform — REST API",
)

# CORS: allow Static Web Apps origin + localhost for dev
_DEFAULT_CORS_ORIGINS = ",".join([
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:7071",
    "https://*.azurestaticapps.net",
])
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.azurestaticapps\.net",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Primary path travels inside the deployed zip alongside api/; fallback for local dev.
_SOURCES_CONFIG = Path(__file__).parent / "sources.yaml"
_SOURCES_CONFIG_FALLBACK = Path(__file__).parent.parent / "scrapers" / "config" / "sources.yaml"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _send_verification_email(to_email: str, name: str, token: str) -> None:
    """Send an email verification link via Gmail SMTP."""
    gmail_user = os.environ.get("GMAIL_USER", "")
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    base_url = os.environ.get("API_BASE_URL", "http://localhost:7071")

    if not gmail_user or not app_password:
        logger.warning("Gmail credentials not set — skipping verification email.")
        return

    verify_url = f"{base_url}/api/verify?token={token}"
    subject = "Verify your AfDB-Platform account"

    html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:520px;margin:auto;padding:20px;color:#333;">
  <h2 style="color:#1a237e;">Welcome to AfDB-Platform, {name}!</h2>
  <p>Click the button below to verify your email and activate your account.</p>
  <a href="{verify_url}"
     style="display:inline-block;margin:16px 0;padding:12px 28px;
            background:#1a237e;color:white;text-decoration:none;border-radius:4px;">
    Verify Email →
  </a>
  <p style="font-size:12px;color:#999;">
    This link expires in 24 hours. If you didn't register, ignore this email.
  </p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to_email
    msg.attach(MIMEText(f"Verify your account: {verify_url}", "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, app_password)
        server.sendmail(gmail_user, to_email, msg.as_string())

    logger.info("Verification email sent to %s", to_email)


def _load_sources() -> dict:
    for path in (_SOURCES_CONFIG, _SOURCES_CONFIG_FALLBACK):
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f).get("sources", {})
    logger.warning("sources.yaml not found — returning empty sources list")
    return {}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/register", response_model=RegisterResponse, status_code=201)
async def register(body: RegisterRequest, claims: dict | None = Depends(get_optional_user)):
    """
    Create a new user account.
    If an Entra External ID Bearer token is present, the token's sub claim is
    used as the user_id so that subsequent authenticated requests (which also
    resolve the user by sub) find the correct profile.
    Sends a verification email — user cannot log in until verified.
    """
    existing = cosmos_db.get_user_by_email(body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Use Entra sub as user_id when authenticated so profile lookups by sub work.
    user_id = (claims.get("sub") or claims.get("id")) if claims else None
    if not user_id:
        user_id = f"user-{secrets.token_hex(8)}"
    verification_token = secrets.token_urlsafe(32)

    user_doc = {
        "id": user_id,
        "email": body.email,
        "name": body.name,
        "profile_text": body.profile_text,
        "score_threshold": body.score_threshold,
        "enabled_sources": body.enabled_sources,
        "notification_email": body.email,
        "verified": False,
        "verification_token": verification_token,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    cosmos_db.upsert_user(user_doc)

    try:
        _send_verification_email(body.email, body.name, verification_token)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", body.email, e)
        # Don't fail registration if email fails — user can request resend later

    return RegisterResponse(
        message="Account created. Check your email to verify your address.",
        user_id=user_id,
    )


@app.get("/api/verify", response_model=MessageResponse)
async def verify_email(token: str = Query(..., min_length=10)):
    """
    Verify a user's email address using the token from the verification email.
    """
    user = cosmos_db.get_user_by_verification_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification token is invalid or has already been used.",
        )

    user["verified"] = True
    user.pop("verification_token", None)
    cosmos_db.upsert_user(user)

    logger.info("User %s verified email.", user.get("id"))
    return MessageResponse(message="Email verified. You can now log in.")


@app.get("/api/jobs", response_model=JobsResponse)
async def get_jobs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    source: str | None = Query(default=None),
    min_score: int = Query(default=0, ge=0, le=10),
    claims: dict = Depends(get_current_user),
):
    """
    Return evaluated jobs for the authenticated user.
    Filtered by their enabled sources and optional query params.
    """
    user_id = claims.get("sub") or claims.get("id", "")
    user = cosmos_db.get_user_by_id(user_id)
    if not user:
        email = claims.get("email", "")
        if email:
            user = cosmos_db.get_user_by_email(email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found. Complete registration first.",
        )

    # Determine which sources to query
    enabled = user.get("enabled_sources", ["afdb"])
    sources_to_query = [source] if source and source in enabled else enabled

    # Fetch jobs and evaluations
    all_jobs = cosmos_db.get_jobs_for_sources(sources_to_query)
    evaluated_ids = cosmos_db.get_evaluated_job_ids_for_user(user_id)

    # Fetch evaluations to enrich jobs with score/summary
    eval_map: dict[str, dict] = {}
    if evaluated_ids:
        try:
            evals = list(
                cosmos_db._evals().query_items(
                    query="SELECT c.job_id, c.score, c.summary FROM c WHERE c.user_id = @u",
                    parameters=[{"name": "@u", "value": user_id}],
                    partition_key=user_id,
                )
            )
            eval_map = {e["job_id"]: e for e in evals}
        except Exception as e:
            logger.warning("Could not fetch evaluations for user %s: %s", user_id, e)

    # Build job items with scores
    items: list[JobItem] = []
    for job in all_jobs:
        ev = eval_map.get(job["job_id"])
        score = ev["score"] if ev else None
        # Exclude jobs with no score when caller requested a minimum score,
        # and exclude jobs whose score falls below the threshold.
        if min_score > 0 and score is None:
            continue
        if score is not None and score < min_score:
            continue
        items.append(JobItem(
            job_id=job["job_id"],
            source_id=job.get("source_id", ""),
            title=job.get("title", ""),
            location=job.get("location", ""),
            contract_type=job.get("contract_type", ""),
            deadline=job.get("deadline", ""),
            url=job.get("url", ""),
            score=score,
            summary=ev["summary"] if ev else None,
            scraped_at=job.get("scraped_at", ""),
        ))

    # Sort: evaluated (by score DESC) first, unevaluated last
    items.sort(key=lambda j: (j.score is None, -(j.score or 0)))

    total = len(items)
    start = (page - 1) * limit
    paginated = items[start: start + limit]

    return JobsResponse(jobs=paginated, total=total, page=page, limit=limit)


@app.put("/api/profile", response_model=UserProfile)
async def update_profile(
    body: ProfileUpdateRequest,
    claims: dict = Depends(get_current_user),
):
    """Update the authenticated user's profile and preferences."""
    user_id = claims.get("sub") or claims.get("id", "")
    user = cosmos_db.get_user_by_id(user_id)
    if not user:
        email = claims.get("email", "")
        if email:
            user = cosmos_db.get_user_by_email(email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )

    if body.name is not None:
        user["name"] = body.name
    if body.profile_text is not None:
        user["profile_text"] = body.profile_text
    if body.score_threshold is not None:
        user["score_threshold"] = body.score_threshold
    if body.enabled_sources is not None:
        # Validate against known sources
        known = set(_load_sources().keys())
        invalid = [s for s in body.enabled_sources if s not in known]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown source(s): {invalid}. Check GET /api/sources.",
            )
        user["enabled_sources"] = body.enabled_sources

    user["updated_at"] = datetime.now(timezone.utc).isoformat()
    cosmos_db.upsert_user(user)

    return UserProfile(
        user_id=user["id"],
        email=user["email"],
        name=user["name"],
        score_threshold=user["score_threshold"],
        enabled_sources=user["enabled_sources"],
        verified=user["verified"],
    )


@app.get("/api/profile", response_model=UserProfile)
async def get_profile(
    claims: dict = Depends(get_current_user),
):
    """Return the authenticated user's profile."""
    user_id = claims.get("sub") or claims.get("id", "")
    user = cosmos_db.get_user_by_id(user_id)
    if not user:
        email = claims.get("email", "")
        if email:
            user = cosmos_db.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found. Complete registration first.",
        )
    return UserProfile(
        user_id=user["id"],
        email=user["email"],
        name=user["name"],
        score_threshold=user["score_threshold"],
        enabled_sources=user["enabled_sources"],
        verified=user["verified"],
    )


@app.get("/api/sources", response_model=SourcesResponse)
async def get_sources():
    """List all available job sources and their enabled status."""
    raw = _load_sources()
    sources = [
        SourceItem(
            source_id=sid,
            display_name=cfg.get("display_name", sid),
            enabled=cfg.get("enabled", False),
            color=cfg.get("color", "#555555"),
            enabled_by_default=cfg.get("enabled_by_default", False),
        )
        for sid, cfg in raw.items()
    ]
    return SourcesResponse(sources=sources)


@app.get("/api/health")
async def health():
    """Health check — no auth required."""
    return {"status": "ok", "version": app.version}
