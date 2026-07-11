"""JobSpy-backed external job search service."""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import jobspy as jobspy
except ImportError:
    jobspy = None  # type: ignore[assignment]


async def search_jobs(
    term: str,
    location: str | None,
    sources: list[str],
) -> dict[str, Any]:
    """Search external job boards via python-jobspy.

    Returns {"results": [...], "errors": {source: message}}.
    Runs jobspy.scrape_jobs() in a thread executor (it's synchronous).
    """
    if jobspy is None:
        logger.error("python-jobspy is not installed")
        return {"results": [], "errors": {"all": "python-jobspy is not installed"}}

    def _scrape() -> Any:
        return jobspy.scrape_jobs(
            site_name=sources,
            search_term=term,
            location=location or "",
            results_wanted=20,
            hours_old=72,
            country_indeed="USA",
        )

    try:
        results_df = await asyncio.to_thread(_scrape)
    except Exception as e:
        logger.error(f"jobspy scrape_jobs failed: {e}")
        return {"results": [], "errors": {"all": str(e)}}

    results: list[dict[str, Any]] = []
    if results_df is not None and not results_df.empty:
        for _, row in results_df.iterrows():
            description: str = str(row.get("description") or "")
            results.append(
                {
                    "title": str(row.get("title") or ""),
                    "company": str(row.get("company") or ""),
                    "location": str(row.get("location") or ""),
                    "snippet": description[:300],
                    "url": str(row.get("job_url") or ""),
                    "source": str(row.get("site") or ""),
                }
            )

    return {"results": results, "errors": {}}
