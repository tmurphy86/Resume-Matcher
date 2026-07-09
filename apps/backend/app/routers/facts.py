"""Facts API endpoints."""

import logging
from typing import Any, Union

from fastapi import APIRouter, HTTPException, Query

from app.database import db
from app.schemas.facts import AnswerGapRequest, DuplicateFactResponse, FactCreate, FactResponse, FactUpdate
from app.services import fact_extractor, interview_mode

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


@router.post("/confirm", response_model=list[Union[FactResponse, DuplicateFactResponse]], status_code=201)
async def confirm_facts_endpoint(
    candidates: list[FactCreate],
) -> list[Union[FactResponse, DuplicateFactResponse]]:
    """Persist confirmed/approved candidate facts to the fact base.

    Implements dedup: checks each candidate against existing facts. If a near-duplicate
    (similarity >= 0.9) is found, returns DuplicateFactResponse. Otherwise, persists and
    returns FactResponse.

    Returns a list mixing FactResponse and DuplicateFactResponse objects.
    """
    results = await fact_extractor.confirm_facts([c.model_dump() for c in candidates])

    # Map results to appropriate response types
    responses: list[Union[FactResponse, DuplicateFactResponse]] = []
    for result in results:
        if result.get("status") == "duplicate":
            responses.append(DuplicateFactResponse(**result))
        else:
            responses.append(FactResponse(**result))

    return responses


@router.post("/gap-questions", response_model=list[dict])
async def get_gap_questions_endpoint(
    job_id: str = Query(..., description="ID of the target job"),
    resume_id: str = Query(..., description="ID of the candidate's resume"),
) -> list[dict[str, Any]]:
    """Generate gap questions for JD requirements not covered by existing facts.

    Analyzes the job description against the verified fact base and the
    resume's content to surface requirements with no supporting evidence.
    Returns a list of targeted questions to elicit verifiable facts.
    """
    return await interview_mode.get_gap_questions(job_id=job_id, resume_id=resume_id)


@router.post("/answer", response_model=dict, status_code=201)
async def answer_gap_question_endpoint(
    request: AnswerGapRequest,
) -> dict[str, Any]:
    """Persist a human answer as a verified fact; return fact + updated gap list.

    Stores the answer as a fact with ``confidence="user_answered"`` and
    ``source="interview"``, then re-runs gap analysis so the caller can
    continue the Q&A loop.
    """
    return await interview_mode.answer_gap_question(
        question=request.question,
        answer=request.answer,
        job_id=request.job_id,
        resume_id=request.resume_id,
    )
