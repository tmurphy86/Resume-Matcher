"""Career intelligence API endpoints (RH-304)."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.database import db
from app.services import career_intelligence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/career", tags=["Career Intelligence"])


@router.post("/cluster", status_code=201)
async def cluster_jds() -> dict[str, Any]:
    """Cluster all parsed JDs into named role archetypes.

    Fetches every job that has a ``parsed`` key in its metadata, sends their
    responsibilities and requirements to the LLM for clustering, validates the
    result, persists a ``CareerReport`` (scores/advice = null; filled by
    Task 6), and returns the report.

    Returns:
        The persisted CareerReport as a JSON object.

    Raises:
        400: No parsed job descriptions found.
        500: LLM call failed or returned malformed output.
    """
    return await career_intelligence.cluster_jds()


@router.get("/reports")
async def list_career_reports() -> list[dict[str, Any]]:
    """Return all career reports ordered by creation time descending."""
    try:
        reports = await db.get_career_reports()
    except Exception as exc:
        logger.error("Failed to list career reports: %s", exc)
        raise HTTPException(status_code=500, detail="Career intelligence failed.")
    return reports


@router.get("/reports/{report_id}")
async def get_career_report(report_id: int) -> dict[str, Any]:
    """Return a single career report by ID.

    Raises:
        404: Report not found.
        500: Database error.
    """
    try:
        report = await db.get_career_report(report_id)
    except Exception as exc:
        logger.error("Failed to fetch career report %s: %s", report_id, exc)
        raise HTTPException(status_code=500, detail="Career intelligence failed.")
    if report is None:
        raise HTTPException(status_code=404, detail="Career report not found.")
    return report
