"""Regression test: POST /api/v1/applications/quick must return 201 even for
databases created before RH-106 made resume_id nullable (BUG-005).

Root cause: the original ``applications`` table was created with
``resume_id TEXT NOT NULL`` (from ``Mapped[str]``).  RH-106 changed the ORM
model to ``Mapped[str | None]`` so that quick-capture cards could hold
``resume_id=NULL``, but no ALTER TABLE migration was added for SQLite.
SQLite does not support ALTER COLUMN, so existing databases kept the
NOT NULL constraint and every INSERT from POST /quick raised::

    IntegrityError: NOT NULL constraint failed: applications.resume_id

The router's generic ``except Exception`` caught this and returned HTTP 500.

Fix: ``init_models_sync`` now detects the NOT NULL constraint on ``resume_id``
and rebuilds the table (the standard SQLite 12-step process) so the column
becomes nullable before any INSERT is attempted.

These tests FAIL on the pre-fix code because:
  - ``_build_pre_rh106_db`` creates the applications table with the original
    NOT NULL constraint on resume_id (plus no interest_signals/status_history,
    matching the earliest possible legacy schema).
  - ``init_models_sync`` runs via ``Database._ensure_initialized``.
  - Without the fix, the rebuild step is missing; resume_id stays NOT NULL.
  - ``create_considering_application`` INSERTs with resume_id=NULL →
    IntegrityError → router returns HTTP 500 → assertion on 201 fails.
"""

import importlib
import sqlite3
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Database
from app.main import app


# ---------------------------------------------------------------------------
# Legacy DB builder
# ---------------------------------------------------------------------------

def _build_pre_rh106_db(db_path: Path) -> None:
    """Create a SQLite file with the earliest pre-RH-106 applications schema.

    Reproduces the state of a database that was first created before:
    - RH-106 (resume_id became nullable)
    - RH-105 (interest_signals added)
    - P3/RH-307 (status_history added)

    This is the worst-case legacy schema: resume_id NOT NULL plus both new
    JSON columns absent.  The migration stack must handle it end-to-end.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE applications (
                application_id   TEXT PRIMARY KEY,
                job_id           TEXT NOT NULL,
                resume_id        TEXT NOT NULL,
                master_resume_id TEXT,
                status           TEXT NOT NULL DEFAULT 'applied',
                company          TEXT,
                role             TEXT,
                applied_at       TEXT,
                notes            TEXT,
                position         INTEGER DEFAULT 0,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            )
            """
        )
        # Seed one existing applied card (resume_id non-null — valid for old schema).
        conn.execute(
            """
            INSERT INTO applications
                (application_id, job_id, resume_id, status, position,
                 created_at, updated_at)
            VALUES
                ('app-pre106', 'job-pre106', 'res-pre106', 'applied', 0,
                 '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00')
            """
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def pre_rh106_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Database:  # type: ignore[misc]
    """Swap the global ``db`` singleton with a Database backed by a pre-RH-106
    SQLite file (resume_id NOT NULL, no interest_signals, no status_history).

    The migration in ``init_models_sync`` runs lazily on first use, exactly as
    it would in production — so the test exercises the real migration path.
    """
    import app.database as database_module

    db_path = tmp_path / "pre_rh106.db"
    _build_pre_rh106_db(db_path)

    test_db = Database(db_path=db_path)
    monkeypatch.setattr(database_module, "db", test_db)
    for router_name in ("applications", "jobs"):
        try:
            module = importlib.import_module(f"app.routers.{router_name}")
        except ModuleNotFoundError:
            continue
        if hasattr(module, "db"):
            monkeypatch.setattr(module, "db", test_db)

    try:
        yield test_db
    finally:
        await test_db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestQuickCaptureLegacySchema:
    async def test_quick_capture_returns_201_on_pre_rh106_db(
        self, pre_rh106_db: Database
    ) -> None:
        """POST /quick must return 201 even when the applications table was
        created with resume_id NOT NULL (pre-RH-106 schema).

        Pre-fix failure path:
          init_models_sync adds interest_signals and status_history but does
          NOT rebuild the table → resume_id stays NOT NULL → INSERT with
          resume_id=NULL raises IntegrityError → router returns HTTP 500 →
          this assertion fails.

        Post-fix success path:
          init_models_sync detects resume_id is NOT NULL, rebuilds the table
          with resume_id nullable → INSERT succeeds → 201 with
          status=considering.
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/applications/quick",
                json={"jd_text": "We are hiring a Python Engineer. 5yr experience."},
            )

        assert resp.status_code == 201, (
            f"Expected 201 but got {resp.status_code}; "
            f"body: {resp.text}"
        )
        body = resp.json()
        assert body["status"] == "considering"
        assert body["resume_id"] is None

    async def test_existing_applied_card_preserved_after_migration(
        self, pre_rh106_db: Database
    ) -> None:
        """The seeded applied card must survive the table rebuild.

        The rebuild copies existing rows; if any row is lost the migration is
        broken and this test fails.
        """
        # Trigger migration by touching the DB (GET board forces _ensure_initialized).
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/applications")

        assert resp.status_code == 200
        applied = resp.json()["columns"].get("applied", [])
        app_ids = [a["application_id"] for a in applied]
        assert "app-pre106" in app_ids, (
            "Seeded applied card was lost during the BUG-005 table rebuild."
        )
