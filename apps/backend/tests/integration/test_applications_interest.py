"""Integration tests for interest signals on applications."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_card(isolated_db, **kwargs):
    """Create a card directly on the DB (bypassing the LLM manual-add path)."""
    defaults = dict(job_id="job-1", resume_id="res-1", status="applied")
    defaults.update(kwargs)
    return await isolated_db.create_application(**defaults)


class TestInterestDimensions:
    async def test_get_interest_dimensions_returns_all_seven(self, isolated_db):
        async with _client() as client:
            resp = await client.get("/api/v1/applications/interest-dimensions")
        assert resp.status_code == 200
        dimensions = resp.json()
        assert len(dimensions) == 7

        # Check structure and expected dimensions
        ids = {d["id"] for d in dimensions}
        expected_ids = {
            "compensation",
            "role_scope",
            "values_mission",
            "growth",
            "technology",
            "stability_lifestyle",
            "people",
        }
        assert ids == expected_ids

        # Check that each has id and label
        for d in dimensions:
            assert "id" in d
            assert "label" in d
            assert isinstance(d["label"], str)
            assert len(d["label"]) > 0


class TestInterestSignalsCrud:
    async def test_create_with_valid_signals(self, isolated_db):
        """Create an application with valid interest signals."""
        resume = await isolated_db.create_resume(content="# Resume")
        job = await isolated_db.create_job(content="JD body")

        async with _client() as client:
            resp = await client.post(
                "/api/v1/applications",
                json={
                    "resume_id": resume["resume_id"],
                    "job_description": "JD text",
                    "status": "applied",
                },
            )
        app_id = resp.json()["application_id"]

        # Now PATCH to add interest signals
        signals = [
            {"dimension": "compensation", "weight": 5, "note": "Important for me"},
            {"dimension": "growth", "weight": 4},
        ]
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{app_id}",
                json={"interest_signals": signals},
            )
        assert resp.status_code == 200
        body = resp.json()
        # Pydantic includes note: None for optional fields
        expected = [
            {"dimension": "compensation", "weight": 5, "note": "Important for me"},
            {"dimension": "growth", "weight": 4, "note": None},
        ]
        assert body["interest_signals"] == expected

    async def test_update_signals(self, isolated_db):
        """PATCH to update signals on existing card."""
        card = await _seed_card(isolated_db)
        original_signals = [
            {"dimension": "compensation", "weight": 3},
        ]

        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"interest_signals": original_signals},
            )
        assert resp.status_code == 200
        expected = [
            {"dimension": "compensation", "weight": 3, "note": None},
        ]
        assert resp.json()["interest_signals"] == expected

        # Update with new signals
        new_signals = [
            {"dimension": "role_scope", "weight": 5, "note": "Looking for autonomy"},
            {"dimension": "growth", "weight": 4},
        ]
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"interest_signals": new_signals},
            )
        assert resp.status_code == 200
        expected = [
            {"dimension": "role_scope", "weight": 5, "note": "Looking for autonomy"},
            {"dimension": "growth", "weight": 4, "note": None},
        ]
        assert resp.json()["interest_signals"] == expected

    async def test_empty_signals_default(self, isolated_db):
        """New cards default to empty signals list."""
        card = await _seed_card(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/applications/{card['application_id']}")
        assert resp.status_code == 200
        assert resp.json()["interest_signals"] == []

    async def test_signals_persisted_on_list(self, isolated_db):
        """Signals are returned when listing applications."""
        card = await _seed_card(isolated_db)
        signals = [{"dimension": "compensation", "weight": 5}]

        async with _client() as client:
            await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"interest_signals": signals},
            )

        async with _client() as client:
            resp = await client.get("/api/v1/applications")
        assert resp.status_code == 200
        columns = resp.json()["columns"]
        expected = [{"dimension": "compensation", "weight": 5, "note": None}]
        for card_list in columns.values():
            for c in card_list:
                if c["application_id"] == card["application_id"]:
                    assert c["interest_signals"] == expected


class TestInterestSignalsValidation:
    async def test_unknown_dimension_on_patch_returns_422(self, isolated_db):
        """PATCH with unknown dimension returns 422."""
        card = await _seed_card(isolated_db)
        signals = [{"dimension": "unknown_dimension", "weight": 3}]

        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"interest_signals": signals},
            )
        assert resp.status_code == 422
        body = resp.json()
        assert "unknown_dimension" in body["detail"]

    async def test_weight_out_of_range_low(self, isolated_db):
        """Weight < 1 is rejected by Pydantic validation (400)."""
        card = await _seed_card(isolated_db)
        signals = [{"dimension": "compensation", "weight": 0}]

        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"interest_signals": signals},
            )
        assert resp.status_code == 422

    async def test_weight_out_of_range_high(self, isolated_db):
        """Weight > 5 is rejected by Pydantic validation (400)."""
        card = await _seed_card(isolated_db)
        signals = [{"dimension": "compensation", "weight": 6}]

        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"interest_signals": signals},
            )
        assert resp.status_code == 422

    async def test_valid_weight_boundaries(self, isolated_db):
        """Weights 1 and 5 are valid."""
        card = await _seed_card(isolated_db)

        for weight in [1, 5]:
            signals = [{"dimension": "compensation", "weight": weight}]
            async with _client() as client:
                resp = await client.patch(
                    f"/api/v1/applications/{card['application_id']}",
                    json={"interest_signals": signals},
                )
            assert resp.status_code == 200
            assert resp.json()["interest_signals"][0]["weight"] == weight

    async def test_optional_note(self, isolated_db):
        """Note field is optional."""
        card = await _seed_card(isolated_db)

        # Without note
        signals = [{"dimension": "compensation", "weight": 3}]
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"interest_signals": signals},
            )
        assert resp.status_code == 200
        assert resp.json()["interest_signals"][0]["note"] is None

        # With note
        signals = [
            {"dimension": "compensation", "weight": 3, "note": "This is important"}
        ]
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"interest_signals": signals},
            )
        assert resp.status_code == 200
        assert resp.json()["interest_signals"][0]["note"] == "This is important"

    async def test_multiple_signals_one_invalid_fails(self, isolated_db):
        """If any signal is invalid, the whole request fails."""
        card = await _seed_card(isolated_db)
        signals = [
            {"dimension": "compensation", "weight": 3},
            {"dimension": "bad_dimension", "weight": 4},
        ]

        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"interest_signals": signals},
            )
        assert resp.status_code == 422
