# Resume Hulk — Project State

> Sync file between the Cowork program lead (Fable) and the Claude Code engineering lead.
> Eng lead: update at the END of every session. Program lead: read at the START of every planning session.

## Current milestone
**P2 — Wire the layers in** (tickets RH-201…RH-210 in [BACKLOG.md](BACKLOG.md)). P1 ACCEPTED — see [reviews/P1-review.md](reviews/P1-review.md).
Recommended dispatch order: wave 1 = RH-201, RH-203, RH-207, RH-209 (independent); wave 2 = RH-202, RH-204, RH-208; wave 3 = RH-205, RH-206, RH-210.

## Baseline (2026-07-09, commit dd9b5c3)
- Fork of srbhr/Resume-Matcher running locally; Tim's resume uploaded; no issues.
- Stack (differs from upstream README): FastAPI + Python 3.13, SQLite via SQLAlchemy 2.0 async, Next.js 16 + React 19, LiteLLM, Playwright PDF.
- Already present: master resume w/ parent lineage (`Resume.is_master`, `parent_id`), tailoring pipeline (`services/improver.py`, `refiner.py`), ATS scoring w/ sub-scores (`services/ats.py`), Kanban application tracker (`routers/applications.py`, `components/tracker/`), cover letter + outreach (`services/cover_letter.py`), interview prep (`services/interview_prep.py`), resume wizard, enrichment, i18n (5 locales), ~444 backend tests + vitest, pre-push hook gate.
- NOT present (Resume Hulk differentiators): fact base, block variants w/ tags, provenance links, anti-hallucination interview mode, interest signals, career intelligence, dedup import of old resumes.

## Shipped
- **RH-101** `feat(facts): RH-101 facts table + CRUD` (afa5038) — `Fact` model, database facade, `schemas/facts.py`, `routers/facts.py` (GET/POST/PATCH/DELETE `/api/v1/facts`), 14 integration tests. ✅
- **RH-102** `feat(facts): RH-102 fact extraction from master resume` (a904ba6) — `FACT_EXTRACTION_PROMPT`, `fact_extractor` service, `POST /facts/extract` + `POST /facts/confirm`; 8 service tests (mocked LLM). ✅
- **RH-103** `feat(schema): RH-103 block variants + tags in ResumeData` (e3cb66b) — `BlockVariant`, `BulletBlock` models; `Experience.bullet_blocks`, `ResumeData.summary_blocks`; active-variant derivation; 17 unit tests. ✅
- **RH-104** `feat(provenance): RH-104 provenance lint service` (7fe672f) — pure `check_provenance()` function; `GET /resumes/{id}/provenance`; 13 unit tests covering covered/uncovered/broken/legacy states. ✅
- **RH-105** `feat(tracker): RH-105 interest signals on applications` (1619bdc) — `interest_signals` JSON column; `GET /applications/interest-dimensions`; PATCH validation (422); 11 integration tests. ✅
- **RH-106** `feat(tracker): RH-106 considering quick-capture` (1aa3bd6) — `Application.resume_id` nullable; `considering` status; `POST /applications/quick`; 7 integration tests. ✅
- **RH-107** `feat(tracker): RH-107 considering column + interest quick-tags` (3fa1e83) — frontend: considering column, interest signal chips + panel, quick-capture mode in add dialog; all 6 locales updated (also fixed fr.json parity gap); 4 new API tests. ✅

## In flight
_(none — wave 3 complete, P2 complete)_

## Blockers
_(none)_

## DECISION NEEDED
_(none)_

## Shipped (P2 wave 3 — 2026-07-10)
- **RH-205** `feat(rh205): provenance badges and unverified-change warnings in tailor view` (81bcd20) — `ProvenancePanel` component (covered/uncovered/broken status bar, verify-gaps link, unverified count); `Data` interface extended with `provenance`/`unverified`; DiffPreviewModal marks unverified changes with amber badge; tailor page renders panel post-improve; `tailor.provenance` i18n in all 6 locales; 8 new vitest tests. ✅
- **RH-206** `feat(tailor): RH-206 clickable ATS gaps → interview mode panel` (4930f60) — missing keyword chips become clickable buttons; ProvenancePanel gains `selectedKeyword` highlight bar; tailor page wires chip→panel selection; `selectedGap`/`clearGap` i18n keys in all 6 locales; 10 new vitest tests. ✅
- **RH-210** `feat(facts): RH-210 old-resume dedup import with variant-of grouping` (2616065) — `import_resume_facts()` with new/duplicate/variant_of grouping (threshold 0.5/0.9); `POST /facts/import-resume`; "Import old resume" modal in facts page with colour-coded groups; `facts.importModal` i18n keys; 5 new backend service tests; 630 backend / 220 frontend passing. ✅

