"""Anti-hallucination gap Q&A loop service.

This is DISTINCT from interview_prep.py (which generates structured interview
questions about a job role). This service drives the provenance loop: identify
JD requirements not covered by existing facts, generate targeted questions that
would elicit verifiable evidence, and persist human answers as new facts.
"""

import logging
import re
from typing import Any

from fastapi import HTTPException

from app.database import db
from app.llm import complete_json
from app.prompts.interview_mode import GAP_QUESTIONS_PROMPT
from app.services.improver import _format_facts_for_prompt, extract_job_keywords

logger = logging.getLogger(__name__)

# Metric pattern for extracting numbers/percentages/dollar amounts from answers.
_METRIC_RE = re.compile(r"(\d+%|\d+x|\$[\d,.]+[BMK]?|\d+[\d,.]*\s*(?:million|billion|thousand|M|B|K)?)")


def _extract_metrics_from_answer(answer: str) -> dict[str, Any]:
    """Extract numeric metrics from a free-text answer.

    Looks for patterns like "40%", "3x", "$2M", "500K". Returns a dict
    with metric strings keyed by position, or an empty dict if none found.

    Args:
        answer: Human-written answer text.

    Returns:
        Dict mapping ``"metric_N"`` to found metric strings, or ``{}``.
    """
    matches = _METRIC_RE.findall(answer)
    if not matches:
        return {}
    return {f"metric_{i}": m.strip() for i, m in enumerate(matches)}


def _format_uncovered_bullets(resume_data: dict[str, Any]) -> str:
    """Extract bullets/summary text from a resume that have no provenance tracking.

    For resumes that have already migrated to bullet_blocks this returns blocks
    with no fact_ids. For legacy resumes (plain description lists) it returns
    all bullets as uncovered.

    Args:
        resume_data: Raw resume ``processed_data`` dict.

    Returns:
        Newline-separated list of bullet texts, or ``"None"`` if empty.
    """
    lines: list[str] = []

    # Summary
    summary_blocks = resume_data.get("summary_blocks", [])
    if summary_blocks:
        for block in summary_blocks:
            active_id = block.get("active_variant_id")
            for variant in block.get("variants", []):
                if variant.get("id") == active_id and not variant.get("fact_ids"):
                    text = variant.get("text", "").strip()
                    if text:
                        lines.append(f"[summary] {text}")
    else:
        summary = resume_data.get("summary", "").strip()
        if summary:
            lines.append(f"[summary] {summary}")

    # Work experience
    for exp in resume_data.get("workExperience", []):
        if not isinstance(exp, dict):
            continue
        label = f"{exp.get('title', '')} @ {exp.get('company', '')}".strip(" @")
        bullet_blocks = exp.get("bullet_blocks", [])
        if bullet_blocks:
            for block in bullet_blocks:
                active_id = block.get("active_variant_id")
                for variant in block.get("variants", []):
                    if variant.get("id") == active_id and not variant.get("fact_ids"):
                        text = variant.get("text", "").strip()
                        if text:
                            lines.append(f"[{label}] {text}")
        else:
            for bullet in exp.get("description", []):
                if isinstance(bullet, str) and bullet.strip():
                    lines.append(f"[{label}] {bullet.strip()}")

    return "\n".join(lines) if lines else "None"


def _build_jd_gaps(
    job_keywords: dict[str, Any],
    facts: list[dict[str, Any]],
) -> str:
    """Identify JD requirements not covered by any existing fact.

    Compares required and preferred skills from the extracted keywords against
    the text of all verified facts. Returns a formatted string listing the
    uncovered gaps.

    Args:
        job_keywords: Extracted keywords dict (output of ``extract_job_keywords``).
        facts: List of fact dicts from ``db.list_facts()``.

    Returns:
        Newline-separated list of uncovered JD requirements, or
        ``"No specific gaps identified."`` when all requirements are covered.
    """
    all_fact_text = " ".join(f.get("statement", "") for f in facts).lower()

    gaps: list[str] = []

    for field, label in [
        ("required_skills", "required skill"),
        ("preferred_skills", "preferred skill"),
        ("key_responsibilities", "responsibility"),
    ]:
        items = job_keywords.get(field, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, str) or not item.strip():
                continue
            # Simple substring check — a token of the requirement appears in any fact
            item_lower = item.strip().lower()
            if item_lower not in all_fact_text:
                gaps.append(f"- [{label}] {item.strip()}")

    return "\n".join(gaps) if gaps else "No specific gaps identified."


