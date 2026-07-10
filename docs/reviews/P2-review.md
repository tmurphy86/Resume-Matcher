# P2 Program Review (2026-07-10, program lead)

**Verdict: ACCEPTED WITH CONDITIONS.** All ten tickets merged, suites green (630 backend / 230 frontend), scope discipline clean (no touches to `.github/`, hooks, Docker). Two acceptance criteria were quietly dropped and carry into P3 as mandatory tickets.

## Verified
- **RH-201/202 (critical path)** — improver injects verified facts into the diff prompt and extracts `fact_ids` from output; unverified changes are segregated, surfaced in the response, and badged amber in the diff modal (never silently included). Interview mode persists answers with `confidence=user_answered`, `source=interview`; refiner honors new facts. The anti-hallucination loop is closed end-to-end.
- **RH-208** — ADR-004 conformant: real Word heading styles and `List Bullet` paragraphs, no manual "•" strings, no text boxes. 18 structural tests.
- **RH-203/210 backend** — dedup thresholds implemented exactly as specced (dup ≥0.9; variant band 0.5–0.9), stdlib-only.
- **RH-204/205/206 UI** — facts library w/ extraction review, provenance panel w/ covered/uncovered/broken, ATS gap chips → interview panel. All 6 locales, 29 new frontend tests in wave 3.

## Findings
1. **F1 — RH-205 shipped half its ticket.** The commit even renamed itself ("provenance badges and unverified-change warnings"): the **variant editor** (criterion 1: per-block variant display w/ tags, active-variant switching) does not exist — zero frontend code references `variants`/`active_variant`. Consequence: the variant layer is machine-writable but human-invisible; nobody can browse, switch, tag, or author variants. → **RH-301 (P3, mandatory carryover)**.
2. **F2 — RH-210 shipped 2 of 3 criteria.** `variant_of` candidates are grouped and color-coded in the import modal, but nothing persists chosen phrasings onto master-resume `bullet_blocks` — the variant library never actually grows from old resumes, which was the point. → **RH-302 (P3, mandatory carryover)**.
3. **F3 — process observation for the eng lead:** in both cases the reviewer approved diffs that met their *commit description* but not their *full ticket*. Reviewer instruction updated implicitly: check the diff against the BACKLOG ticket's acceptance criteria, not the worker's summary. Partial delivery is fine when reported — it must land in PROJECT_STATE as "partially shipped, criterion X deferred," never as ✅.
4. **F4 — observation:** wave-integration friction (worktree collisions, manual locale merges) recurred in every wave. Acceptable cost at this scale; if it grows, serialize locale-touching tickets instead of parallelizing them.

## Verification limits
Same as P1: sandbox can't execute the suites (Python 3.13 / darwin node_modules); verified by code inspection + eng-lead runs + pre-push gate.