## Shipped (P2 wave 2 — 2026-07-09)
- **RH-202** `feat(interview-mode): RH-202 gap questions + answer-to-fact loop` — `GAP_QUESTIONS_PROMPT`; `services/interview_mode.py` (`get_gap_questions`, `answer_gap_question`); `POST /facts/gap-questions` + `POST /facts/answer`; `AnswerGapRequest` schema; refiner Pass 1 augmented with fact keywords; `conftest.py` `isolated_db` extended; 22 new tests (18 service + 4 integration); 625 backend passing. ✅
- **RH-204** `feat(facts): RH-204 facts library page` — `/facts` page with extract modal, inline edit, tag/context filter, duplicate annotations; `lib/api/facts.ts` client; fr.json facts section; 201 frontend passing. ✅
- **RH-208** `feat(export): RH-208 .docx export endpoint` — `services/docx_export.py` (python-docx, ATS-safe structural fidelity); `GET /resumes/{id}/export/docx`; 585/585 backend passing. ✅

## Shipped (P2 wave 1 — 2026-07-09)
- **RH-209** `fix(tests): RH-209 green suite + stale column comment` (491f325) — localStorage mock in vitest.setup.ts; 11 pre-existing frontend failures fixed (194/194 passing); "seven"→"eight" comments in kanban-board.tsx. ✅
- **RH-203** `feat(facts): RH-203 dedup on confirm and annotation on extract` (b40c5cd) — difflib.SequenceMatcher dedup on `POST /facts/confirm` (threshold 0.9); `duplicate_of` annotation on `/extract` candidates; DuplicateFactResponse schema; 15 service tests. ✅
- **RH-207** `feat(template): RH-207 Murphy resume template` (20eb85b) — ResumeMurphy component + murphy.module.css; full-bleed black header, gray competency band, small-caps section headers; registered in TemplateType/TEMPLATE_OPTIONS/print route; 7 render tests + registration test; 201/201 frontend passing. ✅
- **RH-201** `feat(improver): RH-201 blocks + fact provenance in tailoring pipeline` (d2e32a5) — `_wrap_legacy_to_blocks()` auto-wraps legacy description→bullet_blocks for prompt context; `_format_facts_for_prompt()` injects verified facts into diff prompt; DIFF_IMPROVE_PROMPT adds {facts_section} + fact_ids requirement; generate_resume_diffs extracts fact_ids from LLM output; improve preview response now includes provenance + unverified; 585/585 backend passing (+11 new service tests). ✅

## Session log
- 2026-07-09 — Program lead: scaffolding created (this file, BACKLOG, SPEC, ADRs 001–003, .claude/agents/), P1 tickets cut.
- 2026-07-09 — Eng lead (wave 1): dispatched RH-101/103/105/106 in parallel. All 4 agents passed; reviewer approved RH-103; integrated to main. Suite: 546 passed (+102 new).
- 2026-07-09 — Eng lead (wave 2): dispatched RH-102/104/107 in parallel. All 3 agents passed; integrated to main (manual patch for wave-1/wave-2 worktree overlap on backend, lint fix for pre-existing ats-score-card.tsx + fr.json parity). Suite: 567 backend (+21 new), 183 frontend passed (+5 new; 11 pre-existing failures in resume-wizard-page/viewer unchanged). **P1 complete.**
- 2026-07-09 — Program lead: P1 reviewed and ACCEPTED (docs/reviews/P1-review.md). Key findings: tailoring pipeline still provenance-blind (F1 → RH-201/202); extraction lacks dedup (F2 → RH-203); no frontend surface for facts/variants (F3 → RH-204/205); pre-existing frontend failures (F4 → RH-209). P2 tickets RH-201…210 cut. One DECISION pending in RH-208 (docx dependency) — eng lead proposes, program lead approves.
- 2026-07-09 — Eng lead (P2 wave 1): dispatched RH-201/203/207/209 in parallel (RH-209 committed directly; RH-203/207/201 cherry-picked from worktrees). Suite: 585 backend (+18 new), 201 frontend (+7 new). **P2 wave 1 complete.** RH-208 decision awaiting program lead approval (see DECISION NEEDED above). Wave 2 ready to dispatch: RH-202, RH-204; RH-208 pending decision.
- 2026-07-09 — Program lead: RH-208 **Option A (python-docx) APPROVED** → ADR-004, with scope clarification (ATS-safe structure over pixel fidelity; Murphy PDF remains the pixel-faithful artifact). BACKLOG RH-208 updated accordingly. Wave 2 (RH-202, RH-204, RH-208) cleared for dispatch.
- 2026-07-09 — Eng lead (P2 wave 2): manual integration of RH-202/204/208 from worktrees (pre-P1 base → copy new files + surgical patch). RH-202 adds interview mode (gap Q&A → fact persistence); RH-204 adds facts library page; RH-208 adds docx export. Suite: 625 backend (+40 new), 201 frontend. **P2 wave 2 complete.** Wave 3 ready: RH-205, RH-206, RH-210.
- 2026-07-10 — Eng lead (P2 wave 3): dispatched RH-205/RH-210 in parallel (worktrees), then RH-206 after RH-205 landed. Manual merge needed for locale files (stash+cherry-pick collision). Suite: 630 backend, 230 frontend (+29 new). **P2 wave 3 complete. P2 complete.**
