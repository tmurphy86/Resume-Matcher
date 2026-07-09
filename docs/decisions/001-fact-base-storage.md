# ADR-001: Fact base as a first-class SQLAlchemy table

**Status:** Accepted (program lead, 2026-07-09)

## Context
Resume Hulk's anti-hallucination guarantee requires a verified "fact base": career facts every generated bullet must trace to. Options: (a) JSON blob on the master Resume row, (b) new `facts` table.

## Decision
New `facts` table in `models.py`. Facts are queried independently of any resume (gap analysis, interview mode, career intelligence all read them), get referenced by ID from many places, and accumulate over time — relational, not document-shaped.

Schema: `fact_id (pk)`, `statement` (text, the verified claim), `context` (employer/role it belongs to), `source` (resume_id + section, or "interview"), `metrics_json` (structured numbers, e.g. `{"amount": "12.5M", "unit": "USD/yr"}`), `tags_json` (list), `confidence` ("verified" | "user_answered"), `created_at`, `updated_at`.

## Consequences
Additive migration only (new table; existing tables untouched — consistent with repo rule "additive changes only"). Facade pattern in `database.py` gets a facts accessor.
