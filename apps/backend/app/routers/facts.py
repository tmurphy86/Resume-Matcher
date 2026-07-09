"""Facts API endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.database import db
from app.schemas.facts import FactCreate, FactResponse, FactUpdate
from app.services import fact_extractor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/facts", tags=["Facts"])


@router.get("", response_model=list[FactResponse])
async def list_facts(tag: str | None = None, context: str | None = None) -> list[FactResponse]:
    """List all facts, optionally filtered by tag and/or context."""
    try:
        facts = await db.list_facts(tag=tag, context=context)
    except Exception as e:
        logger.error("Failed to list facts: %s", e)
        raise HTTPException(status_code=500, detail="Failed to list facts. Please try again.")
    return [FactResponse(**fact) for fact in facts]


@router.post("", response_model=FactResponse, status_code=201)
async def create_fact(request: FactCreate) -> FactResponse:
    """Create a new fact."""
    try:
        fact = await db.create_fact(
            statement=request.statement,
            context=request.context,
            source=request.source,
            metrics_json=request.metrics_json,
            tags_json=request.tags_json,
            confidence=request.confidence,
        )
    except Exception as e:
        logger.error("Failed to create fact: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create fact. Please try again.")
    return FactResponse(**fact)


@router.patch("/{fact_id}", response_model=FactResponse)
async def update_fact(fact_id: str, request: FactUpdate) -> FactResponse:
    """Update a fact."""
    updates = request.model_dump(exclude_unset=True)
    try:
        fact = await db.update_fact(fact_id, updates)
    except Exception as e:
        logger.error("Failed to update fact %s: %s", fact_id, e)
        raise HTTPException(status_code=500, detail="Failed to update fact. Please try again.")
    if fact is None:
        raise HTTPException(status_code=404, detail="Fact not found")
    return FactResponse(**fact)


@router.delete("/{fact_id}")
async def delete_fact(fact_id: str) -> dict[str, Any]:
    """Delete a fact."""
    try:
        deleted = await db.delete_fact(fact_id)
    except Exception as e:
        logger.error("Failed to delete fact %s: %s", fact_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete fact. Please try again.")
    if not deleted:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"message": "Fact deleted", "affected": 1}


@router.post("/extract", response_model=list[FactResponse])
async def extract_facts(resume_id: str = Query(...)) -> list[FactResponse]:
    """Extract candidate facts from a master resume (not persisted).

    Returns candidates for human review. Call POST /facts/confirm to persist
    the approved facts.
    """
    candidates = await fact_extractor.extract_candidate_facts(resume_id)
    return [FactResponse(**c) for c in candidates]


@router.post("/confirm", response_model=list[FactResponse], status_code=201)
async def confirm_facts_endpoint(candidates: list[FactCreate]) -> list[FactResponse]:
    """Persist confirmed/approved candidate facts to the fact base."""
    persisted = await fact_extractor.confirm_facts([c.model_dump() for c in candidates])
    return [FactResponse(**f) for f in persisted]
