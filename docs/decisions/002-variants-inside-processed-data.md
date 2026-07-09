# ADR-002: Block variants live inside `processed_data` (Pydantic), not new tables

**Status:** Accepted (program lead, 2026-07-09)

## Context
Every resume block (summary, role description, bullet, skill group) needs multiple tagged variants (ic / manager / executive / sales-engineer, domain, seniority). Options: (a) relational variant tables, (b) extend the existing `ResumeData` Pydantic schema stored in `Resume.processed_data` JSON.

## Decision
Extend `ResumeData` (apps/backend/app/schemas/models.py). Variants are document-shaped — always loaded/saved with their resume, ordered, nested. The existing pipeline (improver, refiner, renderer, frontend editor) already round-trips `processed_data`; new relational tables would force joins into every one of those paths.

Shape (additive, all optional with defaults so existing data validates unchanged):
```python
class BlockVariant(BaseModel):
    id: str
    text: str
    tags: list[str] = []        # e.g. ["executive", "fsi"]
    fact_ids: list[str] = []    # provenance -> facts table (ADR-001)

class BulletBlock(BaseModel):
    id: str
    active_variant_id: str
    variants: list[BlockVariant]
```
`Experience` gains `bullet_blocks: list[BulletBlock] = []`; `ResumeData` gains `summary_blocks: list[BulletBlock] = []`. The legacy `description: list[str]` remains and is derived from active variants when blocks exist (single source of truth: blocks win when non-empty).

## Consequences
No DB migration. Master resume is the variant library; tailored resumes select/override active variants. Renderer changes are limited to reading active variants.
