"""Service for extracting and confirming career facts from master resumes."""

import difflib
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

# Similarity threshold for duplicate detection
_SIMILARITY_THRESHOLD: float = 0.9


def _normalize_statement(statement: str) -> str:
    """Normalize a statement for similarity comparison."""
    return statement.lower().strip()


def _compute_similarity(statement_a: str, statement_b: str) -> float:
    """Compute similarity ratio between two statements using SequenceMatcher.

    Args:
        statement_a: First statement to compare.
        statement_b: Second statement to compare.

    Returns:
        Similarity ratio between 0.0 and 1.0.
    """
    normalized_a = _normalize_statement(statement_a)
    normalized_b = _normalize_statement(statement_b)
    matcher = difflib.SequenceMatcher(None, normalized_a, normalized_b)
    return matcher.ratio()


def _find_duplicate_fact(
    candidate_statement: str, existing_facts: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Check if a candidate statement is a duplicate of any existing fact.

    Args:
        candidate_statement: The statement to check.
        existing_facts: List of existing fact dicts from the database.

    Returns:
        The first matching existing fact if a duplicate is found (ratio >= threshold),
        or None if no duplicate exists.
    """
    for existing_fact in existing_facts:
        similarity = _compute_similarity(
            candidate_statement, existing_fact.get("statement", "")
        )
        if similarity >= _SIMILARITY_THRESHOLD:
            return existing_fact
    return None


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
    Each candidate is annotated with a 'duplicate_of' field:
      - If a near-duplicate exists (similarity >= 0.9), duplicate_of contains the existing fact_id
      - Otherwise, duplicate_of is None

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

    # Load existing facts for duplicate checking
    try:
        existing_facts = await db.list_facts()
    except Exception as e:
        logger.error("Failed to load existing facts for dedup check: %s", e)
        existing_facts = []

    # Normalize candidates and annotate with duplicate_of
    annotated_candidates: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue

        normalized = _normalize_candidate(item, resume_id)

        # Check if this candidate is a duplicate of an existing fact
        duplicate = _find_duplicate_fact(normalized.get("statement", ""), existing_facts)
        if duplicate:
            normalized["duplicate_of"] = duplicate.get("fact_id", "")
        else:
            normalized["duplicate_of"] = None

        annotated_candidates.append(normalized)

    return annotated_candidates


async def confirm_facts(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persist confirmed/edited candidate facts to the fact base.

    Implements dedup: before inserting each candidate, checks for near-duplicates
    (similarity >= 0.9) against all existing facts. If a duplicate is found,
    returns a dict with status="duplicate" and existing_fact_id. Otherwise,
    persists with confidence='verified' and returns the persisted fact dict.

    Returns a list of mixed dicts: persisted fact dicts and duplicate-flagging dicts.
    """
    results: list[dict[str, Any]] = []

    # Load all existing facts once for dedup checking
    try:
        existing_facts = await db.list_facts()
    except Exception as e:
        logger.error("Failed to load existing facts for dedup: %s", e)
        existing_facts = []

    for candidate in candidates:
        statement = candidate.get("statement", "")

        # Check if this candidate is a duplicate
        duplicate_fact = _find_duplicate_fact(statement, existing_facts)
        if duplicate_fact:
            # Return duplicate-flagging dict instead of persisting
            results.append(
                {
                    "status": "duplicate",
                    "existing_fact_id": duplicate_fact.get("fact_id", ""),
                    "statement": statement,
                }
            )
            continue

        # No duplicate found, persist the fact
        try:
            fact = await db.create_fact(
                statement=statement,
                context=candidate.get("context", ""),
                source=candidate.get("source", ""),
                metrics_json=candidate.get("metrics_json") or {},
                tags_json=candidate.get("tags_json") or [],
                confidence="verified",
            )
            results.append(fact)
            # Add newly persisted fact to the existing_facts list for subsequent checks
            # so later duplicates can detect against this newly added fact
            existing_facts.append(fact)
        except Exception as e:
            logger.error("Failed to persist fact: %s — %s", statement, e)
            raise HTTPException(
                status_code=500,
                detail="Failed to save facts. Please try again.",
            )

    return results
