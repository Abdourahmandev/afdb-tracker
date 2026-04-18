"""
Pydantic request/response models for the AfDB-Platform API.
"""
from typing import Literal
from pydantic import BaseModel, EmailStr, Field


# ── Register ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=120)
    profile_text: str = Field(..., min_length=20, max_length=10_000)
    score_threshold: int = Field(default=7, ge=1, le=10)
    enabled_sources: list[str] = Field(default=["afdb"])


class RegisterResponse(BaseModel):
    message: str
    user_id: str


# ── Profile ───────────────────────────────────────────────────────────────────

class ProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    profile_text: str | None = Field(default=None, min_length=20, max_length=10_000)
    score_threshold: int | None = Field(default=None, ge=1, le=10)
    enabled_sources: list[str] | None = None


class UserProfile(BaseModel):
    user_id: str
    email: str
    name: str
    score_threshold: int
    enabled_sources: list[str]
    verified: bool


# ── Jobs ─────────────────────────────────────────────────────────────────────

class JobItem(BaseModel):
    job_id: str
    source_id: str
    title: str
    location: str
    contract_type: str
    deadline: str
    url: str
    score: int | None = None
    summary: str | None = None
    scraped_at: str


class JobsResponse(BaseModel):
    jobs: list[JobItem]
    total: int
    page: int
    limit: int


# ── Sources ───────────────────────────────────────────────────────────────────

class SourceItem(BaseModel):
    source_id: str
    display_name: str
    enabled: bool
    color: str
    enabled_by_default: bool


class SourcesResponse(BaseModel):
    sources: list[SourceItem]


# ── Generic ───────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
