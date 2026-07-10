"""Service for extracting and confirming career facts from master resumes."""

import copy
import difflib
import json
import logging
from typing import Any
from uuid import uuid4

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

    # The LLM should return {"facts": [...]} (as the prompt instructs).
    # Also accept bare lists and alternative wrapper keys for robustness.
    if isinstance(raw, list):
        candidates = raw
    elif isinstance(raw, dict):
        if "facts" in raw:
            candidates = raw["facts"] if isinstance(raw["facts"], list) else []
        elif "items" in raw:
            candidates = raw["items"] if isinstance(raw["items"], list) else []
        elif "data" in raw:
            candidates = raw["data"] if isinstance(raw["data"], list) else []
        else:
            # No recognised wrapper key — the LLM ignored the "facts" wrapper
            # instruction (e.g. _extract_json extracted a single fact dict from
            # a bare array).  Raise instead of silently returning [] so the
            # frontend surfaces an actionable error rather than an empty modal.
            # (BUG-003 regression guard.)
            logger.error(
                "Unexpected LLM response shape for fact extraction: keys=%s "
                "(expected 'facts' key).  Prompt may need review.",
                list(raw.keys()),
            )
            raise HTTPException(
                status_code=500,
                detail="Fact extraction failed. Please try again.",
            )
    else:
        logger.warning("Unexpected LLM response type for fact extraction: %s", type(raw))
        candidates = []

    # Load existing facts for duplicate checking
    try:
        existing_facts = await db.list_facts()
    except Exception as e:
        logger.error("Failed to load existing facts for dedup check: %s", e)
        existing_facts = []

    # Normalize candidates and annotate with duplicate_of.
    # Each candidate gets a temporary fact_id (UUID) so the frontend can use it
    # as a stable React key and for per-item selection state.  These IDs are
    # never persisted — /facts/confirm generates real IDs on save.
    annotated_candidates: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue

        normalized = _normalize_candidate(item, resume_id)
        # Assign a temporary unique ID for frontend key/selection tracking.
        normalized["fact_id"] = str(uuid4())

        # Check if this candidate is a duplicate of an existing fact
        duplicate = _find_duplicate_fact(normalized.get("statement", ""), existing_facts)
        if duplicate:
            normalized["duplicate_of"] = duplicate.get("fact_id", "")
        else:
            normalized["duplicate_of"] = None

        annotated_candidates.append(normalized)

    return annotated_candidates


# Variant similarity band — below duplicate threshold, above noise floor
_VARIANT_THRESHOLD: float = 0.5


def _find_best_match(
    candidate_statement: str, existing_facts: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, float]:
    """Return the best-matching existing fact and its similarity score.

    Scans all existing facts and returns the one with the highest similarity
    to *candidate_statement*, along with that similarity score.  If
    *existing_facts* is empty, returns ``(None, 0.0)``.

    Args:
        candidate_statement: The statement to compare.
        existing_facts: List of existing fact dicts from the database.

    Returns:
        A tuple of (best_matching_fact | None, best_similarity_score).
    """
    best_similarity = 0.0
    best_fact: dict[str, Any] | None = None
    for existing_fact in existing_facts:
        similarity = _compute_similarity(
            candidate_statement, existing_fact.get("statement", "")
        )
        if similarity > best_similarity:
            best_similarity = similarity
            best_fact = existing_fact
    return best_fact, best_similarity


