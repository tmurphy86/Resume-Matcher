"""Pydantic schemas for the facts API."""

from typing import Literal

from pydantic import BaseModel


class FactCreate(BaseModel):
    """Create a new fact."""

    statement: str
    context: str | None = None
    source: str | None = None
    metrics_json: dict = {}
    tags_json: list[str] = []
    confidence: str = "verified"


class FactUpdate(BaseModel):
    """Partial update — every field optional."""

    statement: str | None = None
    context: str | None = None
    source: str | None = None
    metrics_json: dict | None = None
    tags_json: list[str] | None = None
    confidence: str | None = None


class FactResponse(BaseModel):
    """A fact with all fields.

    ``fact_id``, ``created_at``, ``updated_at`` default to empty strings so
    candidate facts returned by POST /facts/extract (not yet persisted) can be
    serialised without database-assigned values.
    """

    fact_id: str = ""
    statement: str
    context: str | None = None
    source: str | None = None
    metrics_json: dict
    tags_json: list[str]
    confidence: str
    created_at: str = ""
    updated_at: str = ""
    duplicate_of: str | None = None


class DuplicateFactResponse(BaseModel):
    """Response when a fact is detected as a duplicate during confirmation."""

    status: Literal["duplicate"]
    existing_fact_id: str
    statement: str
