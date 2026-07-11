# PM Bootstrap — read this first (≈2 min)

> Entry point for any high-capability LLM taking over **program lead** duties (product management) for Resume Hulk. This file + PROJECT_STATE.md (~60 lines) are enough to operate. Everything else is load-on-demand via the map below. Do NOT bulk-read the repo or docs/ tree.

## What this project is (30 seconds)
Resume Hulk: local single-user app (fork of OSS Resume-Matcher; FastAPI + SQLite/SQLAlchemy + Next.js + LiteLLM) that tailors resumes to jobs **without hallucination**. Core mechanic: a verified **fact base**; every LLM-generated resume line must cite `fact_ids` or be flagged unverified. On top: tagged block **variants** (IC/manager/exec/SE phrasings), application **tracker** with interest signals, **career intelligence** (JD clustering → attraction/fit scores → advice), job-board intake, thank-you emails. Owner/tester: Tim (tim@murphy.dev).

## How development works (60 seconds)
Three tiers. **You (program lead, Cowork/Fable):** phase reviews, ticket cutting, ADRs, resolving DECISION NEEDED items, triaging Tim's bug reports. **Eng lead (Claude Code main session, Sonnet):** consumes BACKLOG.md top-down, dispatches to cheap worker subagents, reviews, commits, updates PROJECT_STATE.md. **Workers (Haiku/Sonnet subagents):** one scoped ticket each.

Your operating loop: read PROJECT_STATE.md → review latest shipped work (git log + spot-check code against ticket acceptance criteria — past reviews caught silently-dropped criteria twice) → write review to docs/reviews/ → cut next tickets into BACKLOG.md → update PROJECT_STATE.md.

Non-negotiables you enforce: **bug gate** (open BUGS block all features; fixes need pre-fix-failing regression tests), **reopen protocol** (reopened issue → post-mortem prior fix's tests first), **provenance invariant** (no unverified LLM content rendered silently), **additive-only storage**, decisions recorded as ADRs before implementation.

## Context map — load only what the task needs
| You need to… | Read | Size |
|---|---|---|
| Know current status, standing rules | `docs/PROJECT_STATE.md` | ~60 lines |
| Triage Tim's bug reports | `docs/ISSUES.md` (newest entries at bottom) | grep `status: new` |
| Cut/adjust tickets | `docs/BACKLOG.md` — current phase section only | section ≈ 100 lines |
| Understand product scope/phasing | `docs/SPEC.md` | ~50 lines |
| Check an architecture constraint | `docs/decisions/00N-*.md` (5 ADRs, titles are self-explanatory) | ~20 lines each |
| Understand eng-lead process you're instructing | `docs/ORCHESTRATION.md` | ~45 lines |
| See how past reviews were done (format + rigor) | `docs/reviews/P2-review.md` (best example) | ~40 lines |
| Ticket-level shipping history, old session log | `docs/archive/HISTORY.md` | only when auditing |
| Repo conventions the eng team follows | `.claude/CLAUDE.md` | only if judging code directly |

**Don't load:** `docs/agent/` and `docs/portable/` (upstream's docs — for workers, not you), `docs/superpowers/`, locale files, `docs/claude-agents/` (staging copies of subagent defs), anything under `apps/` unless verifying a specific review claim.

## ADR one-liners (so you know when to open one)
1. **001** Facts = first-class SQLite table. 2. **002** Variants live inside `processed_data` Pydantic (additive, no migration). 3. **003** `considering` applications may have NULL resume_id. 4. **004** docx export = python-docx, ATS-safe structure over pixel fidelity. 5. **005** Career intelligence: deterministic scores in Python, LLM only names clusters + writes cited narrative.

## Known failure patterns (learned, don't relearn)
- Green unit suites ≠ working app: breaks recur at page/endpoint level on real data shapes (legacy rows, NULLs, missing metadata keys). Demand seeded-real-shape smoke coverage (BUG-004/009).
- Workers silently drop acceptance criteria; reviewers approve the diff's own story. Always re-check shipped work against the TICKET, and spot-check 2–3 claims in code yourself.
- Regression tests can pass while the feature stays broken (BUG-003→006): ask WHAT LAYER a test exercises.
- Parallel worktree waves collide on locale files and shared modules; sequencing advice belongs in dispatch notes.
