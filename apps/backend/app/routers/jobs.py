"""Job description management endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from app.database import db
from app.schemas import JobUploadRequest, JobUploadResponse
from app.services.jd_parser import backfill_parse_jobs, parse_job_description

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/upload", response_model=JobUploadResponse)
async def upload_job_descriptions(request: JobUploadRequest) -> JobUploadResponse:
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

        # Best-effort parse — errors are logged inside parse_job_description,
        # never raised here so the upload always succeeds.
        await parse_job_description(job["job_id"], jd.strip())

    return JobUploadResponse(
        message="data successfully processed",
        job_id=job_ids,
        request={
            "job_descriptions": request.job_descriptions,
            "resume_id": request.resume_id,
        },
    )


@router.post("/backfill-parse")
async def backfill_parse() -> dict:
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


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    """Get job description by ID."""
    job = await db.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job
