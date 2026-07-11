"""Job description management endpoints."""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.database import db
from app.schemas import JobUploadRequest, JobUploadResponse, JobSummary
from app.services.jd_parser import backfill_parse_jobs, parse_job_description

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/upload", response_model=JobUploadResponse)
async def upload_job_descriptions(
    request: JobUploadRequest, background_tasks: BackgroundTasks
) -> JobUploadResponse:
    """Upload one or more job descriptions.

    Stores the raw text for later use in resume tailoring.
    Returns an array of job_ids corresponding to the input array.
    Triggers structured JD parsing for each uploaded job (best-effort;
    parse failures are logged but never block the upload response).
    """
    if not request.job_descriptions:
        raise HTTPException(status_code=400, detail="No job descriptions provided")

    job_ids = []
    for jd in request.job_descriptions:
        if not jd.strip():
            raise HTTPException(status_code=400, detail="Empty job description")

        job = await db.create_job(
            content=jd.strip(),
            resume_id=request.resume_id,
        )
        job_ids.append(job["job_id"])

        # Best-effort parse — deferred to a background task so N JD uploads are
        # not serialised into N sequential LLM round-trips before responding.
        # Errors are logged inside parse_job_description; the upload always succeeds.
        background_tasks.add_task(parse_job_description, job["job_id"], jd.strip())

    return JobUploadResponse(
        message="data successfully processed",
        job_id=job_ids,
        request={
            "job_descriptions": request.job_descriptions,
            "resume_id": request.resume_id,
        },
    )


@router.post("/backfill-parse")
async def backfill_parse() -> dict[str, Any]:
    """Parse all jobs that do not yet have structured parsed data.

    Idempotent — jobs that already have ``parsed`` in their metadata are
    skipped.  Runs synchronously in the request; for very large job tables
    this may take a while.

    Returns a summary with counts: total, skipped, parsed, failed.
    """
    try:
        summary = await backfill_parse_jobs()
    except Exception as exc:
        logger.error(f"Backfill parse failed: {exc}")
        raise HTTPException(status_code=500, detail="Backfill parse failed. Please try again.")
    return summary


@router.get("", response_model=list[JobSummary])
async def list_jobs(
    q: str | None = None,
    archetype: str | None = None,
) -> list[JobSummary]:
    """List all job descriptions with optional text search and archetype filter.

    - ``q``: case-insensitive substring match against raw JD content.
    - ``archetype``: case-insensitive exact match on archetype name from the
      latest career report (jobs without an archetype assignment are excluded
      when this filter is active).
    """
    try:
        jobs = await db.list_jobs()
    except Exception as exc:
        logger.error(f"Failed to list jobs: {exc}")
        raise HTTPException(status_code=500, detail="Failed to list jobs. Please try again.")

    # Build job_id -> archetype_name map from the latest career report.
    archetype_map: dict[str, str] = {}
    try:
        reports = await db.get_career_reports()
        if reports:
            latest = reports[0]
            for arch in latest.get("archetypes_json") or []:
                arch_name: str = arch.get("name", "")
                for jid in arch.get("jd_ids") or []:
                    archetype_map[jid] = arch_name
    except Exception as exc:
        logger.warning(f"Could not load career reports for archetype lookup: {exc}")

    summaries: list[JobSummary] = []
    for job in jobs:
        content: str = job.get("content", "")

        # Text filter
        if q and q.lower() not in content.lower():
            continue

        # Parsed fields from metadata_json["parsed"]
        parsed: dict = {}
        if isinstance(job.get("parsed"), dict):
            parsed = job["parsed"]

        job_archetype = archetype_map.get(job["job_id"])

        # Archetype filter
        if archetype and (job_archetype or "").lower() != archetype.lower():
            continue

        summaries.append(
            JobSummary(
                job_id=job["job_id"],
                snippet=content[:200],
                created_at=job.get("created_at", ""),
                company=parsed.get("company") or job.get("company"),
                role=parsed.get("role") or job.get("role"),
                level=parsed.get("level"),
                archetype=job_archetype,
            )
        )

    return summaries


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    """Get job description by ID, including parsed fields and linked application IDs."""
    job = await db.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Attach linked application IDs so the frontend can link to the tracker.
    try:
        applications = await db.list_applications()
        job["application_ids"] = [
            a["application_id"]
            for a in applications
            if a.get("job_id") == job_id
        ]
    except Exception as exc:
        logger.warning(f"Could not load applications for job {job_id}: {exc}")
        job["application_ids"] = []

    return job
