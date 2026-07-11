"""BUG-004: Human-path smoke tests — every main GET endpoint must return 2xx.

Covers the class of bug where page-level integration breaks are missed by
unit suites because they require multiple row shapes to coexist in the DB.

Seeded DB state mirrors what Tim's real database looks like after P3:
  - master resume with bullet_blocks (blocks-based)
  - legacy resume (description only, no bullet_blocks)
  - considering application with resume_id=NULL and no status_history
  - normal applied application with status_history
  - job with parsed metadata
"""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.models import ResumeData


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _blocks_resume_data() -> dict:
    """ResumeData with bullet_blocks — the P3 block-based format."""
    base = {
        "personalInfo": {
            "name": "Tim Murphy",
            "title": "Engineering Lead",
            "email": "tim@example.com",
            "phone": "555-0100",
            "location": "Brooklyn, NY",
            "website": "",
            "linkedin": "",
            "github": "",
        },
        "summary": "Engineering lead with 10 years building products.",
        "summary_blocks": [
            {
                "id": "sb-1",
                "active_variant_id": "v-1",
                "variants": [
                    {
                        "id": "v-1",
                        "text": "Engineering lead with 10 years building products.",
                        "tags": [],
                        "fact_ids": [],
                    }
                ],
            }
        ],
        "workExperience": [
            {
                "id": 1,
                "title": "VP Engineering",
                "company": "Acme",
                "location": "NYC",
                "years": "2020 - Present",
                "description": ["Led a team of 20 engineers."],
                "bullet_blocks": [
                    {
                        "id": "bb-1",
                        "active_variant_id": "bv-1",
                        "variants": [
                            {
                                "id": "bv-1",
                                "text": "Led a team of 20 engineers.",
                                "tags": [],
                                "fact_ids": [],
                            }
                        ],
                    }
                ],
            }
        ],
        "education": [],
        "personalProjects": [],
        "additional": {
            "technicalSkills": ["Python", "React"],
            "languages": [],
            "certificationsTraining": [],
            "awards": [],
        },
        "customSections": {},
        "sectionMeta": [],
    }
    return base


def _legacy_resume_data() -> dict:
    """ResumeData without bullet_blocks — the pre-P3 legacy format."""
    return {
        "personalInfo": {
            "name": "Legacy User",
            "title": "Developer",
            "email": "legacy@example.com",
            "phone": "",
            "location": "",
            "website": "",
            "linkedin": "",
            "github": "",
        },
        "summary": "A legacy resume with no blocks.",
        "workExperience": [
            {
                "id": 1,
                "title": "Developer",
                "company": "Old Co",
                "location": "",
                "years": "2015 - 2019",
                "description": ["Wrote code."],
            }
        ],
        "education": [],
        "personalProjects": [],
        "additional": {
            "technicalSkills": [],
            "languages": [],
            "certificationsTraining": [],
            "awards": [],
        },
        "customSections": {},
        "sectionMeta": [],
    }


async def _seed_db(isolated_db) -> dict:
    """Seed all required row shapes and return their IDs."""
    # Master resume (blocks-based, P3 format)
    master = await isolated_db.create_resume(
        content="Tim Murphy resume content",
        processed_data=_blocks_resume_data(),
        is_master=True,
        processing_status="ready",
    )

    # Legacy resume (description-only, no bullet_blocks, pre-P3 format)
    legacy = await isolated_db.create_resume(
        content="Legacy resume content",
        processed_data=_legacy_resume_data(),
        is_master=False,
        processing_status="ready",
    )

    # Job (simple — GET /api/jobs/{id} must return 200)
    job = await isolated_db.create_job(
        content="Senior Python Engineer at TechCorp. Requirements: Python, FastAPI, 5yr.",
    )

    # Considering application — resume_id=NULL (RH-106 quick-capture shape)
    # status_history defaults to [] after BUG-001 migration
    considering = await isolated_db.create_application(
        job_id=job["job_id"],
        resume_id=None,
        status="considering",
    )

    # Normal applied application (also tests status_history column access after BUG-001)
    applied = await isolated_db.create_application(
        job_id=job["job_id"],
        resume_id=master["resume_id"],
        status="applied",
    )

    return {
        "master_id": master["resume_id"],
        "legacy_id": legacy["resume_id"],
        "job_id": job["job_id"],
        "considering_id": considering["application_id"],
        "applied_id": applied["application_id"],
    }


# ---------------------------------------------------------------------------
# Smoke suite
# ---------------------------------------------------------------------------

class TestSmokePaths:
    """Every main GET list/detail endpoint must return 2xx for the seeded DB."""

    async def test_resumes_list(self, isolated_db: object) -> None:
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/resumes/list", params={"include_master": "true"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 2

    async def test_resume_detail_master(self, isolated_db: object) -> None:
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/resumes", params={"resume_id": ids["master_id"]})
        assert resp.status_code == 200

    async def test_resume_detail_legacy(self, isolated_db: object) -> None:
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/resumes", params={"resume_id": ids["legacy_id"]})
        assert resp.status_code == 200

    async def test_applications_list_all_row_shapes(self, isolated_db: object) -> None:
        """BUG-001 regression: must handle considering (NULL resume) + status_history rows."""
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/applications")
        assert resp.status_code == 200
        columns = resp.json()["columns"]
        assert "considering" in columns
        assert "applied" in columns
        # Both seeded cards must be present
        considering_ids = [a["application_id"] for a in columns.get("considering", [])]
        applied_ids = [a["application_id"] for a in columns.get("applied", [])]
        assert len(considering_ids) >= 1
        assert len(applied_ids) >= 1

    async def test_application_detail_considering(self, isolated_db: object) -> None:
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/applications/{ids['considering_id']}")
        assert resp.status_code == 200

    async def test_application_detail_applied(self, isolated_db: object) -> None:
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/applications/{ids['applied_id']}")
        assert resp.status_code == 200

    async def test_facts_list(self, isolated_db: object) -> None:
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/facts")
        assert resp.status_code == 200

    async def test_career_reports_list(self, isolated_db: object) -> None:
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/career/reports")
        assert resp.status_code == 200

    async def test_jobs_detail(self, isolated_db: object) -> None:
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/jobs/{ids['job_id']}")
        assert resp.status_code == 200
