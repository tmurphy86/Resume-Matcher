"""Integration tests for RH-307 — application status_history tracking.

Covers: transition append, bulk append, seed behaviour for legacy rows,
and quick-capture initial entry.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_card(isolated_db, **kwargs):
    """Create a card directly on the DB (bypassing the router)."""
    defaults = dict(job_id="job-1", resume_id="res-1", status="applied")
    defaults.update(kwargs)
    return await isolated_db.create_application(**defaults)


class TestCreateSeeding:
    async def test_create_application_seeds_history_with_initial_status(self, isolated_db):
        """create_application seeds status_history with the initial status entry."""
        card = await _seed_card(isolated_db, status="applied")
        fetched = await isolated_db.get_application(card["application_id"])
        assert fetched is not None
        history = fetched["status_history"]
        assert len(history) == 1
        assert history[0]["status"] == "applied"
        assert history[0]["at"] == card["created_at"]

    async def test_create_saved_card_seeds_history_with_saved(self, isolated_db):
        """Saved status is recorded correctly in initial history."""
        card = await _seed_card(isolated_db, job_id="j-saved", resume_id="r-saved", status="saved")
        fetched = await isolated_db.get_application(card["application_id"])
        assert fetched is not None
        history = fetched["status_history"]
        assert len(history) == 1
        assert history[0]["status"] == "saved"

    async def test_quick_capture_seeds_history_with_considering(self, isolated_db):
        """Quick-capture (considering) create seeds history with 'considering'."""
        job = await isolated_db.create_job(content="Some JD text for considering")
        card = await isolated_db.create_considering_application(
            job_id=job["job_id"],
            company="ACME",
            role="Engineer",
        )
        fetched = await isolated_db.get_application(card["application_id"])
        assert fetched is not None
        history = fetched["status_history"]
        assert len(history) == 1
        assert history[0]["status"] == "considering"


class TestTransitionAppend:
    async def test_single_patch_status_change_appends_history(self, isolated_db):
        """PATCH changing status appends a new entry to status_history."""
        card = await _seed_card(isolated_db, status="applied")

        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"status": "interview"},
            )
        assert resp.status_code == 200

        fetched = await isolated_db.get_application(card["application_id"])
        assert fetched is not None
        history = fetched["status_history"]
        assert len(history) == 2
        assert history[0]["status"] == "applied"
        assert history[1]["status"] == "interview"

    async def test_multiple_status_transitions_accumulate(self, isolated_db):
        """Each distinct status change appends a new entry; history grows."""
        card = await _seed_card(isolated_db, status="applied")
        app_id = card["application_id"]

        async with _client() as client:
            await client.patch(f"/api/v1/applications/{app_id}", json={"status": "interview"})
        async with _client() as client:
            await client.patch(f"/api/v1/applications/{app_id}", json={"status": "accepted"})

        fetched = await isolated_db.get_application(app_id)
        assert fetched is not None
        history = fetched["status_history"]
        assert len(history) == 3
        assert [e["status"] for e in history] == ["applied", "interview", "accepted"]

    async def test_position_only_patch_does_not_append_history(self, isolated_db):
        """A PATCH that only changes position must NOT append to history."""
        card = await _seed_card(isolated_db, status="applied")
        app_id = card["application_id"]

        async with _client() as client:
            await client.patch(f"/api/v1/applications/{app_id}", json={"position": 0})

        fetched = await isolated_db.get_application(app_id)
        assert fetched is not None
        # Still only the initial entry from creation
        assert len(fetched["status_history"]) == 1

    async def test_notes_patch_does_not_append_history(self, isolated_db):
        """A PATCH that only changes notes must NOT append to history."""
        card = await _seed_card(isolated_db, status="applied")

        async with _client() as client:
            await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"notes": "Follow up Monday"},
            )

        fetched = await isolated_db.get_application(card["application_id"])
        assert fetched is not None
        assert len(fetched["status_history"]) == 1


class TestBulkAppend:
    async def test_bulk_move_appends_history_for_each_card(self, isolated_db):
        """bulk_update_applications appends history on every moved card."""
        a = await _seed_card(isolated_db, job_id="j1", resume_id="r1", status="applied")
        b = await _seed_card(isolated_db, job_id="j2", resume_id="r2", status="applied")

        async with _client() as client:
            resp = await client.patch(
                "/api/v1/applications/bulk",
                json={
                    "application_ids": [a["application_id"], b["application_id"]],
                    "status": "rejected",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["affected"] == 2

        for app_id in (a["application_id"], b["application_id"]):
            fetched = await isolated_db.get_application(app_id)
            assert fetched is not None
            history = fetched["status_history"]
            assert len(history) == 2
            assert history[0]["status"] == "applied"
            assert history[1]["status"] == "rejected"

    async def test_bulk_move_same_status_does_not_duplicate_history(self, isolated_db):
        """Moving a card to the same status it already has does not append."""
        card = await _seed_card(isolated_db, status="applied")

        async with _client() as client:
            await client.patch(
                "/api/v1/applications/bulk",
                json={"application_ids": [card["application_id"]], "status": "applied"},
            )

        fetched = await isolated_db.get_application(card["application_id"])
        assert fetched is not None
        # No new entry for a same-status bulk move
        assert len(fetched["status_history"]) == 1


class TestBackfillSeed:
    async def test_existing_row_without_history_gets_seeded_on_status_change(self, isolated_db):
        """Legacy rows (status_history=[]) get backfill-seeded on the next write."""
        # Create the card normally (it will have initial history).
        card = await _seed_card(isolated_db, status="applied")
        app_id = card["application_id"]

        # Simulate a legacy row by clearing the history directly in the DB.
        async with isolated_db._session() as session:
            from app.models import Application
            row = await session.get(Application, app_id)
            assert row is not None
            row.status_history = []
            # Also rewind updated_at to a known timestamp for assertion
            row.updated_at = "2025-01-01T00:00:00+00:00"
            await session.commit()

        # Confirm history is now empty
        fetched = await isolated_db.get_application(app_id)
        assert fetched is not None
        assert fetched["status_history"] == []

        # Trigger a status change — this should backfill + append
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{app_id}",
                json={"status": "interview"},
            )
        assert resp.status_code == 200

        fetched = await isolated_db.get_application(app_id)
        assert fetched is not None
        history = fetched["status_history"]
        # Should be: seed entry (applied / old updated_at) + new entry (interview)
        assert len(history) == 2
        assert history[0]["status"] == "applied"
        assert history[0]["at"] == "2025-01-01T00:00:00+00:00"
        assert history[1]["status"] == "interview"

    async def test_history_entries_contain_iso_timestamps(self, isolated_db):
        """Every history entry must have a parseable ISO 8601 UTC timestamp."""
        from datetime import datetime, timezone

        card = await _seed_card(isolated_db, status="applied")

        async with _client() as client:
            await client.patch(
                f"/api/v1/applications/{card['application_id']}",
                json={"status": "response"},
            )

        fetched = await isolated_db.get_application(card["application_id"])
        assert fetched is not None
        for entry in fetched["status_history"]:
            assert "status" in entry
            assert "at" in entry
            # Must be parseable
            dt = datetime.fromisoformat(entry["at"])
            # Timestamps are UTC
            assert dt.utcoffset() is not None or entry["at"].endswith("+00:00")