async def get_gap_questions(
    job_id: str,
    resume_id: str,
) -> list[dict[str, Any]]:
    """Generate structured questions for JD requirements not covered by existing facts.

    Flow:
    1. Load job → get job_description
    2. Load resume → get processed_data
    3. Load existing facts
    4. Extract job keywords (or reuse cached result from job metadata)
    5. Identify gaps: JD keywords not supported by any fact
    6. Call LLM to generate structured gap questions
    7. Return list of {question, gap_type, jd_keyword}

    Args:
        job_id: ID of the target job.
        resume_id: ID of the candidate's resume.

    Returns:
        List of question dicts with ``question``, ``gap_type``, and ``jd_keyword``.

    Raises:
        HTTPException(404): If job or resume is not found or has no processed data.
        HTTPException(500): On unexpected LLM or DB errors.
    """
    # Load job
    job = await db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    job_description: str = job.get("content", "")
    if not job_description:
        raise HTTPException(status_code=404, detail="Job has no description.")

    # Load resume
    resume = await db.get_resume(resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")

    processed_data: dict[str, Any] | None = resume.get("processed_data")
    if not processed_data:
        raise HTTPException(status_code=404, detail="Resume has not been processed yet.")

    # Load existing facts
    try:
        facts = await db.list_facts()
    except Exception as e:
        logger.error("Failed to load facts for gap analysis: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load facts. Please try again.")

    # Extract job keywords (use cached from job metadata if available)
    try:
        job_keywords_raw = job.get("keywords")
        if isinstance(job_keywords_raw, dict) and job_keywords_raw:
            job_keywords: dict[str, Any] = job_keywords_raw
        else:
            job_keywords = await extract_job_keywords(job_description)
    except Exception as e:
        logger.error("Failed to extract job keywords: %s", e)
        raise HTTPException(status_code=500, detail="Failed to analyze job description. Please try again.")

    # Build prompt sections
    jd_gaps = _build_jd_gaps(job_keywords, facts)
    facts_section = _format_facts_for_prompt(facts)
    uncovered_bullets = _format_uncovered_bullets(processed_data)

    prompt = GAP_QUESTIONS_PROMPT.format(
        jd_gaps=jd_gaps,
        facts_section=facts_section,
        uncovered_bullets=uncovered_bullets,
    )

    try:
        result = await complete_json(
            prompt=prompt,
            system_prompt=(
                "You are a career coach generating targeted interview questions. "
                "Output only valid JSON."
            ),
            max_tokens=2048,
            schema_type="keywords",
        )
    except Exception as e:
        logger.error("LLM call failed for gap questions: %s", e)
        raise HTTPException(status_code=500, detail="Failed to generate questions. Please try again.")

    raw_questions = result.get("questions", [])
    if not isinstance(raw_questions, list):
        logger.warning("LLM returned non-list questions: %s", type(raw_questions))
        raw_questions = []

    questions: list[dict[str, Any]] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        question_text = str(item.get("question", "")).strip()
        gap_type = str(item.get("gap_type", "achievement")).strip()
        jd_keyword = str(item.get("jd_keyword", "")).strip()
        if question_text:
            questions.append(
                {
                    "question": question_text,
                    "gap_type": gap_type,
                    "jd_keyword": jd_keyword,
                }
            )

    return questions


async def answer_gap_question(
    question: str,
    answer: str,
    job_id: str,
    resume_id: str,
) -> dict[str, Any]:
    """Persist a human answer as a verified fact and return updated gap list.

    The answer is stored as a new fact with:
    - ``confidence = "user_answered"``
    - ``source = "interview"``
    - ``context = job_id`` (ties the fact to the target job)
    - ``tags_json = ["interview", "user_answered"]``
    - ``metrics_json`` extracted from any numeric patterns in the answer

    Then re-runs ``get_gap_questions`` to return the refreshed gap list so the
    caller can drive a multi-turn Q&A session.

    Args:
        question: The question that was asked.
        answer: The human's answer text.
        job_id: ID of the target job (used as ``context``).
        resume_id: ID of the candidate's resume (needed for gap refresh).

    Returns:
        Dict with ``fact`` (the persisted fact dict) and ``gap_questions``
        (refreshed list of remaining gap question dicts).

    Raises:
        HTTPException(404): If job or resume is not found.
        HTTPException(500): On DB or LLM errors.
    """
    # Extract metrics from the answer text
    metrics = _extract_metrics_from_answer(answer)

    # Persist the answer as a fact
    try:
        fact = await db.create_fact(
            statement=answer.strip(),
            context=job_id,
            source="interview",
            metrics_json=metrics,
            tags_json=["interview", "user_answered"],
            confidence="user_answered",
        )
    except Exception as e:
        logger.error("Failed to persist answer as fact: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save your answer. Please try again.")

    logger.info(
        "Persisted interview answer as fact %s (job=%s, resume=%s)",
        fact.get("fact_id"),
        job_id,
        resume_id,
    )

    # Refresh gap questions with the new fact now in the DB
    try:
        updated_gaps = await get_gap_questions(job_id=job_id, resume_id=resume_id)
    except HTTPException:
        # If the gap refresh fails (e.g. LLM blip), still return the persisted fact
        logger.warning("Gap refresh failed after answer; returning empty gap list.")
        updated_gaps = []

    return {
        "fact": fact,
        "gap_questions": updated_gaps,
    }
