# Backend Test Suite

Run: `cd apps/backend && uv run pytest`

LLM eval tests (gated, require a real API key): `uv run pytest -m eval`

## Layout

| Directory | What it tests | Key notes |
|-----------|--------------|-----------|
| `unit/` | Pure functions — diffs, parser, LLM key helpers, crypto | No DB, no network |
| `service/` | Service layer with LLM mocked via `respx` | `isolated_db` fixture for real SQLite |
| `integration/` | Full HTTP endpoints via `httpx ASGITransport` | Real routers, real DB migrations |
| `evals/` | Prompt quality scorers + a gated LLM judge | Excluded from default run |

## Smoke Matrix Rule (BUG-009)

`integration/test_smoke_paths.py` is the **integration smoke suite**. Its purpose
is to catch page-level breaks that unit suites miss by exercising real routers
against a seeded DB containing EVERY historical row shape.

**Rule: any ticket that adds or changes an endpoint MUST add it to the smoke matrix.**

Specifically:

1. **New GET endpoint** → add a test in `TestSmokePaths` that calls the endpoint
   against the seeded DB and asserts 200.

2. **New POST/PATCH mutation endpoint** → add a test in `TestSmokeMutations` that
   calls the endpoint against the seeded DB and asserts 2xx.

3. **New DB row shape / schema change** → update `_seed_db()` to include a row
   in the new shape. Document the shape with an inline comment explaining which
   bug or migration it represents.

4. **LLM-calling endpoints** → mock the LLM layer (patch the service function, not
   the DB), not the DB, so the real router + real DB path is exercised.

**Reviewer checklist item:** Before approving any PR that touches a router, verify
`test_smoke_paths.py` covers the new or changed endpoint. If it does not, request
the addition as a blocker.

### Why this rule exists (BUG-009 post-mortem)

BUG-004 added a smoke suite that tested only GET endpoints against a freshly
seeded modern-schema DB. Three defects followed immediately:

- **BUG-005** (`POST /applications/quick` 500): the mutation endpoint was absent
  from the smoke entirely.
- **BUG-006** (fact extraction renders empty): `POST /facts/extract` was never
  called by any smoke test; only unit tests for the Python service existed.
- **BUG-007** (JD Library 500): `GET /api/v1/jobs` (list) was absent from the
  smoke, and the seed never included legacy job shapes (no `parsed` key,
  non-string metadata values).

## Fixtures

`conftest.py::isolated_db` swaps the global `db` singleton with a disposable
temp-file SQLite DB for each test. Use it for any test that needs real DB
behavior. The fixture patches all router + service modules that import `db`.

Do NOT use `isolated_db` and `patch("app.routers.*.db")` in the same test —
pick one approach.
