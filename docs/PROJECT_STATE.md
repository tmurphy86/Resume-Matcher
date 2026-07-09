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
_(nothing yet — P1 not started)_

## In flight
_(none)_

## Blockers
_(none)_

## DECISION NEEDED
_(none — ADRs 001–003 pre-resolve the P1 questions; see docs/decisions/)_

## Session log
- 2026-07-09 — Program lead: scaffolding created (this file, BACKLOG, SPEC, ADRs 001–003, .claude/agents/), P1 tickets cut.
