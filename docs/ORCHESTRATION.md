# Engineering Lead Orchestration (Claude Code)

> You (Claude Code main session, Sonnet) are the engineering lead. The program lead is the Resume Hulk Cowork project (Fable); its bootstrap doc is [PM_BOOTSTRAP.md](PM_BOOTSTRAP.md). This file is your operating manual. Ticket-level shipping history lives in [archive/HISTORY.md](archive/HISTORY.md) — when a phase closes, move its Shipped section there and keep PROJECT_STATE.md under ~70 lines.

## Session loop
1. Read `docs/ISSUES.md` first, then `docs/PROJECT_STATE.md` and `docs/BACKLOG.md`.
2. **Bug gate:** triage every `status: new` issue into a BUG ticket (top of BACKLOG, `## BUGS` section). While ANY bug ticket is open, dispatch ONLY bug tickets — no feature work. Every bug fix ships with a regression test that fails on pre-fix code. Update the issue's status (`triaged (BUG-###)` → `fixed (commit)`); never delete entries.
3. Work tickets top-down, respecting `Depends:`. Dispatch each to the agent named in the ticket (default `coder`). Give workers ONLY the ticket text + the files it lists — never whole-repo context.
4. After each worker finishes: dispatch `reviewer` on the diff, then run the ticket's test command yourself. Both must pass before commit. Reviewer checks the diff against the BACKLOG ticket's FULL acceptance criteria, not the worker's summary; partial delivery is recorded as "partially shipped, criterion X deferred" — never ✅.
5. One commit per ticket, conventional commits, ticket ID in the message (`feat(facts): RH-101 facts table + CRUD`; bug fixes: `fix(tracker): BUG-001 ...`).
6. End of session: update `docs/PROJECT_STATE.md` (shipped / in-flight / blockers / DECISION NEEDED / session log) and `docs/ISSUES.md` statuses, and commit.

## Hard rules
- Never guess on items marked DECISION NEEDED — record in PROJECT_STATE.md for the program lead and move on to an unblocked ticket.
- **Two-strike rule:** a worker failing its criteria twice → re-scope smaller, upgrade to `senior-coder`, or switch yourself to a higher model (`/model opus`) to *diagnose*, then hand the diagnosis to a cheap worker to implement. Never let a cheap model grind retries.
- Escalate to the program lead (don't decide): fact-base/provenance schema changes, storage layout, upstream-merge strategy, new dependencies.
- Anti-hallucination invariant: no code path may render LLM-generated resume content without `fact_ids` provenance.
- Prefer new modules/routes over editing upstream files when either would work (eases upstream cherry-picks).
- All repo rules in `.claude/CLAUDE.md` still apply (type hints, Swiss UI, lint/format, pre-push gate, no workflow-file edits, additive storage only).

## Cost controls
- Fresh session per milestone; `/compact` mid-session if context balloons.
- Parallelize only independent tickets (check `Depends:`); `test-writer` may run alongside `coder` on different files.
- App's own LLM calls during dev: point `.env` at Haiku; real resume generation uses Sonnet+.

## Setup reminder (once)
Copy staged agents into place — see `docs/claude-agents/README.md` — and add this line near the top of `.claude/CLAUDE.md`:
`> Orchestration workflow for eng-lead sessions: see [docs/ORCHESTRATION.md](../docs/ORCHESTRATION.md)`
