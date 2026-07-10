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

## P3 — Career intelligence (+ mandatory P2 carryovers)
> Context: [reviews/P2-review.md](reviews/P2-review.md) (findings F1/F2 → RH-301/302), [ADR-005](decisions/005-career-intelligence-architecture.md) (deterministic numbers, LLM narrative). RH-301/302 ship first — they are unmet P2 acceptance criteria, not new features.

### RH-301: Variant editor (P2 carryover — RH-205 criterion 1)
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** — **Finding:** P2-F1
**Goal:** Humans can see, switch, tag, and author block variants.
**Files:** `apps/frontend/components/tailor/` and/or `components/builder/` (block variant UI), `apps/frontend/lib/api/resume.ts`, locales, tests
**Acceptance criteria:**
- [ ] Each block with variants shows them (tag chips visible); switching `active_variant_id` persists and updates preview without full re-render
- [ ] "Save as variant" on any edited/accepted diff text (with tag selection) writes a new `BlockVariant` carrying the diff's fact_ids
- [ ] Blocks-less legacy sections degrade gracefully (no variant UI shown)
- [ ] All 6 locales; lint + vitest pass
**Test:** `cd apps/frontend && npm run test && npm run lint`
**Out of scope:** variant analytics, bulk operations

### RH-302: Import persists variant_of phrasings (P2 carryover — RH-210 criterion 3)
**Size:** S **Assign:** coder (haiku) **Depends:** — **Finding:** P2-F2
**Goal:** Confirming a `variant_of` candidate writes its phrasing onto the matched fact's master-resume blocks.
**Files:** `apps/backend/app/services/fact_extractor.py`, `apps/backend/app/routers/facts.py`, facts page import modal confirm handler, tests
**Acceptance criteria:**
- [ ] New endpoint (or extended confirm) accepts `{candidate, existing_fact_id, accept_as_variant: true}` → appends `BlockVariant(text=candidate.statement, fact_ids=[existing_fact_id])` to the master-resume block(s) citing that fact; creates a block if none cites it
- [ ] Import modal confirm actually calls it for checked variant_of rows
- [ ] Tests: variant appended, block created when absent, dedup (same text not appended twice)
**Test:** `cd apps/backend && uv run pytest tests/service/test_fact_extractor.py`

### RH-303: Structured JD parsing
**Size:** S **Assign:** coder (haiku) **Depends:** — **ADR:** 005
**Goal:** Every job stores `parsed {responsibilities[], requirements[], level?, comp?}` for the intelligence layer.
**Files:** `apps/backend/app/prompts/` (new template), `apps/backend/app/services/jd_parser.py` (new), `apps/backend/app/routers/jobs.py` (parse on upload + backfill endpoint), tests (canned LLM)
**Acceptance criteria:**
- [ ] JD upload triggers parse; result stored in `jobs.metadata_json["parsed"]` (facade dynamic-key pattern per ADR-005)
- [ ] `POST /api/jobs/backfill-parse` parses existing jobs missing `parsed`
- [ ] Malformed LLM output → logged, job saved without `parsed` (never blocks upload)
**Test:** `cd apps/backend && uv run pytest tests/service/test_jd_parser.py`

### RH-304: Archetype clustering + career_reports storage
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** RH-303 **ADR:** 005
**Goal:** Cluster responsibilities across all parsed JDs into named role archetypes; persist reports skeleton.
**Files:** `apps/backend/app/models.py` (`CareerReport` per ADR-005), `apps/backend/app/database.py` (facade), `apps/backend/app/prompts/` (clustering template), `apps/backend/app/services/career_intelligence.py` (new), `apps/backend/app/routers/career.py` (new), `apps/backend/app/main.py`, tests
**Acceptance criteria:**
- [ ] Clustering prompt: JSON-schema-constrained `{archetypes: [{name, description, jd_ids, responsibilities}]}`; every source JD assigned; canned-response tests incl. malformed output
- [ ] `POST /api/career/cluster` runs clustering over jobs with `parsed`; persists partial `CareerReport` (archetypes_json, jd_ids_json)
- [ ] `GET /api/career/reports` + `GET /api/career/reports/{id}` list/fetch history
**Test:** `cd apps/backend && uv run pytest tests/service/test_career_intelligence.py`
**Out of scope:** scores, narrative (RH-305)

