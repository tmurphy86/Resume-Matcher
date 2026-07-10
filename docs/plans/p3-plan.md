# P3 Plan — Career intelligence + P2 carryovers

> Source: docs/BACKLOG.md (P3 section). Context: docs/reviews/P2-review.md.
> Execution order: Tasks 1–4 independent; Task 5 depends on Task 3; Task 6 on Task 5; Tasks 7–8 on Task 6 (Task 8 also on Task 4).
> Branch baseline: 6c8d4a9 (P2 Complete).

## Global Constraints

- All Python functions must have type hints (params + return).
- All frontend UI changes follow Swiss International Style: tokens only (no rounded corners), borders `rounded-none`, 1px black, hard shadows. Canvas `#F0F0E8`, ink `#000000`, headers `font-serif`, body `font-sans`, metadata `font-mono`. No chart libs — typographic/tabular presentation only.
- All 6 locale files (`en`, `es`, `zh`, `ja`, `pt`, `fr`) must be updated for any user-facing string. Pre-push parity check enforces this.
- `npm run lint` and `npm run format` must pass for any frontend change.
- Log detailed errors server-side; return generic messages to clients (`raise HTTPException(status_code=500, detail="Operation failed. Please try again.")`).
- Use `copy.deepcopy()` for any mutable default or before mutating cached/shared data.
- New backend endpoints mount under `/api/v1` via `app/routers/__init__.py`.
- Anti-hallucination invariant: no code path may render LLM-generated resume content without `fact_ids` provenance.
- No real LLM calls in tests — use canned responses / respx mocks per existing service test patterns.
- Enter-key textarea fix on all textareas: `if (e.key === 'Enter') e.stopPropagation()`.
- Additive storage only: never drop columns or tables; never remove existing statuses.
- Tests must be anti-theater: a test must fail when its target breaks.

---

## Task 1: RH-301 Variant editor (P2 carryover)

**Ticket:** RH-301
**Size:** M **Agent:** senior-coder
**Finding:** P2-F1 — RH-205 shipped without the variant editor (criterion 1 of its spec)
**Goal:** Humans can see, switch, tag, and author block variants in the tailor/builder UI.

**Files:**
- `apps/frontend/components/tailor/` and/or `components/builder/` (block variant UI additions)
- `apps/frontend/lib/api/resume.ts` (any new API calls needed)
- `apps/frontend/messages/*.json` (all 6 locales — en, es, zh, ja, pt, fr)
- Vitest tests for the new components

**Constraints:**
- Swiss International Style (no chart libs, rounded-none, tokens only)
- Enter-key textarea fix on all textareas
- Blocks-less legacy sections must degrade gracefully (no variant UI shown)
- The PATCH resume endpoint already accepts `processed_data` updates — use it

**Acceptance criteria:**
- [ ] Each block with variants shows them (tag chips visible); switching `active_variant_id` persists via PATCH `/api/v1/resumes/{id}` and updates the UI preview without a full page re-render
- [ ] "Save as variant" on any edited/accepted diff text (with tag selection) writes a new `BlockVariant` carrying the diff's `fact_ids` onto the block's `variants` array and PATCHes the resume
- [ ] Blocks-less legacy sections degrade gracefully (no variant UI shown)
- [ ] All 6 locales updated; `npm run lint` and `npm run test` pass

**Test command:** `cd apps/frontend && npm run test && npm run lint`

**Out of scope:** variant analytics, bulk operations, backend schema changes (BlockVariant already exists in `app/schemas/models.py`)

---

## Task 2: RH-302 Import persists variant_of phrasings (P2 carryover)

**Ticket:** RH-302
**Size:** S **Agent:** coder
**Finding:** P2-F2 — RH-210 never persists variant_of phrasings to blocks
**Goal:** Confirming a `variant_of` candidate writes its phrasing onto the matched fact's master-resume blocks.

