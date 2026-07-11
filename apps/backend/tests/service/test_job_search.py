"""Tests for the JobSpy-backed job search service."""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch


def _make_df(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal DataFrame matching jobspy output shape."""
    return pd.DataFrame(rows)


@pytest.mark.asyncio
@pytest.mark.service
async def test_search_returns_results() -> None:
    """Two-row DataFrame produces two results."""
    mock_df = _make_df([
        {
            "title": "Software Engineer",
            "company": "Acme",
            "location": "New York, NY",
            "description": "Build things.",
            "job_url": "https://example.com/job/1",
            "site": "linkedin",
        },
        {
            "title": "Data Scientist",
            "company": "Globex",
            "location": "Austin, TX",
            "description": "Analyse things.",
            "job_url": "https://example.com/job/2",
            "site": "indeed",
        },
    ])

    with patch("app.services.job_search.jobspy") as mock_jobspy:
        mock_jobspy.scrape_jobs.return_value = mock_df
        from app.services.job_search import search_jobs
        result = await search_jobs(term="engineer", location=None, sources=["linkedin", "indeed"])

    assert len(result["results"]) == 2
    assert result["errors"] == {}


@pytest.mark.asyncio
@pytest.mark.service
async def test_search_maps_fields_correctly() -> None:
    """Each result dict has title/company/location/snippet/url/source."""
    mock_df = _make_df([
        {
            "title": "ML Engineer",
            "company": "Neural Co",
            "location": "Remote",
            "description": "Train models.",
            "job_url": "https://example.com/ml",
            "site": "glassdoor",
        },
    ])

    with patch("app.services.job_search.jobspy") as mock_jobspy:
        mock_jobspy.scrape_jobs.return_value = mock_df
        from app.services.job_search import search_jobs
        result = await search_jobs(term="ml", location="Remote", sources=["glassdoor"])

    r = result["results"][0]
    assert r["title"] == "ML Engineer"
    assert r["company"] == "Neural Co"
    assert r["location"] == "Remote"
    assert r["snippet"] == "Train models."
    assert r["url"] == "https://example.com/ml"
    assert r["source"] == "glassdoor"


@pytest.mark.asyncio
@pytest.mark.service
async def test_search_snippet_truncated_at_300() -> None:
    """Descriptions longer than 300 chars are truncated in the snippet."""
    long_description = "A" * 500

    mock_df = _make_df([
        {
            "title": "Engineer",
            "company": "Corp",
            "location": "NYC",
            "description": long_description,
            "job_url": "https://example.com",
            "site": "linkedin",
        },
    ])

    with patch("app.services.job_search.jobspy") as mock_jobspy:
        mock_jobspy.scrape_jobs.return_value = mock_df
        from app.services.job_search import search_jobs
        result = await search_jobs(term="eng", location=None, sources=["linkedin"])

    assert len(result["results"][0]["snippet"]) == 300


@pytest.mark.asyncio
@pytest.mark.service
async def test_search_empty_results() -> None:
    """Empty DataFrame returns results=[] and errors={}."""
    mock_df = _make_df([])

    with patch("app.services.job_search.jobspy") as mock_jobspy:
        mock_jobspy.scrape_jobs.return_value = mock_df
        from app.services.job_search import search_jobs
        result = await search_jobs(term="nobody", location=None, sources=["linkedin"])

    assert result["results"] == []
    assert result["errors"] == {}


@pytest.mark.asyncio
@pytest.mark.service
async def test_search_handles_exception() -> None:
    """Exception from scrape_jobs returns results=[] and errors with 'all' key."""
    with patch("app.services.job_search.jobspy") as mock_jobspy:
        mock_jobspy.scrape_jobs.side_effect = RuntimeError("network timeout")
        from app.services.job_search import search_jobs
        result = await search_jobs(term="dev", location=None, sources=["indeed"])

    assert result["results"] == []
    assert "all" in result["errors"]
    assert "network timeout" in result["errors"]["all"]


@pytest.mark.asyncio
@pytest.mark.service
async def test_search_respects_sources() -> None:
    """The sources list is forwarded to scrape_jobs unchanged."""
    mock_df = _make_df([])

    with patch("app.services.job_search.jobspy") as mock_jobspy:
        mock_jobspy.scrape_jobs.return_value = mock_df
        from app.services.job_search import search_jobs
        await search_jobs(term="dev", location="Boston", sources=["zip_recruiter", "glassdoor"])

    call_kwargs = mock_jobspy.scrape_jobs.call_args
    assert call_kwargs.kwargs["site_name"] == ["zip_recruiter", "glassdoor"]
