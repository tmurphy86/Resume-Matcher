"""Regression test: GET /api/applications must return 200 for databases created
before P3 added the status_history column (BUG-001).

Root cause: interest_signals (RH-105) and status_history (P3/RH-307) were
added to the Application ORM model without a corresponding ALTER TABLE
migration in init_models_sync.  For existing databases the columns were absent
from the SQLite table, so SQLAlchemy's generated SELECT included the column
names and SQLite raised OperationalError — caught by the router's generic
handler and returned as HTTP 500 to every client.

Fix: init_models_sync now runs idempotent ALTER TABLE statements for both
columns when they are missing, matching the existing interview_prep migration
pattern for the resumes table.

These tests FAIL on the pre-fix code because:
  - _build_legacy_db creates applications with the original schema
    (no interest_signals, no status_history).
  - Database(db_path=...) triggers init_models_sync on first use.
  - Without the fix, init_models_sync does NOT add the missing columns.
  - select(Application) therefore references non-existent columns →
    OperationalError → HTTP 500 → assert resp.status_code == 200 fails.
"""

import importlib
import sqlite3
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Database
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_legacy_db(db_path: Path) -> None:
    """Seed a SQLite file with the *original* applications schema.

    Omits interest_signals and status_history — exactly the shape that existed
    before RH-105/P3 and that causes select(Application) to raise
    OperationalError when no migration has been applied.

    Two rows are inserted:
    - a normal "applied" card (resume_id non-null)
    - a "considering" card  (resume_id IS NULL, as created by quick-capture)
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE applications (
                application_id   TEXT PRIMARY KEY,
                job_id           TEXT NOT NULL,
                resume_id        TEXT,
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
        # Legacy applied card.
        conn.execute(
            """
            INSERT INTO applications
                (application_id, job_id, resume_id, status, position,
                 created_at, updated_at)
            VALUES
                ('app-legacy', 'job-1', 'res-1', 'applied', 0,
                 '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00')
            """
        )
        # Legacy considering card (resume_id IS NULL).
        conn.execute(
            """
            INSERT INTO applications
                (application_id, job_id, resume_id, status, position,
                 created_at, updated_at)
            VALUES
                ('app-considering', 'job-2', NULL, 'considering', 0,
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
async def legacy_schema_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Swap the global db singleton with a Database backed by a legacy SQLite file.

    The file is created with the pre-P3 applications schema (no interest_signals,
    no status_history).  Database.__init__ does NOT run init_models_sync eagerly;
    it runs on first async use — so the migration (or lack of it) runs when the
    first HTTP request arrives, exactly as it would in production.
    """
    import app.database as database_module

    db_path = tmp_path / "legacy.db"
    _build_legacy_db(db_path)

    test_db = Database(db_path=db_path)
    monkeypatch.setattr(database_module, "db", test_db)
    for router_name in ("applications",):
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

class TestLegacySchemaCompat:
    async def test_list_applications_returns_200_for_legacy_db(
        self, legacy_schema_db: Database
    ) -> None:
        """GET /api/applications returns 200 even for rows missing status_history.

        Pre-fix failure path:
          init_models_sync does NOT ALTER TABLE → select(Application) lists
          status_history in the SQL → SQLite raises OperationalError →
          router catches it and returns HTTP 500 → this assertion fails.

        Post-fix success path:
          init_models_sync adds interest_signals and status_history via
          ALTER TABLE → select(Application) succeeds → 200 with seeded data.
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/applications")

        assert resp.status_code == 200
        columns = resp.json()["columns"]
        # The seeded applied row must appear in its column.
        assert len(columns["applied"]) == 1
        assert columns["applied"][0]["application_id"] == "app-legacy"
        # Legacy rows have no recorded signals — the migrated column defaults to [].
        assert columns["applied"][0]["interest_signals"] == []

    async def test_considering_card_null_resume_id_returns_200(
        self, legacy_schema_db: Database
    ) -> None:
        """Considering cards (resume_id=NULL) from legacy rows serialise cleanly.

        This also exercises the quick-capture row shape (resume_id IS NULL)
        which the RH-106 feature introduced and which pre-P3 databases may
        contain without a status_history column.
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/applications")

        assert resp.status_code == 200
        considering = resp.json()["columns"]["considering"]
        assert len(considering) == 1
        assert considering[0]["resume_id"] is None
