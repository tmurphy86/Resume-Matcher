"""Integration tests for the considering quick-capture endpoint (RH-106)."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.applications import APPLICATION_STATUS_ORDER


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestQuickCapture:
    async def test_quick_capture_returns_201_with_considering_status(self, isolated_db: object) -> None:
        """POST /quick with valid jd_text → 201, status=considering, resume_id=None."""
        async with _client() as client:
            resp = await client.post(
                "/api/v1/applications/quick",
                json={"jd_text": "We are Acme hiring a Software Engineer."},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "considering"
        assert body["resume_id"] is None
        assert "application_id" in body
        assert "job_id" in body

    async def test_quick_capture_stores_company_and_role(self, isolated_db: object) -> None:
        """Optional company/role fields are persisted when provided."""
        async with _client() as client:
            resp = await client.post(
                "/api/v1/applications/quick",
                json={
                    "jd_text": "Join Globex as a Senior Engineer.",
                    "company": "Globex",
                    "role": "Senior Engineer",
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["company"] == "Globex"
        assert body["role"] == "Senior Engineer"

    async def test_quick_capture_duplicate_returns_409(self, isolated_db: object) -> None:
        """Submitting the same jd_text twice → second call returns 409."""
        payload = {"jd_text": "Duplicate JD text for dedup test."}
        async with _client() as client:
            first = await client.post("/api/v1/applications/quick", json=payload)
            assert first.status_code == 201

            # Duplicate: same jd_text creates a new Job, but considering check fires.
            # The endpoint must return 409 and not leave an orphan job behind.
            second = await client.post("/api/v1/applications/quick", json=payload)
        assert second.status_code == 409
        assert "considering" in second.json()["detail"].lower()

    async def test_board_includes_considering_column(self, isolated_db: object) -> None:
        """GET /applications board always has a 'considering' column."""
        async with _client() as client:
            resp = await client.get("/api/v1/applications")
        assert resp.status_code == 200
        columns = resp.json()["columns"]
        assert "considering" in columns
        assert "considering" == APPLICATION_STATUS_ORDER[0]

    async def test_quick_capture_card_appears_in_board(self, isolated_db: object) -> None:
        """A just-created considering card shows up in the board response."""
        async with _client() as client:
            create_resp = await client.post(
                "/api/v1/applications/quick",
                json={"jd_text": "Board visibility test JD."},
            )
            assert create_resp.status_code == 201

            board_resp = await client.get("/api/v1/applications")
        assert board_resp.status_code == 200
        considering_col = board_resp.json()["columns"]["considering"]
        assert len(considering_col) == 1
        assert considering_col[0]["resume_id"] is None
        assert considering_col[0]["status"] == "considering"

    async def test_quick_capture_missing_jd_text_returns_422(self, isolated_db: object) -> None:
        """jd_text is required; missing → 422 validation error."""
        async with _client() as client:
            resp = await client.post(
                "/api/v1/applications/quick",
                json={"company": "No JD Corp"},
            )
        assert resp.status_code == 422

    async def test_quick_capture_empty_jd_text_returns_422(self, isolated_db: object) -> None:
        """Empty string jd_text violates min_length=1 → 422."""
        async with _client() as client:
            resp = await client.post(
                "/api/v1/applications/quick",
                json={"jd_text": ""},
            )
        assert resp.status_code == 422
