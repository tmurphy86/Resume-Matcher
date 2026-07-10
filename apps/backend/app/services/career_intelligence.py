"""Service for clustering parsed JDs into named role archetypes (RH-304).

Reads all jobs that have ``metadata_json["parsed"]``, sends their
responsibilities + requirements to the LLM for clustering, validates that
every job ID appears in exactly one archetype, and persists a
``CareerReport`` skeleton (scores/advice/model_used = None; filled by Task 6).
"""

import logging
from typing import Any

from fastapi import HTTPException

from app.config_cache import get_content_language
from app.database import db
from app.llm import complete_json
from app.prompts.templates import ARCHETYPE_CLUSTER_PROMPT, get_language_name

logger = logging.getLogger(__name__)

# Maximum number of archetypes the LLM may produce.  Gives the model useful
# headroom while keeping the output tractable.
_MAX_ARCHETYPES = 10


def _build_job_descriptions_block(jobs: list[dict[str, Any]]) -> str:
    """Format parsed jobs into a text block for the clustering prompt.

    Each entry shows the job ID, level/comp hints, and the parsed
    responsibilities/requirements so the LLM has enough signal to cluster.
    """
    lines: list[str] = []
    for job in jobs:
        parsed: dict[str, Any] = job.get("parsed") or {}
        job_id: str = job["job_id"]
        level: str | None = parsed.get("level")
        comp: str | None = parsed.get("comp")
        resp: list[str] = parsed.get("responsibilities") or []
        reqs: list[str] = parsed.get("requirements") or []

        lines.append(f"--- JOB ID: {job_id} ---")
        if level:
            lines.append(f"Level: {level}")
        if comp:
            lines.append(f"Comp: {comp}")
        if resp:
            lines.append("Responsibilities:")
            for r in resp:
                lines.append(f"  - {r}")
        if reqs:
            lines.append("Requirements:")
            for r in reqs:
                lines.append(f"  - {r}")
        lines.append("")

    return "\n".join(lines)


def _validate_clustering_result(
    result: Any,
    expected_job_ids: set[str],
) -> list[dict[str, Any]]:
    """Validate the LLM clustering result.

    Returns the list of archetype dicts if valid.  Raises ``ValueError`` with a
    descriptive message if:
    - ``result`` is not a dict with an ``archetypes`` key
    - any archetype entry is missing required keys
    - not every expected job ID appears in exactly one archetype
    - a job ID appears in more than one archetype (duplicate assignment)

    Args:
        result: Raw value returned by ``complete_json``.
        expected_job_ids: Set of all job IDs that were sent to the LLM.

    Returns:
        The validated list of archetype dicts.
    """
    if not isinstance(result, dict):
        raise ValueError(f"LLM returned {type(result).__name__} instead of dict")

    archetypes = result.get("archetypes")
    if not isinstance(archetypes, list):
        raise ValueError("LLM result missing 'archetypes' list")

    required_keys = {"name", "description", "jd_ids", "responsibilities"}
    for i, arch in enumerate(archetypes):
        if not isinstance(arch, dict):
            raise ValueError(f"archetypes[{i}] is not a dict")
        missing = required_keys - arch.keys()
        if missing:
            raise ValueError(f"archetypes[{i}] missing keys: {missing}")
        if not isinstance(arch["jd_ids"], list):
            raise ValueError(f"archetypes[{i}].jd_ids is not a list")

    # Every expected job ID must appear in exactly one archetype.
    seen: dict[str, int] = {}  # job_id -> archetype index
    for i, arch in enumerate(archetypes):
        for jid in arch["jd_ids"]:
            if jid in seen:
                raise ValueError(
                    f"job_id '{jid}' appears in multiple archetypes "
                    f"(indices {seen[jid]} and {i})"
                )
            seen[jid] = i

    assigned = set(seen.keys())

    # Check for invented IDs first — if the LLM used IDs we never sent it,
    # that's the root cause and the more actionable error to surface.
    extra_ids = assigned - expected_job_ids
    if extra_ids:
        raise ValueError(
            f"LLM invented {len(extra_ids)} job ID(s) not in the input: "
            f"{sorted(extra_ids)[:5]}{'...' if len(extra_ids) > 5 else ''}"
        )

    missing_ids = expected_job_ids - assigned
    if missing_ids:
        raise ValueError(
            f"{len(missing_ids)} job ID(s) not assigned to any archetype: "
            f"{sorted(missing_ids)[:5]}{'...' if len(missing_ids) > 5 else ''}"
        )

    return archetypes


async def cluster_jds() -> dict[str, Any]:
    """Cluster all parsed JDs into named archetypes and persist a CareerReport.

    Steps:
    1. Fetch all jobs that have ``metadata_json["parsed"]``.
    2. Build a prompt block from their responsibilities/requirements.
    3. Call the LLM for clustering.
    4. Validate that every job ID is assigned to exactly one archetype.
    5. Persist a ``CareerReport`` (scores/advice/model_used = None).
    6. Return the report dict.

    Raises:
        HTTPException(400): No parsed jobs available to cluster.
        HTTPException(500): LLM call failed or returned malformed output.
    """
    # --- 1. Gather parsed jobs ---
    all_jobs: list[dict[str, Any]] = await db.list_jobs()
    parsed_jobs = [j for j in all_jobs if j.get("parsed")]

    if not parsed_jobs:
        raise HTTPException(
            status_code=400,
            detail="No parsed job descriptions found. Run JD parsing first.",
        )

    expected_ids: set[str] = {j["job_id"] for j in parsed_jobs}

    # --- 2. Build prompt ---
    language_code = get_content_language()
    output_language = get_language_name(language_code)
    jd_block = _build_job_descriptions_block(parsed_jobs)

    prompt = ARCHETYPE_CLUSTER_PROMPT.format(
        output_language=output_language,
        max_archetypes=_MAX_ARCHETYPES,
        job_descriptions_block=jd_block,
    )

    # --- 3. Call LLM ---
    try:
        raw_result = await complete_json(prompt, schema_type="keywords")
    except Exception as exc:
        logger.error("Career clustering LLM call failed: %s", exc)
        raise HTTPException(status_code=500, detail="Career intelligence failed.")

    # --- 4. Validate ---
    try:
        archetypes = _validate_clustering_result(raw_result, expected_ids)
    except ValueError as exc:
        logger.error("Career clustering: malformed LLM output — %s", exc)
        raise HTTPException(status_code=500, detail="Career intelligence failed.")

    # --- 5. Persist ---
    jd_ids_list = sorted(expected_ids)
    report = await db.create_career_report(
        archetypes_json=archetypes,
        jd_ids_json=jd_ids_list,
        scores_json=None,
        advice_md=None,
        model_used=None,
    )

    logger.info(
        "Career report %s created: %d archetypes for %d JDs",
        report["id"],
        len(archetypes),
        len(jd_ids_list),
    )

    # --- 6. Return ---
    return report
