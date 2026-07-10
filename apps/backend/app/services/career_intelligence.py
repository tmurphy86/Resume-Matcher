"""Career intelligence service (RH-304 + RH-305).

Provides two top-level async functions:

- ``cluster_jds()`` — clusters parsed JDs into named archetypes and persists
  a ``CareerReport`` skeleton (RH-304).
- ``generate_career_report()`` — computes attraction/fit scores, calls the LLM
  for a structured advice narrative, validates cited IDs, and updates the most
  recent ``CareerReport`` (RH-305).

Pure scoring helpers (``compute_attraction_score``, ``compute_fit_score``) are
deterministic: identical inputs always produce identical outputs.
"""

import logging
import re
from typing import Any

from fastapi import HTTPException

from app.config_cache import get_content_language
from app.database import db
from app.llm import complete_json, get_llm_config, get_model_name
from app.prompts.templates import (
    ARCHETYPE_CLUSTER_PROMPT,
    CAREER_ADVICE_PROMPT,
    get_language_name,
)

logger = logging.getLogger(__name__)

# Maximum number of archetypes the LLM may produce.  Gives the model useful
# headroom while keeping the output tractable.
_MAX_ARCHETYPES = 10

# ---------------------------------------------------------------------------
# Deterministic scoring helpers (pure Python, no LLM)
# ---------------------------------------------------------------------------

# Common English stop words to filter from keyword overlap matching.
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "through", "is",
        "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "could", "should", "may",
        "might", "must", "can", "we", "you", "they", "it", "that", "this",
        "as", "not", "no", "nor", "our", "their", "its", "all", "more",
        "other", "than", "also", "such", "both", "each", "any", "your",
    }
)


def _tokenize(text: str) -> set[str]:
    """Tokenize *text* into lowercase alpha-numeric tokens, filtering stop words.

    Keeps tokens of 2+ characters that are not stop words.  Splitting on word
    boundaries means tokens like ``c++``, ``c#``, and version numbers survive.

    Args:
        text: Raw text to tokenize.

    Returns:
        Set of normalised token strings.
    """
    return {
        token
        for token in re.findall(r"[a-z0-9+#]+", text.lower())
        if token not in _STOP_WORDS and len(token) >= 2
    }


def _collect_fact_cited_block_token_sets(
    processed_data: dict[str, Any],
) -> list[set[str]]:
    """Extract tokenised text from all fact-cited block variants in *processed_data*.

    Iterates ``summary_blocks``, ``workExperience[*].bullet_blocks``, and
    ``personalProjects[*].bullet_blocks``.  Only variants with a non-empty
    ``fact_ids`` list are included — these are the provenance-backed claims.

    Args:
        processed_data: The ``processed_data`` dict from a master resume.

    Returns:
        List of token sets, one per fact-cited block variant (non-empty sets only).
    """
    result: list[set[str]] = []

    def _process_blocks(blocks: list[Any]) -> None:
        for block in blocks:
            if not isinstance(block, dict):
                continue
            for variant in (block.get("variants") or []):
                if not isinstance(variant, dict):
                    continue
                if variant.get("fact_ids"):
                    text = variant.get("text") or ""
                    tokens = _tokenize(text)
                    if tokens:
                        result.append(tokens)

    _process_blocks(processed_data.get("summary_blocks") or [])
    for exp in (processed_data.get("workExperience") or []):
        if isinstance(exp, dict):
            _process_blocks(exp.get("bullet_blocks") or [])
    for proj in (processed_data.get("personalProjects") or []):
        if isinstance(proj, dict):
            _process_blocks(proj.get("bullet_blocks") or [])

    return result


def compute_attraction_score(
    applications: list[dict[str, Any]],
    archetype_jd_ids: list[str],
) -> float:
    """Compute the attraction score for one archetype.

    Attraction = mean weight across all ``interest_signals`` in all member
    applications (applications whose ``job_id`` is in *archetype_jd_ids*).
    If there are no member applications or none have signals, returns 0.0.

    The result is deterministic: identical inputs produce identical output.

    Args:
        applications: All application dicts (each may have ``interest_signals``).
        archetype_jd_ids: Job IDs belonging to this archetype.

    Returns:
        Mean signal weight in [0.0, 5.0], or 0.0 if no signals.
    """
    member_ids: set[str] = set(archetype_jd_ids)
    weights: list[float] = []
    for app in applications:
        if app.get("job_id") not in member_ids:
            continue
        for signal in (app.get("interest_signals") or []):
            if not isinstance(signal, dict):
                continue
            w = signal.get("weight")
            if isinstance(w, (int, float)):
                weights.append(float(w))
    return sum(weights) / len(weights) if weights else 0.0