**Files:**
- `apps/backend/app/services/fact_extractor.py` (extend confirm logic)
- `apps/backend/app/routers/facts.py` (new or extended endpoint)
- `apps/frontend/app/(default)/facts/page.tsx` (import modal confirm handler)
- `apps/backend/tests/service/test_fact_extractor.py` (extend)

**Constraints:**
- New endpoint (or extended `/facts/confirm`) accepts `{candidate, existing_fact_id, accept_as_variant: true}` → appends `BlockVariant(text=candidate.statement, fact_ids=[existing_fact_id])` to the master-resume block(s) citing that fact; creates a block if none cites it
- Dedup guard: same text must not be appended twice to the same block
- Uses the existing `BlockVariant` schema from `app/schemas/models.py`
- The master resume's `processed_data` is stored as JSON in the DB; the facade's `get_resume` / `update_resume` methods handle reads/writes

**Acceptance criteria:**
- [ ] New endpoint (or extended confirm) accepts `{candidate, existing_fact_id, accept_as_variant: true}` → appends `BlockVariant` to master-resume block(s) citing that fact; creates a block if none cites it
- [ ] Import modal confirm actually calls it for checked `variant_of` rows
- [ ] Tests: variant appended, block created when absent, dedup (same text not appended twice)

**Test command:** `cd apps/backend && uv run pytest tests/service/test_fact_extractor.py`

**Out of scope:** frontend for creating blocks from scratch, variant editor UI (Task 1)

---

## Task 3: RH-303 Structured JD parsing

**Ticket:** RH-303
**Size:** S **Agent:** coder
**Goal:** Every job stores `parsed {responsibilities[], requirements[], level?, comp?}` for the career intelligence layer.

**Files:**
- `apps/backend/app/prompts/templates.py` (new `JD_PARSE_PROMPT` constant, follow existing prompt pattern with `{output_language}` and doubled braces for literal JSON)
- `apps/backend/app/services/jd_parser.py` (new service)
- `apps/backend/app/routers/jobs.py` (parse on upload + backfill endpoint)
- `apps/backend/tests/service/test_jd_parser.py` (new, canned LLM responses)

**Constraints:**
- Result stored in `jobs.metadata_json["parsed"]` — the `Job` model already has a `metadata_json` column (dict); use the dynamic-key pattern per ADR-005: read→merge→write, never full replacement
- Malformed LLM output → logged, job saved without `parsed` key (never blocks upload)
- No real LLM calls in tests (canned responses via mocks per existing service tests)
- New endpoint mounts under `/api/v1` via `app/routers/__init__.py`

**Acceptance criteria:**
- [ ] JD upload (`POST /api/v1/jobs/upload`) triggers parse; result stored in `jobs.metadata_json["parsed"]` as `{responsibilities: [], requirements: [], level?: str, comp?: str}`
- [ ] `POST /api/v1/jobs/backfill-parse` parses existing jobs missing `parsed` (idempotent — skip if `parsed` already present)
- [ ] Malformed LLM output → logged, job saved/left without `parsed` (never blocks upload)
- [ ] Service tests with canned LLM response: happy path, malformed output handled gracefully

**Test command:** `cd apps/backend && uv run pytest tests/service/test_jd_parser.py`

**Out of scope:** frontend display of parsed JD fields, archetype clustering (Task 5)

---

## Task 4: RH-307 Application status history (outcome events)

**Ticket:** RH-307
**Size:** S **Agent:** coder
**Goal:** Every status transition recorded for outcome analytics.

**Files:**
- `apps/backend/app/models.py` (`status_history` JSON column on `Application`)
- `apps/backend/app/database.py` (facade guard — append to history on every status-changing write)
- `apps/backend/app/routers/applications.py` (all status-changing paths)
- `apps/backend/tests/integration/` (extend existing application tests)

**Constraints:**
- `status_history` is a JSON column defaulting to `[]`; each entry is `{status: str, at: str (ISO 8601)}`
- Additive column — existing `status` behavior unchanged; existing application tests must still pass
- All status-changing paths: single PATCH, bulk move, quick-capture create — all must append
- Backfill: existing applications missing `status_history` get seeded `[{status: current_status, at: updated_at}]` on their next write (not a migration — lazy seed)

