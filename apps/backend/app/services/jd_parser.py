"""Service for parsing job descriptions into structured fields."""

import copy
import logging
from typing import Any

from app.config_cache import get_content_language
from app.database import db
from app.llm import complete_json
from app.prompts.templates import JD_PARSE_PROMPT, get_language_name

logger = logging.getLogger(__name__)


async def parse_job_description(job_id: str, job_content: str) -> dict[str, Any] | None:
    """Parse a job description and store the result in metadata_json["parsed"].

    Calls the LLM to extract structured fields (responsibilities, requirements,
    level, comp) and merges the result into the job's metadata_json.  If the
    LLM returns malformed output the error is logged and the job is left
    without a ``parsed`` key — the upload is never blocked.

    Args:
        job_id: The ID of the job record to update.
        job_content: The raw JD text to parse.

    Returns:
        The parsed dict on success, or None if parsing failed.
    """
    language_code = get_content_language()
    output_language = get_language_name(language_code)

    prompt = JD_PARSE_PROMPT.format(
        output_language=output_language,
        job_description=job_content,
    )

    try:
        result = await complete_json(prompt, schema_type="keywords")
    except Exception as exc:
        logger.error(f"JD parse LLM call failed for job {job_id}: {exc}")
        return None

    # Validate the LLM response has the expected structure.
    if not isinstance(result, dict):
        logger.error(
            f"JD parse returned non-dict for job {job_id}: type={type(result).__name__}"
        )
        return None

    parsed: dict[str, Any] = {
        "responsibilities": result.get("responsibilities") if isinstance(result.get("responsibilities"), list) else [],
        "requirements": result.get("requirements") if isinstance(result.get("requirements"), list) else [],
        "level": result.get("level") if isinstance(result.get("level"), str) else None,
        "comp": result.get("comp") if isinstance(result.get("comp"), str) else None,
    }

    try:
        job = await db.get_job(job_id)
        if job is None:
            logger.error(f"JD parse: job {job_id} not found when saving parsed result")
            return None

        # Read → merge → write (ADR-005 dynamic-key pattern).
        existing_meta = copy.deepcopy(job)
        existing_meta["parsed"] = parsed
        await db.update_job(job_id, {"parsed": parsed})
    except Exception as exc:
        logger.error(f"JD parse failed to persist parsed result for job {job_id}: {exc}")
        return None

    return parsed


async def backfill_parse_jobs() -> dict[str, Any]:
    """Parse all jobs that do not yet have a ``parsed`` key in metadata_json.

    Iterates every job, skips those where ``metadata_json.get("parsed")``
    is already set, and calls :func:`parse_job_description` for the rest.
    This operation is idempotent — running it multiple times is safe.

    Returns:
        A summary dict with counts: ``{"total": int, "skipped": int,
        "parsed": int, "failed": int}``.
    """
    all_jobs = await db.list_jobs()

    total = len(all_jobs)
    skipped = 0
    parsed_count = 0
    failed = 0

    for job in all_jobs:
        job_id: str = job["job_id"]

        # Skip jobs that already have parsed data.
        if job.get("parsed"):
            skipped += 1
            continue

        result = await parse_job_description(job_id, job.get("content", ""))
        if result is not None:
            parsed_count += 1
        else:
            failed += 1

    logger.info(
        f"JD backfill complete: total={total} skipped={skipped} "
        f"parsed={parsed_count} failed={failed}"
    )
    return {
        "total": total,
        "skipped": skipped,
        "parsed": parsed_count,
        "failed": failed,
    }