def compute_fit_score(
    processed_data: dict[str, Any],
    requirements: list[str],
) -> tuple[float, list[str]]:
    """Compute the fit score and gap list for one archetype.

    Fit = fraction of *requirements* that are "covered" by the master resume.
    A requirement is covered when at least one fact-cited block variant's text
    shares a keyword token with the requirement (after stop-word removal).

    If *requirements* is empty, fit = 1.0 with no gaps.

    The result is deterministic: identical inputs produce identical output.

    Args:
        processed_data: The ``processed_data`` dict from the master resume.
        requirements: List of requirement strings from the archetype's member JDs.

    Returns:
        Tuple of (fit_score, gap_list) where fit_score ∈ [0.0, 1.0] and
        gap_list is the subset of requirements that had no supporting fact.
    """
    if not requirements:
        return 1.0, []

    block_token_sets = _collect_fact_cited_block_token_sets(processed_data)

    covered = 0
    gaps: list[str] = []
    for req in requirements:
        req_tokens = _tokenize(req)
        if not req_tokens:
            # Empty after stop-word removal — treat as covered (nothing to miss).
            covered += 1
            continue
        matched = any(req_tokens & block_tokens for block_tokens in block_token_sets)
        if matched:
            covered += 1
        else:
            gaps.append(req)

    return covered / len(requirements), gaps


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


# ---------------------------------------------------------------------------
# Advice narrative helpers
# ---------------------------------------------------------------------------


def _build_archetypes_scores_block(
    archetypes: list[dict[str, Any]],
    scores: dict[str, dict[str, Any]],
) -> str:
    """Format archetypes + scores into a text block for the advice prompt.

    Args:
        archetypes: List of archetype dicts from the CareerReport.
        scores: Mapping of archetype name → score dict (attraction, fit, gaps).

    Returns:
        Formatted multi-line string for prompt injection.
    """
    lines: list[str] = []
    for arch in archetypes:
        name: str = arch.get("name", "Unknown")
        score = scores.get(name, {})
        lines.append(f"--- ARCHETYPE: {name} ---")
        lines.append(f"Description: {arch.get('description', '')}")
        lines.append(f"Attraction Score: {score.get('attraction', 0.0):.2f} / 5.0")
        lines.append(f"Fit Score: {score.get('fit', 0.0):.0%}")
        gaps: list[str] = score.get("gaps") or []
        if gaps:
            lines.append("Coverage gaps (requirements not backed by resume facts):")
            for gap in gaps:
                lines.append(f"  - {gap}")
        jd_ids: list[str] = arch.get("jd_ids") or []
        if jd_ids:
            lines.append(f"JD IDs: {', '.join(jd_ids)}")
        lines.append("")
    return "\n".join(lines)


def _validate_narrative_result(result: Any) -> dict[str, Any]:
    """Validate the LLM narrative result structure.

    Args:
        result: Raw value returned by ``complete_json``.

    Returns:
        The validated narrative dict.

    Raises:
        ValueError: When the structure is missing required keys or wrong type.
    """
    if not isinstance(result, dict):
        raise ValueError(f"LLM returned {type(result).__name__} instead of dict")
    required_keys = {"target", "stretch", "deprioritize", "market_observations"}
    missing = required_keys - result.keys()
    if missing:
        raise ValueError(f"Narrative missing required keys: {missing}")
    return result


def _narrative_to_markdown(narrative: dict[str, Any]) -> str:
    """Convert the structured LLM narrative to a Markdown string.

    Args:
        narrative: Validated narrative dict from the LLM.

    Returns:
        Markdown-formatted advice string.
    """
    sections: list[str] = []

    target: list[Any] = narrative.get("target") or []
    if target:
        lines = ["## Target Roles"]
        for item in target:
            name = item if isinstance(item, str) else item.get("name", "")
            if name:
                lines.append(f"- **{name}**")
        sections.append("\n".join(lines))

    stretch: list[Any] = narrative.get("stretch") or []
    if stretch:
        lines = ["## Stretch Opportunities"]
        for item in stretch:
            if isinstance(item, str):
                lines.append(f"- **{item}**")
            else:
                name = item.get("name", "")
                plan = item.get("gap_closing_plan") or ""
                if name:
                    lines.append(f"- **{name}**: {plan}" if plan else f"- **{name}**")
        sections.append("\n".join(lines))

    deprioritize: list[Any] = narrative.get("deprioritize") or []
    if deprioritize:
        lines = ["## Deprioritize"]
        for item in deprioritize:
            name = item if isinstance(item, str) else item.get("name", "")
            if name:
                lines.append(f"- {name}")
        sections.append("\n".join(lines))

    market_obs: str = narrative.get("market_observations") or ""
    if market_obs:
        sections.append(f"## Market Observations\n{market_obs}")

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# generate_career_report — RH-305 main entry point
# ---------------------------------------------------------------------------


