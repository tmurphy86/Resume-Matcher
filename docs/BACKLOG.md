# Resume Hulk — Backlog

> Written/prioritized by the program lead (Cowork). Consumed top-down by the Claude Code eng lead.
> Ticket rules: one module focus, executable acceptance criteria, explicit out-of-scope. See docs/ORCHESTRATION.md.

## P1 — Fact base, variants, provenance, interest signals

### RH-101: Facts table + CRUD
**Size:** S **Assign:** coder (haiku) **Depends:** — **ADR:** 001
**Goal:** First-class fact base storage and API.
**Files:** `apps/backend/app/models.py`, `apps/backend/app/database.py`, `apps/backend/app/schemas/facts.py` (new), `apps/backend/app/routers/facts.py` (new), `apps/backend/app/main.py` (router include), `apps/backend/tests/integration/test_facts_api.py` (new)
**Constraints:** Additive only; follow existing model/facade/router patterns (mirror `applications.py`); type hints everywhere.
**Acceptance criteria:**
- [ ] `Fact` model per ADR-001 (fact_id pk, statement, context, source, metrics_json, tags_json, confidence, created_at, updated_at)
- [ ] Facade accessors in `database.py` consistent with existing collections
- [ ] `GET /api/facts` (filterable by tag/context), `POST`, `PATCH /{id}`, `DELETE /{id}`
- [ ] Integration tests: create/list/filter/update/delete + validation errors
**Test:** `cd apps/backend && uv run pytest tests/integration/test_facts_api.py`
**Out of scope:** fact extraction, any frontend, provenance links

### RH-102: Fact extraction from master resume (human-confirmed)
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** RH-101
**Goal:** LLM extracts candidate facts from the master resume's `processed_data`; user confirms before they enter the fact base.
**Files:** `apps/backend/app/prompts/` (new template, follow existing prompt-module pattern), `apps/backend/app/services/fact_extractor.py` (new), `apps/backend/app/routers/facts.py` (extend), tests in `apps/backend/tests/service/`
**Constraints:** JSON-schema-constrained LLM output via existing `llm.py` wrapper; no real LLM calls in tests (canned responses, respx/mocks per existing service tests).
**Acceptance criteria:**
- [ ] `POST /api/facts/extract` (resume_id) → list of candidate facts (`status=candidate`, not persisted to fact base)
- [ ] `POST /api/facts/confirm` accepts edited/approved candidates → persists with `confidence=verified`
- [ ] Extraction captures metrics into `metrics_json` (e.g. "$12.5M portfolio" → structured)
- [ ] Service tests with canned LLM response: happy path, malformed LLM output handled per repo error-handling pattern
**Test:** `cd apps/backend && uv run pytest tests/service/test_fact_extractor.py`
**Out of scope:** confirmation UI (P2), dedup against existing facts

### RH-103: Block variants + tags in ResumeData
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** — **ADR:** 002
**Goal:** Variant layer inside `processed_data` with full backward compatibility.
**Files:** `apps/backend/app/schemas/models.py`, `apps/backend/tests/unit/test_resume_schema_variants.py` (new)
**Constraints:** Purely additive — every existing stored `processed_data` must validate unchanged; existing schema tests must pass untouched.
**Acceptance criteria:**
- [ ] `BlockVariant {id, text, tags[], fact_ids[]}` and `BulletBlock {id, active_variant_id, variants[]}` per ADR-002
- [ ] `Experience.bullet_blocks: list[BulletBlock] = []`, `ResumeData.summary_blocks: list[BulletBlock] = []`
- [ ] Helper derives legacy `description: list[str]` from active variants when blocks non-empty (blocks win); round-trip tested both directions
- [ ] Unit tests: legacy payload validates; blocks payload round-trips; active-variant switch changes derived description
**Test:** `cd apps/backend && uv run pytest tests/unit/test_resume_schema_variants.py tests/unit`
**Out of scope:** editor UI, improver/refiner integration, renderer changes

### RH-104: Provenance lint service
**Size:** S **Assign:** coder (haiku) **Depends:** RH-101, RH-103
**Goal:** Report which resume content lacks fact provenance — the enforcement point for the no-hallucination invariant.
**Files:** `apps/backend/app/services/provenance.py` (new), `apps/backend/app/routers/resumes.py` (one endpoint), `apps/backend/tests/unit/test_provenance.py` (new)
**Constraints:** Pure function core (ResumeData in → report out); endpoint is a thin wrapper.
**Acceptance criteria:**
- [ ] `GET /api/resumes/{id}/provenance` → `{covered: n, uncovered: [{section, block_id, variant_id, text}]}`
- [ ] Variants with empty `fact_ids` and legacy bullets without blocks are reported uncovered
- [ ] Cited `fact_ids` that don't exist in the facts table are reported as `broken`
- [ ] Unit tests for all three states
**Test:** `cd apps/backend && uv run pytest tests/unit/test_provenance.py`
**Out of scope:** blocking behavior, badges UI, improver integration (P2)

