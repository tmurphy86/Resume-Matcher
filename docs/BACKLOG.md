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

## P2 — Wire the layers in (tailor-loop hardening)
> Context: [reviews/P1-review.md](reviews/P1-review.md). P1 built the fact/variant/provenance layers; P2 makes the pipeline and the human actually use them. F1 is the critical path.

### RH-201: Improver reads/writes blocks with fact provenance
**Size:** L (split if needed) **Assign:** senior-coder (sonnet) **Depends:** — **Finding:** F1
**Goal:** Tailoring operates on `bullet_blocks`/`summary_blocks`, not legacy `description`; every generated variant carries `fact_ids`.
**Files:** `apps/backend/app/services/improver.py`, `apps/backend/app/prompts/` (tailoring templates), `apps/backend/app/services/provenance.py` (integration point), service tests
**Constraints:** Facts relevant to the resume are injected into the tailoring prompt; LLM output schema requires `fact_ids[]` per rewritten block; blocks-less legacy resumes auto-wrap into single-variant blocks on first tailor. No real LLM calls in tests.
**Acceptance criteria:**
- [ ] Tailored resume `processed_data` contains blocks; legacy `description` derived, not authored
- [ ] Each generated variant cites ≥1 valid fact_id OR is returned in an `unverified[]` list — never silently included
- [ ] Improve response includes the provenance report (`covered/uncovered/broken`)
- [ ] Existing improver tests still pass; new tests: fact injection, unverified segregation, legacy auto-wrap
**Test:** `cd apps/backend && uv run pytest tests/service -k improver or provenance`
**Out of scope:** refiner.py (RH-202), any UI