async def import_resume_facts(source_resume_id: str) -> list[dict[str, Any]]:
    """Import facts from an old/legacy resume, grouping by similarity to existing facts.

    Groups:
      - new: similarity < 0.5 to all existing facts → candidate for insertion
      - variant_of: 0.5 <= similarity < 0.9 → offered as variant phrasing
      - duplicate: similarity >= 0.9 → near-duplicate, flag only

    Returns a list of dicts with shape:
      { statement, context, source, metrics_json, tags_json, confidence,
        group: "new" | "duplicate" | "variant_of",
        existing_fact_id: str | None,   # set for duplicate and variant_of
        existing_statement: str | None  # set for duplicate and variant_of
      }

    Raises HTTPException(404) if the resume is not found or has no processed_data.
    """
    # extract_candidate_facts handles 404 for missing resume / missing processed_data
    candidates = await extract_candidate_facts(source_resume_id)

    # Load all existing facts for similarity comparison
    try:
        existing_facts = await db.list_facts()
    except Exception as e:
        logger.error(
            "Failed to load existing facts for import (resume %s): %s", source_resume_id, e
        )
        existing_facts = []

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        statement = candidate.get("statement", "")

        best_fact, best_similarity = _find_best_match(statement, existing_facts)

        if best_similarity >= _SIMILARITY_THRESHOLD:
            group = "duplicate"
        elif best_similarity >= _VARIANT_THRESHOLD:
            group = "variant_of"
        else:
            group = "new"
            best_fact = None  # do not expose an existing fact for "new" items

        results.append(
            {
                **candidate,
                "group": group,
                "existing_fact_id": best_fact.get("fact_id") if best_fact else None,
                "existing_statement": best_fact.get("statement") if best_fact else None,
            }
        )

    return results


async def persist_variant_to_blocks(
    candidate_statement: str,
    existing_fact_id: str,
) -> dict[str, Any]:
    """Append a variant phrasing to master-resume block(s) that cite existing_fact_id.

    Algorithm:
    1. Load master resume and its processed_data.
    2. Scan ``summary_blocks`` and ``workExperience[*].bullet_blocks`` for any
       block whose variants include ``existing_fact_id`` in their ``fact_ids``.
    3. For each matching block: append a new ``BlockVariant`` (unless an identical
       text already exists — dedup guard).
    4. If no block cites the fact: create a new ``BulletBlock`` containing the
       new variant and append it to ``summary_blocks``.
    5. Persist the mutated ``processed_data`` back via ``db.update_resume``.

    Returns a dict ``{"status": "ok", "matched_blocks": bool}`` indicating
    whether existing blocks were found (True) or a new block was created (False).

    Raises:
        HTTPException(404): Master resume not found or has no processed_data.
        HTTPException(500): Any unexpected persistence error.
    """
    master = await db.get_master_resume()
    if master is None:
        raise HTTPException(status_code=404, detail="No master resume found.")

    processed_data = master.get("processed_data")
    if not processed_data:
        raise HTTPException(
            status_code=404,
            detail="Master resume has no processed data.",
        )

    try:
        data: dict[str, Any] = copy.deepcopy(processed_data)

        # Gather all mutable block dicts from both locations.
        # summary_blocks is a flat list; workExperience is a list of experience
        # entries, each of which has bullet_blocks.
        all_blocks: list[dict[str, Any]] = list(data.get("summary_blocks") or [])
        for exp in data.get("workExperience") or []:
            all_blocks.extend(exp.get("bullet_blocks") or [])

        matched_any = False
        for block in all_blocks:
            variants: list[dict[str, Any]] = block.get("variants") or []
            cites_fact = any(
                existing_fact_id in (v.get("fact_ids") or []) for v in variants
            )
            if not cites_fact:
                continue
            matched_any = True
            # Dedup: do not append if the same text already exists in this block.
            if any(v.get("text") == candidate_statement for v in variants):
                continue
            variants.append(
                {
                    "id": str(uuid4()),
                    "text": candidate_statement,
                    "tags": [],
                    "fact_ids": [existing_fact_id],
                }
            )
            block["variants"] = variants

        if not matched_any:
            # No existing block cites this fact — create a new block in summary_blocks.
            new_variant_id = str(uuid4())
            new_block: dict[str, Any] = {
                "id": str(uuid4()),
                "active_variant_id": new_variant_id,
                "variants": [
                    {
                        "id": new_variant_id,
                        "text": candidate_statement,
                        "tags": [],
                        "fact_ids": [existing_fact_id],
                    }
                ],
            }
            if not isinstance(data.get("summary_blocks"), list):
                data["summary_blocks"] = []
            data["summary_blocks"].append(new_block)

        await db.update_resume(master["resume_id"], {"processed_data": data})
        return {"status": "ok", "matched_blocks": matched_any}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to persist variant to blocks: %s", e)
        raise HTTPException(status_code=500, detail="Operation failed.")


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
