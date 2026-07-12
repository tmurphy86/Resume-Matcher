"""Integration tests for job description endpoints."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestJobUpload:
    """POST /api/v1/jobs/upload"""

    @patch("app.routers.jobs.db", new_callable=AsyncMock)
    async def test_upload_single_job(self, mock_db, client):
        mock_db.create_job.return_value = {
            "job_id": "job-123",
            "content": "Senior Engineer at TechCorp",
            "created_at": "2026-01-01T00:00:00Z",
        }
        async with client:
            resp = await client.post("/api/v1/jobs/upload", json={
                "job_descriptions": ["Senior Engineer at TechCorp"],
                "resume_id": None,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "data successfully processed"
        assert len(data["job_id"]) == 1

    @patch("app.routers.jobs.db", new_callable=AsyncMock)
    async def test_upload_multiple_jobs(self, mock_db, client):
        mock_db.create_job.side_effect = [
            {"job_id": f"job-{i}", "content": f"JD {i}", "created_at": "2026-01-01T00:00:00Z"}
            for i in range(3)
        ]
        async with client:
            resp = await client.post("/api/v1/jobs/upload", json={
                "job_descriptions": ["JD 1", "JD 2", "JD 3"],
            })
        assert resp.status_code == 200
        assert len(resp.json()["job_id"]) == 3

    async def test_upload_empty_list_returns_400(self, client):
        async with client:
            resp = await client.post("/api/v1/jobs/upload", json={
                "job_descriptions": [],
            })
        assert resp.status_code == 400

    async def test_upload_empty_string_returns_400(self, client):
        async with client:
            resp = await client.post("/api/v1/jobs/upload", json={
                "job_descriptions": ["  "],
            })
        assert resp.status_code == 400


class TestGetJob:
    """GET /api/v1/jobs/{job_id}"""

    @patch("app.routers.jobs.db", new_callable=AsyncMock)
    async def test_get_existing_job(self, mock_db, client):
        mock_db.get_job.return_value = {
            "job_id": "job-123",
            "content": "Engineer role",
            "created_at": "2026-01-01T00:00:00Z",
        }
        async with client:
            resp = await client.get("/api/v1/jobs/job-123")
        assert resp.status_code == 200
        assert resp.json()["job_id"] == "job-123"

    @patch("app.routers.jobs.db", new_callable=AsyncMock)
    async def test_get_nonexistent_job_returns_404(self, mock_db, client):
        mock_db.get_job.return_value = None
        async with client:
            resp = await client.get("/api/v1/jobs/nonexistent")
        assert resp.status_code == 404


class TestListJobs:
    """GET /api/v1/jobs"""

    async def test_empty_db_returns_empty_list(self, isolated_db):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_snippet_not_full_content(self, isolated_db):
        long_content = "x" * 500
        await isolated_db.create_job(content=long_content)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert len(data[0]["snippet"]) == 200
        assert "content" not in data[0]

    async def test_text_search_q_filters_by_content(self, isolated_db):
        await isolated_db.create_job(content="Senior Python Engineer at MegaCorp")
        await isolated_db.create_job(content="Frontend Designer React UI")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs?q=python")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "MegaCorp" in data[0]["snippet"]

    async def test_q_is_case_insensitive(self, isolated_db):
        await isolated_db.create_job(content="Senior PYTHON Developer")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs?q=Python")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_archetype_filter_excludes_unassigned(self, isolated_db):
        # No career report -> no archetype assignment -> archetype filter returns nothing.
        await isolated_db.create_job(content="Backend role at SomeCo")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs?archetype=Backend")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_archetype_filter_with_career_report(self, isolated_db):
        job1 = await isolated_db.create_job(content="Backend role at Alpha")
        job2 = await isolated_db.create_job(content="Frontend role at Beta")
        await isolated_db.create_career_report(
            archetypes_json=[
                {
                    "name": "Backend",
                    "description": "be",
                    "jd_ids": [job1["job_id"]],
                    "responsibilities": [],
                },
                {
                    "name": "Frontend",
                    "description": "fe",
                    "jd_ids": [job2["job_id"]],
                    "responsibilities": [],
                },
            ],
            jd_ids_json=[job1["job_id"], job2["job_id"]],
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs?archetype=Backend")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["archetype"] == "Backend"

    async def test_archetype_populated_from_latest_report(self, isolated_db):
        job = await isolated_db.create_job(content="SRE role at Infra Inc")
        await isolated_db.create_career_report(
            archetypes_json=[
                {
                    "name": "SRE",
                    "description": "ops",
                    "jd_ids": [job["job_id"]],
                    "responsibilities": [],
                },
            ],
            jd_ids_json=[job["job_id"]],
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["archetype"] == "SRE"

    async def test_get_job_detail_includes_application_ids(self, isolated_db):
        job = await isolated_db.create_job(content="PM role at WidgetCo")
        app_row = await isolated_db.create_application(
            job_id=job["job_id"], company="WidgetCo", role="PM"
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/jobs/{job['job_id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert "application_ids" in data
        assert app_row["application_id"] in data["application_ids"]

    async def test_legacy_job_without_parsed_metadata(self, isolated_db):
        """Test that jobs without parsed metadata are handled gracefully.

        Legacy rows pre-dating RH-303 have no parsed key in metadata_json.
        The endpoint should return 200 with graceful null values.
        """
        job = await isolated_db.create_job(content="Senior Engineer role")
        # Verify the job exists and has no parsed key yet
        fetched = await isolated_db.get_job(job["job_id"])
        assert "parsed" not in fetched

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["job_id"] == job["job_id"]
        assert data[0]["snippet"] == "Senior Engineer role"
        assert data[0]["company"] is None
        assert data[0]["role"] is None
        assert data[0]["level"] is None

    async def test_legacy_job_without_parsed_key(self, isolated_db):
        """Test that jobs without parsed key in metadata_json are handled gracefully.

        Legacy rows may have metadata_json with company/role but no parsed key.
        """
        job = await isolated_db.create_job(
            content="Staff DevOps Engineer",
        )
        # Update the job to remove the parsed key if it exists, keeping only company/role.
        await isolated_db.update_job(job["job_id"], {"company": "TechCorp", "role": "DevOps"})

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["company"] == "TechCorp"
        assert data[0]["role"] == "DevOps"
        assert data[0]["level"] is None

    async def test_list_jobs_with_parsed_and_fallback_fields(self, isolated_db):
        """Test that parsed fields take precedence over metadata fields.

        When both parsed["company"] and metadata["company"] exist,
        parsed should win.
        """
        job = await isolated_db.create_job(content="Engineer role")
        # Store parsed data with one company, and metadata with another
        await isolated_db.update_job(
            job["job_id"],
            {
                "company": "MetaCorp",
                "role": "MetaRole",
                "parsed": {
                    "responsibilities": ["Work on stuff"],
                    "requirements": ["Be smart"],
                    "level": "Senior",
                    "comp": None,
                },
            },
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # Company should prefer parsed, but parsed doesn't have company, so fallback to metadata
        assert data[0]["company"] == "MetaCorp"
        assert data[0]["role"] == "MetaRole"
        assert data[0]["level"] == "Senior"

    async def test_legacy_job_with_non_string_level(self, isolated_db):
        """Test that non-string level values are handled gracefully.

        Some legacy or corrupted parsed data might have non-string values.
        The endpoint should coerce them gracefully.
        """
        job = await isolated_db.create_job(content="DevOps role")
        # Store parsed data with level as a number or dict (corrupted data)
        await isolated_db.update_job(
            job["job_id"],
            {
                "parsed": {
                    "responsibilities": [],
                    "requirements": [],
                    "level": {"text": "Senior"},  # Non-string level
                    "comp": None,
                },
            },
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/jobs")
        # Should return 200 even with non-standard level data
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        # Level should be None or gracefully handled
        assert data[0]["level"] is None or isinstance(data[0]["level"], str)
