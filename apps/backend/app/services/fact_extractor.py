"""Service for extracting and confirming career facts from master resumes."""

import json
import logging
from typing import Any

from fastapi import HTTPException

from app.database import db
from app.llm import complete_json
from app.prompts.fact_extraction import FACT_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

# Required fields every candidate fact dict must have (with fallback defaults).
_REQUIRED_FIELDS: dict[str, Any] = {
    "statement": "",
    "context": "",
    "source": "",
    "metrics_json": {},
    "tags_json": [],
    "confidence": "candidate",
}


def _normalize_candidate(item: dict[str, Any], resume_id: str) -> dict[str, Any]:
    """Fill missing fields with defaults and enforce confidence='candidate'."""
    normalized: dict[str, Any] = {}
    for field, default in _REQUIRED_FIELDS.items():
        normalized[field] = item.get(field, default)
    # Enforce candidate confidence — never trust LLM to set it differently.
    normalized["confidence"] = "candidate"
    # Ensure source traces back to the resume if the LLM left it blank.
    if not normalized["source"]:
        normalized["source"] = f"resume:{resume_id}"
    # Guard against non-dict / non-list values from the LLM.
    if not isinstance(normalized["metrics_json"], dict):
        normalized["metrics_json"] = {}
    if not isinstance(normalized["tags_json"], list):
        normalized["tags_json"] = []
    return normalized


async def extract_candidate_facts(resume_id: str) -> list[dict[str, Any]]:
    """Extract candidate facts from a resume's processed_data via LLM.

    Returns a list of candidate fact dicts (not persisted — confidence='candidate').
    Raises HTTPException(404) if the resume is not found or has no processed_data.
    """
    resume = await db.get_resume(resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")

    processed_data = resume.get("processed_data")
    if not processed_data:
        raise HTTPException(
            status_code=404,
            detail="Resume has no processed data. Upload and process the resume first.",
        )

    prompt = FACT_EXTRACTION_PROMPT.format(
        resume_json=json.dumps(processed_data, indent=2)
    )

    try:
        raw = await complete_json(prompt, schema_type="keywords")
    except Exception as e:
        logger.error("Fact extraction LLM call failed for resume %s: %s", resume_id, e)
        raise HTTPException(
            status_code=500,
            detail="Fact extraction failed. Please try again.",
        )

    # The LLM may return a bare list or wrap it: {"facts": [...]}
    if isinstance(raw, dict):
        candidates = raw.get("facts") or raw.get("items") or raw.get("data") or []
    elif isinstance(raw, list):
        candidates = raw
    else:
        logger.warning("Unexpected LLM response type for fact extraction: %s", type(raw))
        candidates = []

    return [
        _normalize_candidate(item, resume_id)
        for item in candidates
        if isinstance(item, dict)
    ]


async def confirm_facts(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persist confirmed/edited candidate facts to the fact base.

    Sets confidence='verified' on each. Returns the persisted fact dicts.
    """
    persisted: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            fact = await db.create_fact(
                statement=candidate.get("statement", ""),
                context=candidate.get("context", ""),
                source=candidate.get("source", ""),
                metrics_json=candidate.get("metrics_json") or {},
                tags_json=candidate.get("tags_json") or [],
                confidence="verified",
            )
            persisted.append(fact)
        except Exception as e:
            logger.error("Failed to persist fact: %s — %s", candidate.get("statement"), e)
            raise HTTPException(
                status_code=500,
                detail="Failed to save facts. Please try again.",
            )
    return persisted
