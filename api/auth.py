"""
auth.py — JWT validation for Entra External ID tokens.

Local dev: set SKIP_AUTH=true in .env to bypass validation entirely.
Production: set ENTRA_EXTERNAL_TENANT_ID and ENTRA_CLIENT_ID.

Token flow:
  Frontend (MSAL.js) → obtains Bearer token from Entra External ID tenant
  API request         → Authorization: Bearer <token>
  This module         → validates signature, expiry, audience, issuer
"""
import logging
import os
from functools import lru_cache

import jwt
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

SKIP_AUTH: bool = os.environ.get("SKIP_AUTH", "false").lower() == "true"


@lru_cache(maxsize=1)
def _get_jwks(jwks_uri: str) -> dict:
    """Fetch and cache the JWKS from Entra External ID tenant."""
    resp = requests.get(jwks_uri, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _get_jwks_uri() -> str:
    tenant_id = os.environ.get("ENTRA_EXTERNAL_TENANT_ID", "")
    if not tenant_id:
        raise RuntimeError("ENTRA_EXTERNAL_TENANT_ID is not set.")
    return (
        f"https://{tenant_id}.ciamlogin.com/{tenant_id}"
        f".onmicrosoft.com/discovery/v2.0/keys"
    )


def _validate_token(token: str) -> dict:
    """Validate an Entra External ID JWT. Returns decoded claims."""
    tenant_id = os.environ.get("ENTRA_EXTERNAL_TENANT_ID", "")
    client_id = os.environ.get("ENTRA_CLIENT_ID", "")

    if not tenant_id or not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth not configured. Set ENTRA_EXTERNAL_TENANT_ID and ENTRA_CLIENT_ID.",
        )

    jwks_uri = _get_jwks_uri()
    jwks = _get_jwks(jwks_uri)

    try:
        header = jwt.get_unverified_header(token)
        key = jwt.PyJWKClient(jwks_uri).get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            key.key,
            algorithms=[header.get("alg", "RS256")],
            audience=client_id,
            issuer=f"https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0",
        )
        return claims

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired.")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """
    FastAPI dependency — returns the authenticated user's claims dict.

    In SKIP_AUTH mode (local dev), returns a mock user without touching Cosmos DB.
    In production, validates the JWT and returns claims (sub, email, name, etc.).
    """
    if SKIP_AUTH:
        logger.warning("SKIP_AUTH=true — using mock dev user. Never use in production.")
        user_id = os.environ.get("DEV_USER_ID", "dev-user-001")
        return {
            "sub": user_id,
            "id":  user_id,
            "email": os.environ.get("DEV_USER_EMAIL", "dev@localhost"),
            "name": "Dev User",
        }

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _validate_token(credentials.credentials)