### RH-305: Attraction/fit scoring + advice narrative
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** RH-304 **ADR:** 005
**Goal:** The full report: deterministic scores + cited narrative.
**Files:** `apps/backend/app/services/career_intelligence.py`, `apps/backend/app/prompts/` (advice template), tests
**Acceptance criteria:**
- [ ] **Deterministic (pure Python, unit-tested):** per archetype — attraction = weighted mean of member applications' interest signals by dimension; fit = fact/requirement coverage ratio (reuse provenance/keyword machinery); gap list = requirements with no supporting fact
- [ ] `POST /api/career/report` computes scores, then LLM narrative (target / stretch w/ gap-closing plans / deprioritize / market observations); narrative cites only fact_ids, jd_ids, and computed scores — cited IDs validated to exist, else report flagged
- [ ] Report persisted complete (scores_json, advice_md, model_used); numbers reproducible across runs with identical inputs (test asserts equality)
**Test:** `cd apps/backend && uv run pytest tests/service/test_career_intelligence.py tests/unit/test_career_scores.py`

### RH-306: Career intelligence dashboard UI
**Size:** M **Assign:** senior-coder (sonnet) **Depends:** RH-305
**Goal:** `/career` page: archetypes, attraction×fit view, gaps, report history.
**Files:** `apps/frontend/app/(default)/career/` (new), `apps/frontend/lib/api/career.ts` (new), locales, tests
**Acceptance criteria:**
- [ ] Archetype cards: name, member JD count, attraction score, fit score, top gaps; Swiss tokens (no charts libs — typographic/tabular presentation)
- [ ] Attraction×fit 2×2 placement (want×can-get / stretch / deprioritize quadrants)
- [ ] Gap items link to interview mode (existing RH-206 panel pattern); "Generate report" + history list w/ advice_md rendered
- [ ] All 6 locales; lint + vitest pass
**Test:** `cd apps/frontend && npm run test && npm run lint`

### RH-307: Application status history (outcome events)
**Size:** S **Assign:** coder (haiku) **Depends:** — **ADR:** 005
**Goal:** Every status transition recorded for outcome analytics.
**Files:** `apps/backend/app/models.py` (`status_history` JSON column), `apps/backend/app/database.py`, `apps/backend/app/routers/applications.py`, tests
**Acceptance criteria:**
- [ ] All status-changing paths (single PATCH, bulk move, quick-capture create) append `{status, at}`; existing `status` behavior unchanged
- [ ] Backfill: existing applications get seeded history `[{current status, updated_at}]` on first write
- [ ] Tests: transition append, bulk append, seed
**Test:** `cd apps/backend && uv run pytest tests/integration -k application`

### RH-308: Outcome overlay + report nudge
**Size:** S **Assign:** coder (haiku) **Depends:** RH-305, RH-307
**Goal:** Response/interview rates per archetype; refresh reminder.
**Files:** `apps/backend/app/services/career_intelligence.py` (deterministic overlay calc), `apps/frontend/app/(default)/career/` (overlay display + nudge banner), locales, tests
**Acceptance criteria:**
- [ ] Per archetype: response rate (reached `response`+) and interview rate (reached `interview`+) from status_history; deterministic unit tests
- [ ] Career page shows a "report stale — N new applications since last report" banner when ≥5 applications post-date the latest report (client-side check; no scheduler)
**Test:** `cd apps/backend && uv run pytest tests/unit/test_career_scores.py && cd ../frontend && npm run test`

## Icebox
JobSpy intake, JD library, multi-JD tailoring (P4) · thank-you email prompt profile on cover-letter module (P4) · styled "pretty docx" (per ADR-004)
