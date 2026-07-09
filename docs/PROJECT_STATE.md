# Resume Hulk — Project State

> Sync file between the Cowork program lead (Fable) and the Claude Code engineering lead.
> Eng lead: update at the END of every session. Program lead: read at the START of every planning session.

## Current milestone
**P1 — Fact base, variants, provenance, interest signals** (tickets RH-101…RH-107 in [BACKLOG.md](BACKLOG.md))

## Baseline (2026-07-09, commit dd9b5c3)
- Fork of srbhr/Resume-Matcher running locally; Tim's resume uploaded; no issues.
- Stack (differs from upstream README): FastAPI + Python 3.13, SQLite via SQLAlchemy 2.0 async, Next.js 16 + React 19, LiteLLM, Playwright PDF.
- Already present: master resume w/ parent lineage (`Resume.is_master`, `parent_id`), tailoring pipeline (`services/improver.py`, `refiner.py`), ATS scoring w/ sub-scores (`services/ats.py`), Kanban application tracker (`routers/applications.py`, `components/tracker/`), cover letter + outreach (`services/cover_letter.py`), interview prep (`services/interview_prep.py`), resume wizard, enrichment, i18n (5 locales), ~444 backend tests + vitest, pre-push hook gate.
- NOT present (Resume Hulk differentiators): fact base, block variants w/ tags, provenance links, anti-hallucination interview mode, interest signals, career intelligence, dedup import of old resumes.

## Shipped
- **RH-101** `feat(facts): RH-101 facts table + CRUD` (afa5038) — `Fact` model, database facade, `schemas/facts.py`, `routers/facts.py` (GET/POST/PATCH/DELETE `/api/v1/facts`), 14 integration tests. ✅
- **RH-103** `feat(schema): RH-103 block variants + tags in ResumeData` (e3cb66b) — `BlockVariant`, `BulletBlock` models; `Experience.bullet_blocks`, `ResumeData.summary_blocks`; active-variant derivation of legacy `description`/`summary`; 17 unit tests. ✅
- **RH-105** `feat(tracker): RH-105 interest signals on applications` (1619bdc) — `interest_signals` JSON column on Application; `InterestSignal`/`InterestDimension` schemas; `resources/interest_dimensions.json` (7 dims); `GET /applications/interest-dimensions`; PATCH dimension validation (422); 11 integration tests. ✅
- **RH-106** `feat(tracker): RH-106 considering quick-capture` (1aa3bd6) — `Application.resume_id` nullable; `considering` status (first in order); `POST /applications/quick` creates Job+Application(considering) in one call; duplicate 409 guard; 7 integration tests. ✅

## In flight
- **RH-102** — blocked on RH-101 ✅ (unblocked; not yet dispatched)
- **RH-104** — blocked on RH-101 ✅ + RH-103 ✅ (unblocked; not yet dispatched)
- **RH-107** — blocked on RH-105 ✅ + RH-106 ✅ (unblocked; not yet dispatched)

## Blockers
_(none)_

## DECISION NEEDED
_(none — ADRs 001–003 pre-resolve the P1 questions; see docs/decisions/)_

## Session log
- 2026-07-09 — Program lead: scaffolding created (this file, BACKLOG, SPEC, ADRs 001–003, .claude/agents/), P1 tickets cut.
- 2026-07-09 — Eng lead: dispatched RH-101/103/105/106 in parallel (4 isolated worktrees). All 4 agents passed tests; reviewer approved RH-103; cherry-picked all into main. Full suite: 546 passed (444 baseline + 102 new). RH-102, RH-104, RH-107 unblocked for next dispatch.