### RH-105: Interest signals on applications (backend)
**Size:** S **Assign:** coder (haiku) **Depends:** —
**Goal:** Applications store weighted "why I'm interested" signals.
**Files:** `apps/backend/app/models.py` (one JSON column), `apps/backend/app/schemas/applications.py`, `apps/backend/app/routers/applications.py`, `apps/backend/app/resources/interest_dimensions.json` (new), `apps/backend/tests/integration/test_applications_interest.py` (new)
**Constraints:** Additive column (`interest_signals` JSON default `[]`); dimensions loaded from the JSON resource, never hardcoded.
**Acceptance criteria:**
- [ ] Signal shape: `{dimension, weight (int 1–5), note?}`; dimension must exist in `interest_dimensions.json` (compensation, role_scope, values_mission, growth, technology, stability_lifestyle, people)
- [ ] Create/update endpoints accept and persist signals; detail response returns them
- [ ] `GET /api/applications/interest-dimensions` returns the config for the frontend
- [ ] Tests: valid payload, unknown dimension → 422, weight out of range → 422
**Test:** `cd apps/backend && uv run pytest tests/integration/test_applications_interest.py`
**Out of scope:** UI (RH-107), career reports

### RH-106: "Considering" quick-capture
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** — **ADR:** 003
**Goal:** Log a job being considered in <30s, without a tailored resume.
**Files:** `apps/backend/app/models.py` (`Application.resume_id` → nullable), `apps/backend/app/schemas/applications.py` (`considering` status, quick-capture schema), `apps/backend/app/routers/applications.py`, `apps/backend/app/database.py` (facade guard), tests
**Constraints:** ADR-003 exactly; app-level dupe guard for (job_id, resume_id IS NULL); existing tracker tests must pass.
**Acceptance criteria:**
- [ ] `POST /api/applications/quick` with `{jd_text | jd_url?, company?, role?}` creates Job + Application(status=considering, resume_id=NULL) in one call
- [ ] Duplicate considering-card for same job → 409
- [ ] Later attach of tailored resume updates the same card (no new card)
- [ ] Status enum ordering puts `considering` first; existing statuses unchanged
**Test:** `cd apps/backend && uv run pytest tests/integration -k application`
**Out of scope:** JD URL fetching (store URL as text for now), frontend column (RH-107)

### RH-107: Tracker UI — considering column + interest quick-tags
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** RH-105, RH-106
**Goal:** Kanban gains a "Considering" column; card modal and add-dialog gain the interest quick-tag panel.
**Files:** `apps/frontend/components/tracker/kanban-board.tsx`, `kanban-column.tsx`, `card-detail-modal.tsx`, `manual-add-application-dialog.tsx`, `apps/frontend/lib/api/tracker.ts`, `apps/frontend/messages/*.json` (ALL 5 locales — pre-push parity check)
**Constraints:** Swiss International Style (docs/portable/swiss-design-system/) — no rounded corners, tokens only; Enter-key textarea fix per CLAUDE.md.
**Acceptance criteria:**
- [ ] "Considering" column renders first; cards without a resume hide/disable "Edit resume"
- [ ] Quick-tag panel: dimensions fetched from API, toggle + 1–5 weight + optional note; persists via PATCH
- [ ] Signals summarized on the card (compact chips, metadata font)
- [ ] All 5 locale files updated; `npm run lint` and `npm run test` pass
**Test:** `cd apps/frontend && npm run test && npm run lint`
**Out of scope:** career intelligence dashboard, drag-reorder changes

## P2 (preview — do not start; tickets cut after P1 review)
Interview mode (gap Q&A → new facts) · fact-confirmation + variant editor UI · provenance badges · clickable ATS gaps → interview mode · dedup import of old resumes · "Tim" PDF template · .docx export · improver emits fact_ids

## Icebox
Career intelligence engine (P3) · outcome overlay (P3) · JobSpy intake, JD library, multi-JD tailoring (P4) · thank-you email prompt profile on cover-letter module (P4)