### RH-202: Interview mode — gaps become questions, answers become facts
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** RH-201
**Goal:** The anti-hallucination Q&A loop.
**Files:** `apps/backend/app/services/interview_mode.py` (new — distinct from interview_prep), `apps/backend/app/prompts/`, `apps/backend/app/routers/facts.py` (extend), tests
**Acceptance criteria:**
- [ ] `POST /api/facts/gap-questions` (job_id, resume_id) → structured questions for JD requirements with no supporting fact (uses RH-201's unverified list + JD keywords)
- [ ] `POST /api/facts/answer` persists answers as facts (`confidence=user_answered`, `source=interview`), returns updated gap list
- [ ] Refiner honors new facts on next pass (integration test with canned LLM)
**Test:** `cd apps/backend && uv run pytest tests/service/test_interview_mode.py`
**Out of scope:** chat UI (RH-205 exposes it minimally)

### RH-203: Fact dedup on confirm + re-extract
**Size:** S **Assign:** coder (haiku) **Depends:** — **Finding:** F2
**Goal:** Confirming the same fact twice must not duplicate it.
**Files:** `apps/backend/app/services/fact_extractor.py`, `apps/backend/app/schemas/facts.py`, tests
**Constraints:** Deterministic — stdlib `difflib.SequenceMatcher` on normalized statements (threshold 0.9); no new deps, no embeddings, no LLM.
**Acceptance criteria:**
- [ ] `POST /facts/confirm` flags near-duplicates of existing facts → returned as `{status: "duplicate", existing_fact_id}` instead of inserted
- [ ] `POST /facts/extract` annotates candidates already covered by existing facts
- [ ] Tests: exact dup, near dup (>0.9), distinct fact below threshold
**Test:** `cd apps/backend && uv run pytest tests/service/test_fact_extractor.py`
**Out of scope:** merge UI, embedding similarity

### RH-204: Facts library + extraction review UI
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** RH-203 **Finding:** F3
**Goal:** Human surface for the fact base: list/filter/edit facts; run extraction; review/edit/confirm candidates.
**Files:** `apps/frontend/app/(default)/facts/` (new page), `apps/frontend/lib/api/facts.ts` (new), `apps/frontend/messages/*.json` (all locales), vitest API tests
**Constraints:** Swiss design system; metadata font for fact IDs/sources; textarea Enter-key fix.
**Acceptance criteria:**
- [ ] Facts page: table w/ tag+context filters, inline edit, delete w/ confirm
- [ ] "Extract from master" flow: candidates listed w/ dup annotations, editable, confirm selected
- [ ] All locales updated; lint + vitest pass
**Test:** `cd apps/frontend && npm run test && npm run lint`

### RH-205: Variant editor + provenance badges in tailor view
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** RH-201 **Finding:** F3
**Goal:** Per-block variant switching and visible provenance in the resume editor.
**Files:** `apps/frontend/components/tailor/` (block editor additions), `apps/frontend/lib/api/resume.ts`, locales, tests
**Acceptance criteria:**
- [ ] Each block shows its variants (tags visible); switching active variant updates preview without full re-render
- [ ] Provenance badge per block: covered (fact count) / uncovered / broken — uncovered+broken use alert tokens; hover reveals cited facts
- [ ] Unverified LLM suggestions (RH-201) rendered in a distinct "needs verification" state with a shortcut to interview-mode questions (RH-202 endpoint)
**Test:** `cd apps/frontend && npm run test && npm run lint`

### RH-206: Clickable ATS gaps → interview mode
**Size:** S **Assign:** coder (haiku) **Depends:** RH-202, RH-205
**Goal:** Missing-keyword items in the ATS score card deep-link into gap questions.
**Files:** `apps/frontend/components/tailor/ats-score-card.tsx`, locales, tests
**Acceptance criteria:**
- [ ] Each missing keyword renders as an action chip → opens interview-mode panel pre-filtered to that gap
- [ ] Covered keywords unchanged; lint passes
**Test:** `cd apps/frontend && npm run test && npm run lint`

### RH-207: "Murphy" resume template
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** —
**Goal:** Pixel-faithful template of Tim's current resume design (black name bar w/ letter-spaced caps, thin-rule small-caps section headers, gray competency band, serif-free body, mono contact line).
**Files:** `apps/frontend/components/resume/resume-murphy.tsx` (new) + `styles/murphy.module.css` (new), template registration (follow resume-modern.tsx pattern), print route compatibility
**Reference:** docs/reference/tim-resume-original.pdf (Tim: drop the PDF here)
**Acceptance criteria:**
- [ ] Renders master resume across 3 pages matching the reference layout (header, overview, competency band, experience w/ right-aligned dates, education, two-tier skills)
- [ ] Print/PDF output paginates cleanly (page-container/use-pagination)
- [ ] Registered in template picker; lint passes
**Test:** `cd apps/frontend && npm run test && npm run lint` + manual PDF export check
**Out of scope:** .docx (RH-208)

### RH-208: .docx export (ATS-safe)
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** — **ADR:** 004
**Goal:** Export any resume as an ATS-safe .docx.
**Files:** `apps/backend/app/services/docx_export.py` (new), `apps/backend/app/routers/resumes.py` (endpoint), `apps/backend/pyproject.toml` (add `python-docx` — approved dep), tests
**Constraints:** ADR-004 — `python-docx`, imperative construction from `ResumeData`. Target is **ATS-safe structural fidelity, NOT pixel fidelity** (Murphy PDF is the pixel artifact): real heading styles, real bullet lists, no text boxes, no floating elements, minimal tables. Simple parser-friendly approximations only for the header/competency band.
**Acceptance criteria:**
- [ ] `GET /api/resumes/{id}/export/docx` streams a valid .docx with correct section ordering (contact, overview, competencies, experience w/ dates, education, skills)
- [ ] Headings use Word heading styles; bullets use list styles (not manual "• " strings)
- [ ] Deterministic test opens the generated BytesIO with python-docx and asserts heading text, section order, bullet counts
- [ ] Works for both blocks-based and legacy resumes (derived description path)
**Test:** `cd apps/backend && uv run pytest tests/service/test_docx_export.py`
**Out of scope:** styled "pretty" docx (future ticket per ADR-004), frontend download button styling beyond the existing export pattern

### RH-209: Test hygiene
**Size:** S **Assign:** coder (haiku) **Depends:** — **Finding:** F4
**Goal:** Green suite, no noise.
**Files:** `apps/frontend/tests/` (resume-wizard-page/viewer failures), `apps/frontend/components/tracker/kanban-board.tsx` (stale "seven columns" comment)
**Acceptance criteria:**
- [ ] 11 pre-existing frontend failures fixed or (if truly obsolete) each removal justified in the report — never silently deleted
- [ ] Full frontend suite green
**Test:** `cd apps/frontend && npm run test`

### RH-210: Old-resume dedup import
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** RH-203, RH-204
**Goal:** Import legacy resumes; near-duplicate bullets cluster onto existing facts/variants for review instead of creating noise.
**Files:** `apps/backend/app/services/fact_extractor.py` (extend), `apps/backend/app/routers/facts.py`, facts UI import flow, tests
**Acceptance criteria:**
- [ ] Upload old resume → extraction runs → candidates grouped: `new` / `duplicate` / `variant_of` (similar statement, different phrasing → offered as new variant text on the existing fact's blocks)
- [ ] Confirm flow persists variants to master-resume blocks where applicable
- [ ] Tests cover all three groupings
**Test:** `cd apps/backend && uv run pytest tests/service/test_fact_extractor.py`

## Icebox
Career intelligence engine (P3: responsibility clustering, attraction/fit analysis, advice reports) · outcome overlay (P3) · JobSpy intake, JD library, multi-JD tailoring (P4) · thank-you email prompt profile on cover-letter module (P4)
