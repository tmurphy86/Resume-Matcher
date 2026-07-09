# P1 Program Review (2026-07-09, program lead)

**Verdict: ACCEPTED.** All seven tickets shipped, ADR-conformant, scope-disciplined.

## Verified
- Commits afa5038…3fa1e83 map 1:1 to RH-101…107; no touches to `.github/`, hooks, Docker, or existing test assertions. The two out-of-ticket touches (ats-score-card.tsx lint, fr.json parity) were justified and reported.
- ADR-001/002/003 implemented exactly: `Fact` table schema matches; variants are additive Pydantic (`model_validator` derives legacy `description` from active variants — blocks win); `resume_id` nullable with app-level 409 dupe guard for considering cards.
- Tests are real (anti-theater sampled): mocked-LLM assertions include `assert_not_called` guards, 404/422/409 paths covered; 70 new test functions across 6 backend files + api-tracker tests.
- Kanban column addition done the right way (derived from `APPLICATION_STATUS_ORDER`, no board surgery).

## Verification limits
Program-lead sandbox cannot execute the suites (no Python 3.13 download; frontend node_modules are darwin binaries). Relying on eng-lead runs (567 backend / 183 frontend passed) + the pre-push gate. **Tim: a green local `uv run pytest` + `npm run test` before pushing confirms.**

## Findings → P2 shape
1. **F1 (critical path): the tailoring pipeline is provenance-blind.** `improver.py` and `refiner.py` contain zero references to `bullet_blocks` / `summary_blocks` / `fact_ids` — tailored output still round-trips legacy `description` lists, bypassing the variant layer entirely. Provenance lint currently reports ~everything uncovered on a fresh tailor. Expected (out of P1 scope), but it means P1's layers are inert until P2 wires them in. → RH-201/202.
2. **F2: fact extraction has no dedup.** Re-running extract→confirm creates duplicate facts. Also blocks old-resume import. → RH-203 (prerequisite for RH-210).
3. **F3: zero frontend surface for facts/variants.** No extraction-review UI, no variant editor, no provenance badges. The backend APIs are unreachable by a human. → RH-204/205.
4. **F4 (hygiene):** 11 pre-existing frontend failures (resume-wizard-page/viewer) predate P1 but now pollute every suite run; stale "seven fixed-width columns" comment in kanban-board.tsx. → RH-209.
5. **F5 (observation):** interest signals are captured but nothing consumes them yet — by design (P3); noted so nobody "optimizes" them away.