**Acceptance criteria:**
- [ ] `status_history` JSON column added to `Application` model, default `[]`
- [ ] All status-changing paths append `{status, at}` entry
- [ ] Quick-capture create seeds history with initial `considering` entry
- [ ] Backfill: existing apps without history get seeded on next write
- [ ] Tests: transition append, bulk append, seed behavior

**Test command:** `cd apps/backend && uv run pytest tests/integration -k application`

**Out of scope:** analytics display (Task 8), any frontend changes

---

## Task 5: RH-304 Archetype clustering + career_reports storage

**Ticket:** RH-304
**Size:** M **Agent:** senior-coder
**Depends:** Task 3 (RH-303 — jobs must have `parsed` field)

**Goal:** Cluster responsibilities across all parsed JDs into named role archetypes; persist report skeleton.

**Files:**
- `apps/backend/app/models.py` (`CareerReport` model per ADR-005)
- `apps/backend/app/database.py` (facade accessors for career_reports)
- `apps/backend/app/prompts/templates.py` (clustering template)
- `apps/backend/app/services/career_intelligence.py` (new)
- `apps/backend/app/routers/career.py` (new)
- `apps/backend/app/routers/__init__.py` (include new router)
- `apps/backend/app/main.py` (if needed for router mount)
- `apps/backend/tests/service/test_career_intelligence.py` (new)

**Constraints:**
- `CareerReport` per ADR-005: columns `id`, `created_at`, `archetypes_json`, `jd_ids_json`, `scores_json` (nullable), `advice_md` (nullable), `model_used` (nullable)
- Clustering prompt: JSON-schema-constrained output `{archetypes: [{name, description, jd_ids, responsibilities}]}`; every source JD must be assigned to exactly one archetype
- Malformed LLM output → logged, raise appropriate HTTP error (do not persist partial data)
- No real LLM calls in tests; use canned responses

**Acceptance criteria:**
- [ ] `CareerReport` model added to `models.py`; table created via existing engine init pattern
- [ ] Facade accessors: `create_career_report`, `get_career_reports`, `get_career_report`
- [ ] `POST /api/v1/career/cluster` runs clustering over jobs with `parsed`; persists partial `CareerReport` (archetypes_json, jd_ids_json set; scores/advice NULL)
- [ ] `GET /api/v1/career/reports` + `GET /api/v1/career/reports/{id}` list/fetch history
- [ ] Canned-response tests including malformed output

**Test command:** `cd apps/backend && uv run pytest tests/service/test_career_intelligence.py`

**Out of scope:** scores, narrative (Task 6)

---

## Task 6: RH-305 Attraction/fit scoring + advice narrative

**Ticket:** RH-305
**Size:** M **Agent:** senior-coder
**Depends:** Task 5 (RH-304 — CareerReport model + clustering)

**Goal:** The full career report: deterministic scores + cited LLM narrative.

**Files:**
- `apps/backend/app/services/career_intelligence.py` (extend)
- `apps/backend/app/prompts/templates.py` (advice narrative template)
- `apps/backend/app/routers/career.py` (extend with `POST /career/report`)
- `apps/backend/tests/service/test_career_intelligence.py` (extend)
- `apps/backend/tests/unit/test_career_scores.py` (new — pure scoring logic)

**Constraints:**
- Deterministic scores (pure Python, no LLM): attraction = weighted mean of member applications' `interest_signals` by dimension; fit = fact/requirement coverage ratio (fact_ids in master resume blocks vs. parsed JD requirements); gap list = requirements with no supporting fact
- LLM narrative must cite only `fact_ids`, `jd_ids`, and computed scores in structured output — cited IDs validated to exist in DB, else report flagged (`advice_md` set to error marker, not silently accepted)
- Report persisted complete: `scores_json`, `advice_md`, `model_used` updated on the existing `CareerReport` row from clustering
- Numbers must be reproducible: identical inputs → identical scores (unit test asserts equality)
- No real LLM calls in tests