async def generate_career_report() -> dict[str, Any]:
    """Compute scores + LLM advice narrative and update the most recent CareerReport.

    Steps:
    1. Fetch the most recent CareerReport (created by clustering).
    2. Fetch all applications, jobs, and the master resume.
    3. Compute attraction and fit scores per archetype (deterministic).
    4. Call the LLM for a structured advice narrative.
    5. Validate that every cited fact_id and jd_id exists in the DB.
       Invalid citations → ``advice_md`` set to an error marker; report still
       persisted.
    6. Convert the narrative to Markdown.
    7. Update the CareerReport with ``scores_json``, ``advice_md``,
       ``model_used``.
    8. Return the updated report.

    Raises:
        HTTPException(400): No master resume, or no career reports available.
        HTTPException(500): LLM call failed, returned malformed output, or DB
                            update failed.
    """
    # --- 1. Fetch the most recent CareerReport ---
    reports = await db.get_career_reports()
    if not reports:
        raise HTTPException(
            status_code=400,
            detail="No career reports found. Run JD clustering first.",
        )
    report = reports[0]  # ordered by id DESC; first = most recent
    archetypes: list[dict[str, Any]] = report.get("archetypes_json") or []

    # --- 2. Fetch supporting data ---
    all_jobs: list[dict[str, Any]] = await db.list_jobs()
    all_applications: list[dict[str, Any]] = await db.list_applications()
    master_resume = await db.get_master_resume()
    if not master_resume:
        raise HTTPException(
            status_code=400,
            detail="No master resume found. Upload a master resume first.",
        )
    processed_data: dict[str, Any] = master_resume.get("processed_data") or {}

    # Build job_id → requirements mapping from parsed metadata.
    job_requirements: dict[str, list[str]] = {}
    for job in all_jobs:
        parsed: dict[str, Any] = job.get("parsed") or {}
        job_requirements[job["job_id"]] = parsed.get("requirements") or []

    # --- 3. Compute per-archetype scores ---
    scores: dict[str, dict[str, Any]] = {}
    for arch in archetypes:
        arch_name: str = arch.get("name", "")
        jd_ids: list[str] = arch.get("jd_ids") or []

        attraction = compute_attraction_score(all_applications, jd_ids)

        # Aggregate requirements from all member JDs.
        all_reqs: list[str] = []
        for jid in jd_ids:
            all_reqs.extend(job_requirements.get(jid) or [])

        fit, gaps = compute_fit_score(processed_data, all_reqs)

        scores[arch_name] = {
            "attraction": round(attraction, 4),
            "fit": round(fit, 4),
            "gaps": gaps,
        }

    # --- 4. Build and send advice prompt ---
    language_code = get_content_language()
    output_language = get_language_name(language_code)
    archetypes_block = _build_archetypes_scores_block(archetypes, scores)
    prompt = CAREER_ADVICE_PROMPT.format(
        archetypes_with_scores=archetypes_block,
        output_language=output_language,
    )

    try:
        raw_result = await complete_json(prompt, schema_type="keywords")
    except Exception as exc:
        logger.error("Career advice LLM call failed: %s", exc)
        raise HTTPException(status_code=500, detail="Career intelligence failed.")

    # --- 5. Validate structure ---
    try:
        narrative = _validate_narrative_result(raw_result)
    except ValueError as exc:
        logger.error("Career advice: malformed LLM output — %s", exc)
        raise HTTPException(status_code=500, detail="Career intelligence failed.")

    # --- 5b. Validate cited IDs ---
    cited_fact_ids: list[str] = narrative.get("cited_fact_ids") or []
    cited_jd_ids: list[str] = narrative.get("cited_jd_ids") or []

    all_facts = await db.list_facts()
    valid_fact_ids: set[str] = {f["fact_id"] for f in all_facts}
    valid_jd_ids: set[str] = {j["job_id"] for j in all_jobs}

    invalid_fact_ids = set(cited_fact_ids) - valid_fact_ids
    invalid_jd_ids = set(cited_jd_ids) - valid_jd_ids

    if invalid_fact_ids or invalid_jd_ids:
        logger.error(
            "Career advice: invalid cited IDs — fact_ids=%s jd_ids=%s",
            sorted(invalid_fact_ids),
            sorted(invalid_jd_ids),
        )
        advice_md = "[CITATION ERROR: invalid IDs cited]"
    else:
        # --- 6. Convert to Markdown ---
        advice_md = _narrative_to_markdown(narrative)

    # --- 7. Determine model used ---
    try:
        config = get_llm_config()
        model_used: str | None = get_model_name(config)
    except Exception as exc:
        logger.warning("Could not determine model name: %s", exc)
        model_used = None

    # --- 8. Persist ---
    updated = await db.update_career_report(
        report_id=report["id"],
        scores_json=scores,
        advice_md=advice_md,
        model_used=model_used,
    )
    if updated is None:
        logger.error("Career report %s not found during update", report["id"])
        raise HTTPException(status_code=500, detail="Career intelligence failed.")

    logger.info(
        "Career report %s updated: scores for %d archetypes, advice_md=%d chars",
        updated["id"],
        len(archetypes),
        len(advice_md),
    )
    return updated
