# ADR-004: .docx export via python-docx

**Status:** Accepted (program lead, 2026-07-09; proposed by eng lead in RH-208)

## Context
RH-208 needs a .docx export path. Options: (A) python-docx — imperative, pure-Python document construction; (B) html→docx via pandoc/mammoth — reuses the HTML render path but requires the pandoc system binary (mammoth is actually docx→html, wrong direction).

## Decision
**Option A — python-docx.** Approved as proposed: deterministic, structurally testable (open the generated file, assert headings/bullets), no system binary, small footprint. The one-time field-mapping cost is acceptable; pandoc as a system dependency is the wrong trade for a single-developer local app and would complicate Docker/CI.

**Scope clarification (program lead):** the .docx target is **ATS-safe structural fidelity, not pixel fidelity**. The pixel-faithful artifact is the Murphy PDF template (RH-207). The .docx should render clean standard constructs — real heading styles, real bullet lists, no text boxes, no floating elements, minimal tables — because its consumers are ATS parsers and recruiters who edit. Do not attempt to reproduce the black header bar or competency band shading beyond simple, parser-friendly approximations.

## Consequences
- New backend dependency `python-docx` (approved; add via `uv add python-docx`).
- Deterministic structural test per ticket; no LLM/network in tests.
- If a styled "pretty docx" is ever wanted, that's a separate future ticket layering styles onto the same mapper — not a rewrite.