**Acceptance criteria:**
- [ ] Deterministic scoring (pure Python): attraction, fit, gap list per archetype
- [ ] `POST /api/v1/career/report` computes scores → LLM narrative → validates cited IDs → persists complete report
- [ ] Narrative template targets: "target / stretch w/ gap-closing plans / deprioritize / market observations"
- [ ] Cited IDs validated; invalid → report flagged (not silently accepted)
- [ ] Unit tests assert score reproducibility with identical inputs
- [ ] Full suite test count confirmed passing

**Test command:** `cd apps/backend && uv run pytest tests/service/test_career_intelligence.py tests/unit/test_career_scores.py`

**Out of scope:** frontend display (Task 7), outcome overlay (Task 8)

---

## Task 7: RH-306 Career intelligence dashboard UI

**Ticket:** RH-306
**Size:** M **Agent:** senior-coder
**Depends:** Task 6 (RH-305 — career report API)

**Goal:** `/career` page — archetypes, attraction×fit quadrant view, gaps, report history.

**Files:**
- `apps/frontend/app/(default)/career/page.tsx` (new page)
- `apps/frontend/lib/api/career.ts` (new API client)
- `apps/frontend/messages/*.json` (all 6 locales)
- Vitest tests

**Constraints:**
- Swiss International Style: no chart libs — typographic/tabular presentation only; tokens only; rounded-none; 1px black borders; hard shadows
- Attraction×fit 2×2 is a text/table layout, NOT a canvas/SVG chart: four labeled quadrant cells (Want & Can Get / Stretch / Deprioritize / Market), archetype names placed in their cell
- Gap items link to interview mode panel (existing RH-206 pattern — `selectedGap` state on the tailor page)
- `advice_md` rendered as markdown prose
- Enter-key textarea fix on all textareas

**Acceptance criteria:**
- [ ] Archetype cards: name, member JD count, attraction score, fit score, top gaps; Swiss tokens
- [ ] Attraction×fit 2×2 placement (typographic/tabular — no chart libs)
- [ ] Gap items link to interview mode (RH-206 panel pattern)
- [ ] "Generate report" button calls `POST /career/report`; history list shows past reports with `advice_md` rendered
- [ ] All 6 locales updated; `npm run lint` and `npm run test` pass

**Test command:** `cd apps/frontend && npm run test && npm run lint`

**Out of scope:** outcome overlay (Task 8), real-time updates

---

## Task 8: RH-308 Outcome overlay + report nudge

**Ticket:** RH-308
**Size:** S **Agent:** coder
**Depends:** Task 6 (RH-305 — career report), Task 4 (RH-307 — status_history)

**Goal:** Response/interview rates per archetype; refresh reminder banner when report is stale.

**Files:**
- `apps/backend/app/services/career_intelligence.py` (deterministic overlay calc)
- `apps/frontend/app/(default)/career/page.tsx` (overlay display + nudge banner)
- `apps/frontend/messages/*.json` (all 6 locales)
- `apps/backend/tests/unit/test_career_scores.py` (extend)
- `apps/frontend/` vitest tests

**Constraints:**
- Per archetype: response rate = applications that reached `response` status or later / total; interview rate = reached `interview` or later / total — computed from `status_history` (not current `status` alone)
- Stale-report banner: client-side check — count applications created after the latest report's `created_at`; show banner if ≥5
- No scheduler, no backend polling endpoint for staleness — pure client-side check against data already fetched
- Deterministic: unit tests assert exact rates with known inputs

**Acceptance criteria:**
- [ ] Per archetype response rate + interview rate computed from `status_history`; deterministic unit tests
- [ ] Career page shows these rates on archetype cards
- [ ] "Report stale — N new applications since last report" banner appears when ≥5 applications post-date latest report
- [ ] All 6 locales; `npm run lint` and `npm run test` pass

**Test command:** `cd apps/backend && uv run pytest tests/unit/test_career_scores.py && cd ../../frontend && npm run test`

**Out of scope:** scheduler, push notifications, email nudges
