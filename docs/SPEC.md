# Resume Hulk — Product Spec (condensed)

> Source of truth for *what* we're building on top of the Resume-Matcher fork. Maintained by the program lead (Cowork). Architecture decisions: [decisions/](decisions/).

## Vision
A local, single-user app that manages a structured resume repository and tailors resumes to specific roles **without hallucination**, tracks applications at volume, and turns that corpus into career intelligence.

## Three-layer content model
1. **Fact base** — verified career facts w/ metrics; the only permissible source for generated claims (ADR-001).
2. **Block variants** — every resume block holds multiple variants tagged by audience (ic / manager / executive / sales-engineer), domain, seniority; each variant cites `fact_ids` (ADR-002).
3. **Documents** — a resume is a selection of active variants + a template; per-block editing; every sent resume snapshotted (existing `parent_id` lineage + tracker link).

## Differentiating features (build order)
### P1 — Repository upgrade (current)
Facts table + extraction from master resume (human-confirmed), block variants + tags, provenance links, interest signals on applications, "considering" quick-capture (ADR-003).

### P2 — Tailor-loop hardening
**Interview mode:** when tailoring finds a JD requirement with no supporting fact, it asks structured questions instead of inventing; answers persist as new facts (`confidence=user_answered`). Provenance badges in the editor; per-block diff accept/reject (partially exists via refiner); ATS gaps clickable → interview mode. Custom "Tim" template reproducing his resume design; .docx export. **Dedup import:** old resumes imported by clustering near-duplicate bullets into existing facts/variants for human review.

### P3 — Career intelligence (integrated module; own routes + tables)
- **Interest signals** (shipped in P1 as data capture): dimensions — compensation, role & scope, values/mission, growth, technology, stability/lifestyle, people — each weighted 1–5 + note; config-driven (`config/interest_dimensions.json`).
- **Advice engine** (on demand + every ~5 new applications): cluster JD core responsibilities into role archetypes → cross-reference with interest weights (what attracts) and fact-base coverage (what fits) → LLM synthesis: target archetypes, stretch archetypes w/ gap-closing plans, deprioritize list, market observations. Advice cites only recorded facts + captured JDs.
- **Outcome overlay:** response/interview rates per archetype as tracker data accrues.

### P4 — Job intake expansion
JobSpy integration (Indeed/Glassdoor/Google; LinkedIn excluded), JD library, multi-JD tailoring. Cover-letter module gains "thank-you / follow-up email" prompt profile.

## Invariants (enforce in review)
- **No generated resume content without `fact_ids`.** Unverifiable content is flagged, never silently included.
- Additive storage changes only; TinyDB-era facade semantics preserved.
- All UI follows the repo's Swiss International Style system.
- Deterministic tests for every behavior; no real LLM calls in default suites.

## Out of scope
Multi-user/auth, hosted deployment, LinkedIn scraping, removing the cover-letter feature (kept for thank-you emails).
