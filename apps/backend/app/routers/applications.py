"""Kanban application-tracker endpoints."""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.database import DuplicateConsideringError, db
from app.services.improver import extract_job_keywords
from app.schemas import (
    APPLICATION_STATUS_ORDER,
    ApplicationActionResponse,
    ApplicationDetailResponse,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationUpdate,
    BulkDelete,
    BulkStatusUpdate,
    InterestDimension,
    ManualApplicationCreate,
    QuickCaptureCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/applications", tags=["Application Tracker"])

# Cache for interest dimensions loaded from JSON
_interest_dimensions_cache: list[dict[str, str]] | None = None


def _load_interest_dimensions() -> list[dict[str, str]]:
    """Load interest dimensions from the JSON resource file."""
    global _interest_dimensions_cache
    if _interest_dimensions_cache is not None:
        return _interest_dimensions_cache

    dimensions_path = Path(__file__).parent.parent / "resources" / "interest_dimensions.json"
    try:
        with open(dimensions_path, "r") as f:
            _interest_dimensions_cache = json.load(f)
        return _interest_dimensions_cache
    except Exception as e:
        logger.error("Failed to load interest dimensions: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load interest dimensions.")


def _get_valid_dimensions() -> set[str]:
    """Get the set of valid dimension IDs."""
    dimensions = _load_interest_dimensions()
    return {d["id"] for d in dimensions}


def _group_by_status(applications: list[dict[str, Any]]) -> dict[str, list[ApplicationResponse]]:
    """Group a flat list into the seven columns (all keys always present).

    A row with an unknown status can't be represented by the enum-backed
    ``ApplicationResponse``; rather than 500 the whole board we skip it (the
    board only renders the seven known columns) and log it.
    """
    columns: dict[str, list[ApplicationResponse]] = {s: [] for s in APPLICATION_STATUS_ORDER}
    for app in applications:
        status = app.get("status")
        if status not in columns:
            logger.warning("Skipping application with unknown status %r", status)
            continue
        columns[status].append(ApplicationResponse(**app))
    return columns


@router.get("/interest-dimensions", response_model=list[InterestDimension])
async def get_interest_dimensions() -> list[InterestDimension]:
    """Get all interest dimensions for the frontend."""
    dimensions = _load_interest_dimensions()
    return [InterestDimension(**d) for d in dimensions]


@router.get("", response_model=ApplicationListResponse)
async def list_applications() -> ApplicationListResponse:
    """List all applications grouped by status column."""
    try:
        applications = await db.list_applications()
    except Exception as e:
        logger.error("Failed to list applications: %s", e)
        raise HTTPException(status_code=500, detail="Failed to load applications. Please try again.")
    return ApplicationListResponse(columns=_group_by_status(applications))


@router.post("/quick", response_model=ApplicationResponse, status_code=201)
async def quick_capture_application(request: QuickCaptureCreate) -> ApplicationResponse:
    """Quick-capture a considering card (<30 s, no tailored resume).

    Creates a Job from the pasted JD text (or reuses an existing job with
    identical content) and a considering Application with resume_id=NULL.
    Returns 409 when a considering card for this exact job already exists
    (same jd_text → same job_id → same NULL resume_id check fires).
    """
    # Reuse an existing job when the JD text is identical so that the
    # considering-card dedup check can fire on the second submission.
    existing_job = await db.get_job_by_content(request.jd_text)
    if existing_job is not None:
        job = existing_job
        created_new_job = False
    else:
        job = await db.create_job(content=request.jd_text)
        created_new_job = True

    try:
        application = await db.create_considering_application(
            job_id=job["job_id"],
            company=request.company,
            role=request.role,
        )
    except DuplicateConsideringError as e:
        logger.info("Duplicate considering application blocked: %s", e)
        # Only clean up the job if we created it this request — don't delete
        # a pre-existing job that may have other applications.
        if created_new_job:
            try:
                await db.delete_job(job["job_id"])
            except Exception as cleanup_error:
                logger.warning("Failed to clean up orphan job %s: %s", job["job_id"], cleanup_error)
        raise HTTPException(status_code=409, detail="A considering application for this job already exists.")
    except Exception as e:
        logger.error("Failed to create considering application: %s", e)
        if created_new_job:
            try:
                await db.delete_job(job["job_id"])
            except Exception as cleanup_error:
                logger.warning("Failed to clean up orphan job %s: %s", job["job_id"], cleanup_error)
        raise HTTPException(status_code=500, detail="Failed to create application. Please try again.")

    # Best-effort: cache company/role on the job for later reuse — never 500.
    company = request.company
    role = request.role
    if company or role:
        try:
            await db.update_job(job["job_id"], {"company": company, "role": role})
        except Exception as e:
            logger.warning("Failed to cache company/role on job %s: %s", job["job_id"], e)

    return ApplicationResponse(**application)


@router.post("", response_model=ApplicationResponse)
async def create_application(request: ManualApplicationCreate) -> ApplicationResponse:
    """Manually add a card from a pasted job description.

    Creates the job, runs a best-effort company/role extraction when not
    provided, then creates the application. If application creation fails the
    just-created job is cleaned up (no orphan jobs / retry drift); caching
    company/role on the job is best-effort and never fails the request.
    """
    job = await db.create_job(content=request.job_description, resume_id=request.resume_id)

    company = request.company
    role = request.role
    if not company or not role:
        extracted = await _extract_company_role(request.job_description)
        company = company or extracted.get("company")
        role = role or extracted.get("role")

    try:
        application = await db.create_application(
            job_id=job["job_id"],
            resume_id=request.resume_id,
            status=request.status.value,
            company=company,
            role=role,
            notes=request.notes,
        )
    except Exception as e:
        logger.error("Failed to create application: %s", e)
        try:
            await db.delete_job(job["job_id"])
        except Exception as cleanup_error:
            logger.warning("Failed to clean up orphan job %s: %s", job["job_id"], cleanup_error)
        raise HTTPException(status_code=500, detail="Failed to create application. Please try again.")

    # Best-effort: cache company/role on the job for later reuse — never 500.
    if company or role:
        try:
            await db.update_job(job["job_id"], {"company": company, "role": role})
        except Exception as e:
            logger.warning("Failed to cache company/role on job %s: %s", job["job_id"], e)

    return ApplicationResponse(**application)


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
async def get_application_detail(application_id: str) -> ApplicationDetailResponse:
    """Get a card with its embedded JD and applied resume (one round-trip).

    Tolerates a deleted resume by returning ``resume: null`` rather than 500.
    """
    application = await db.get_application(application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    job_content: str | None = None
    resume: dict[str, Any] | None = None
    try:
        job = await db.get_job(application["job_id"])
        if job:
            job_content = job.get("content")
        resume = await db.get_resume(application["resume_id"])
    except Exception as e:
        # Detail is best-effort beyond the card itself; never 500 the modal.
        logger.warning("Failed to load detail context for %s: %s", application_id, e)

    return ApplicationDetailResponse(**application, job_content=job_content, resume=resume)


@router.patch("/bulk", response_model=ApplicationActionResponse)
async def bulk_update_applications(request: BulkStatusUpdate) -> ApplicationActionResponse:
    """Move many cards to one column."""
    try:
        moved = await db.bulk_update_applications(request.application_ids, request.status.value)
    except Exception as e:
        logger.error("Failed to bulk-update applications: %s", e)
        raise HTTPException(status_code=500, detail="Failed to move applications. Please try again.")
    return ApplicationActionResponse(message=f"Moved {moved} application(s)", affected=moved)


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(application_id: str, request: ApplicationUpdate) -> ApplicationResponse:
    """Update a card (status/position/notes/company/role/applied_at/interest_signals)."""
    updates = request.model_dump(exclude_unset=True)
    # Normalize the enum to its stable string value for the data layer.
    if "status" in updates and updates["status"] is not None:
        updates["status"] = request.status.value

    # Validate interest signals dimensions if provided.
    if "interest_signals" in updates and updates["interest_signals"] is not None:
        valid_dimensions = _get_valid_dimensions()
        for signal in updates["interest_signals"]:
            if signal["dimension"] not in valid_dimensions:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unknown interest dimension: {signal['dimension']}",
                )

    try:
        updated = await db.update_application(application_id, updates)
    except Exception as e:
        logger.error("Failed to update application %s: %s", application_id, e)
        raise HTTPException(status_code=500, detail="Failed to update application. Please try again.")
    if updated is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationResponse(**updated)


@router.delete("/{application_id}", response_model=ApplicationActionResponse)
async def delete_application(application_id: str) -> ApplicationActionResponse:
    """Delete a card."""
    try:
        deleted = await db.delete_application(application_id)
    except Exception as e:
        logger.error("Failed to delete application %s: %s", application_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete application. Please try again.")
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
    return ApplicationActionResponse(message="Application deleted", affected=1)


@router.post("/bulk-delete", response_model=ApplicationActionResponse)
async def bulk_delete_applications(request: BulkDelete) -> ApplicationActionResponse:
    """Delete many cards."""
    try:
        deleted = await db.bulk_delete_applications(request.application_ids)
    except Exception as e:
        logger.error("Failed to bulk-delete applications: %s", e)
        raise HTTPException(status_code=500, detail="Failed to delete applications. Please try again.")
    return ApplicationActionResponse(message=f"Deleted {deleted} application(s)", affected=deleted)


async def _extract_company_role(job_description: str) -> dict[str, str | None]:
    """Best-effort company/role extraction for the manual-add path.

    Reuses the cached keyword-extraction pass; falls back to blank (editable)
    on any failure so a flaky LLM never blocks card creation. LLM output isn't
    guaranteed to be a string, so values are type-guarded before ``.strip()``.
    """
    try:
        keywords = await extract_job_keywords(job_description)
        raw_company = keywords.get("company")
        raw_role = keywords.get("role")
        return {
            "company": (raw_company.strip() if isinstance(raw_company, str) else "") or None,
            "role": (raw_role.strip() if isinstance(raw_role, str) else "") or None,
        }
    except Exception as e:
        logger.warning("Company/role extraction failed (manual add): %s", e)
        return {}
