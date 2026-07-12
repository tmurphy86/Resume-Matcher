# Frontend Test Suite

Run: `cd apps/frontend && npm run test`

## Layout

| Location | What it tests |
|----------|--------------|
| `tests/pages/` | Page-level smoke tests — mount each page, assert no crash |
| `tests/*.test.tsx` | Component and hook tests |
| `tests/*.test.ts` | Utility and API client tests |

## Page Smoke Matrix Rule (BUG-009)

`tests/pages/` contains smoke tests that mount every main page and assert it
renders without crashing. These catch React component breaks that backend tests
miss.

**Rule: any ticket that adds or changes a page MUST add or update its entry in
the page smoke matrix.**

Specifically:

1. **New page** → create `tests/pages/<name>-smoke.test.tsx` that mounts the
   page with all required mocks and asserts `container.firstChild` is truthy.

2. **New API response shape** → update the corresponding fixture in
   `tests/pages/smoke-shared.ts`. Fixtures must be derived from the actual
   backend Pydantic schemas — do not hand-write payloads that can drift from
   what the real API returns.

3. **Multiple historical shapes** → the smoke must include ALL historical API
   response shapes (modern + legacy), not just the happy path. See the job
   fixtures in `smoke-shared.ts` for an example (modern, pre-RH-303, and
   bad-metadata shapes are all represented).

4. **LLM-triggered UI flows** → mock the API call (e.g., `extractFacts`), not
   just the data-loading call. Exercise the component branches that render after
   the async call completes (loading, success, empty, error). See
   `tests/extract-modal.test.tsx` for the pattern.

**Reviewer checklist item:** Before approving any PR that touches a page or adds
an API response field, verify the smoke fixtures in `smoke-shared.ts` reflect
the new shape. If they do not, request the update as a blocker.

### Why this rule exists (BUG-009 post-mortem)

BUG-004 added page smokes that mounted each page but used minimal, hand-written
mock payloads. Three defects followed immediately:

- **BUG-005**: `POST /applications/quick` was never called in any frontend test.
- **BUG-006**: The facts page smoke mounted but never opened the extract modal,
  so the component branches rendering candidate lists (or empty states) were
  untested.
- **BUG-007**: The jobs page had no smoke test at all. Legacy job shapes (null
  company/role/level) were never mocked, and when the backend 500'd the frontend
  had no coverage to detect it.

## Schema-Parity Fixtures

`tests/pages/smoke-shared.ts` exports typed fixture objects that mirror the
backend Pydantic schemas. When a backend schema changes, update the corresponding
export in this file. Do NOT copy-paste inline payloads in individual test files —
import from `smoke-shared.ts` instead.
