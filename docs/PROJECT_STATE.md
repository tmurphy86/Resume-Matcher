# Resume Hulk — Project State

> Sync file between the program lead (Cowork/Fable) and the Claude Code engineering lead.
> Eng lead: update at END of every session. Program lead: read at START of every planning session.
> **New program lead? Read [PM_BOOTSTRAP.md](PM_BOOTSTRAP.md) FIRST — it tells you what to load and what to skip.**
> Per-ticket shipping detail + full session log: [archive/HISTORY.md](archive/HISTORY.md) (append-only; move entries there when a phase closes).

## Current milestone
**P5 READY** — Bug gate 2 cleared 2026-07-11. BUG-005…009 all fixed. Suite: 822 backend / 322 frontend. P3 and P4 acceptance conditions now met. Feature work may resume.

## Phase status
| Phase | Scope | Status |
|---|---|---|
| P1 | Fact base, variants, provenance, interest signals (RH-101…107) | ACCEPTED ([reviews/P1-review.md](reviews/P1-review.md)) |
| P2 | Provenance-aware tailoring, interview mode, facts UI, Murphy template, docx (RH-201…210) | ACCEPTED W/ CONDITIONS ([reviews/P2-review.md](reviews/P2-review.md)) |
| P3 | Career intelligence + P2 carryovers (RH-301…308) | CONDITIONAL — pending bug gate |
| P4 | Thank-you emails, JD library, JobSpy intake, multi-JD tailoring (RH-401…404) | CONDITIONAL — pending bug gate |
| Bug gate 1 | BUG-001…004 | CLEARED 2026-07-11 |
| Bug gate 2 | BUG-005…009 | CLEARED 2026-07-11 |

## Standing instructions (do not drop)
- **Bug gate:** docs/ISSUES.md is step 1 of every eng-lead session; open bugs block features; every fix ships a pre-fix-failing regression test.
- **Reopen protocol (new, from BUG-006):** a reopened issue requires a post-mortem of the prior fix's regression tests before any new fix.
- **Reviewer:** check diffs against the BACKLOG ticket's FULL acceptance criteria, not the worker's summary; partial delivery is reported as partial, never ✅.
- **Endpoint rule (lands with BUG-009):** any ticket adding/changing an endpoint must add it to the smoke seed matrix.

## In flight
_(none)_

## Blockers
_(none)_

## DECISION NEEDED
_(none)_

## Session log (recent — full log in archive/HISTORY.md)
- 2026-07-11 — Eng lead (bug gate 2): BUG-005…009 cleared in parallel dispatch. BUG-005: SQLite NOT NULL constraint on resume_id rebuilt via 12-step migration. BUG-006: extract modal branches fixed + 6 component tests (post-mortem: prior tests were service-layer only). BUG-007: defensive isinstance checks on JobSummary fields for legacy rows. BUG-008: status_history added to ApplicationResponse schema. BUG-009: smoke suite expanded (26 backend / 322 frontend), mutation endpoint matrix added, schema-parity fixtures, test READMEs with reviewer rule. Suite: 822/322. P3+P4 ACCEPTED.
- 2026-07-11 — Eng lead (P4 wave 2): RH-403/404 shipped after spend-limit re-dispatch + worktree rebase friction. Suite 788/310. **P4 complete.** Self-reported defect: status_history absent from ApplicationResponse.
- 2026-07-11 — Program lead: P4 human testing found 3 new defects + 1 self-report → BUG-005…008 filed (BUG-006 is a REOPEN of BUG-003 with mandatory test post-mortem), BUG-009 smoke-hardening added (why did the smoke suite miss all of these?). Bug gate re-engaged. Docs compressed for low-context PM handover: PM_BOOTSTRAP.md created, history archived, this file slimmed.
