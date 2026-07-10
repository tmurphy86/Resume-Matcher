# ADR-005: Career intelligence — deterministic numbers, LLM narrative

**Status:** Accepted (program lead, 2026-07-10)

## Context
P3 builds the career intelligence module (SPEC §P3): cluster JD responsibilities into role archetypes, cross-reference interest signals (attraction) and fact-base coverage (fit), synthesize trajectory advice. Design questions: where numbers come from, where the LLM is allowed, and storage.

## Decision
**Split computation from narration.**
- **Deterministic in Python:** attraction scores (weighted aggregation of interest signals per archetype), fit scores (fact/keyword coverage per archetype), response-rate overlays. Same inputs → same numbers, unit-testable, no LLM.
- **LLM for language-shaped work only:** (a) clustering JD responsibilities into named archetypes (JSON-schema-constrained output; canned responses in tests), (b) the narrative synthesis of a report — which must cite only fact_ids, jd_ids, and the computed scores it is handed. The LLM never invents a number.

**Storage (additive):**
- `career_reports` table: `report_id` pk, `generated_at`, `jd_ids_json`, `archetypes_json` (clusters w/ member responsibilities), `scores_json` (attraction/fit/outcome per archetype), `advice_md` (narrative), `model_used`.
- `Application.status_history` JSON column (list of `{status, at}`) — appended on every status change; powers outcome overlays. Existing `status` field unchanged.
- JD structured parse lives in `jobs.metadata_json` under `parsed` (`{responsibilities[], requirements[], level?, comp?}`) — consistent with the facade's existing dynamic-key pattern; no new job columns.

## Consequences
No new dependencies (no embedding libraries — clustering is LLM-side; similarity where needed stays stdlib difflib). Reports are reproducible in their numeric parts and auditable in their narrative parts (citations). Old reports are kept, enabling advice drift over time.
