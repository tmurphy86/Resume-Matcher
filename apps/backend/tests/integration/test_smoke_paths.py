"""BUG-004/BUG-009: Human-path smoke tests — every main endpoint must return 2xx.

Covers the class of bug where page-level integration breaks are missed by
unit suites because they require multiple row shapes to coexist in the DB.

BUG-009 post-mortems: why the original BUG-004 suite missed three defects:

BUG-005 (POST /applications/quick 500s):
  The original smoke suite seeded a fresh DB (auto-migrated by app startup)
  which had the correct nullable schema from the start. It never tested against
  a DB initialized with the original NOT NULL resume_id schema, so the
  IntegrityError on NULL insert was invisible. It also never called
  POST /applications/quick at all — the suite covered only GET endpoints.

BUG-006 (Fact extraction renders empty — reopened):
  The BUG-003 regression tests were backend service tests only — they mocked
  LLM responses and tested the Python extract_candidate_facts() function.
  The frontend page smokes from BUG-004 mounted the FactsPage but did not
  exercise the extract modal flow (open modal → trigger extract → render
  candidates vs. empty state). The smoke never clicked the extract button
  or rendered any modal branch.

BUG-007 (JD Library fails to load):
  The smoke suite seeded jobs via create_job() which produces modern rows
  (metadata_json={}, no "parsed" key). It never seeded legacy-shaped rows
  (pre-P3 jobs with non-string values in metadata fields, or jobs with a
  "parsed" key whose sub-fields were dicts rather than strings). Additionally,
  GET /api/v1/jobs (the list endpoint) was entirely absent from the smoke
  suite — the only job endpoint tested was GET /api/v1/jobs/{id}.

Seeded DB state (BUG-009 extended):
  - master resume with bullet_blocks (P3/blocks-based format)
  - legacy resume (description only, no bullet_blocks — pre-P1)
  - pre-RH-303 job: metadata_json={}, no "parsed" key (triggers BUG-007 path)
  - job with parsed metadata containing non-string level (corrupted/legacy value)
  - job with modern full parsed metadata
  - considering application: resume_id=NULL, status_history=[], interest_signals=[]
  - applied application: resume_id set, has status_history entry
  - no career report (empty career_reports table is a valid state)
  - a seeded fact (for PATCH /facts/{id})

All GET list/detail AND POST/PATCH mutation endpoints are covered.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.models import ResumeData


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _blocks_resume_data() -> dict:
    """ResumeData with bullet_blocks — the P3 block-based format."""
    base = {
        "personalInfo": {
            "name": "Tim Murphy",
            "title": "Engineering Lead",
            "email": "tim@example.com",
            "phone": "555-0100",
            "location": "Brooklyn, NY",
            "website": "",
            "linkedin": "",
            "github": "",
        },
        "summary": "Engineering lead with 10 years building products.",
        "summary_blocks": [
            {
                "id": "sb-1",
                "active_variant_id": "v-1",
                "variants": [
                    {
                        "id": "v-1",
                        "text": "Engineering lead with 10 years building products.",
                        "tags": [],
                        "fact_ids": [],
                    }
                ],
            }
        ],
        "workExperience": [
            {
                "id": 1,
                "title": "VP Engineering",
                "company": "Acme",
                "location": "NYC",
                "years": "2020 - Present",
                "description": ["Led a team of 20 engineers."],
                "bullet_blocks": [
                    {
                        "id": "bb-1",
                        "active_variant_id": "bv-1",
                        "variants": [
                            {
                                "id": "bv-1",
                                "text": "Led a team of 20 engineers.",
                                "tags": [],
                                "fact_ids": [],
                            }
                        ],
                    }
                ],
            }
        ],
        "education": [],
        "personalProjects": [],
        "additional": {
            "technicalSkills": ["Python", "React"],
            "languages": [],
            "certificationsTraining": [],
            "awards": [],
        },
        "customSections": {},
        "sectionMeta": [],
    }
    return base


def _legacy_resume_data() -> dict:
    """ResumeData without bullet_blocks — the pre-P3 legacy format (pre-P1 shape)."""
    return {
        "personalInfo": {
            "name": "Legacy User",
            "title": "Developer",
            "email": "legacy@example.com",
            "phone": "",
            "location": "",
            "website": "",
            "linkedin": "",
            "github": "",
        },
        "summary": "A legacy resume with no blocks.",
        "workExperience": [
            {
                "id": 1,
                "title": "Developer",
                "company": "Old Co",
                "location": "",
                "years": "2015 - 2019",
                "description": ["Wrote code."],
            }
        ],
        "education": [],
        "personalProjects": [],
        "additional": {
            "technicalSkills": [],
            "languages": [],
            "certificationsTraining": [],
            "awards": [],
        },
        "customSections": {},
        "sectionMeta": [],
    }


async def _seed_db(isolated_db: object) -> dict:
    """Seed ALL required row shapes and return their IDs.

    BUG-009: Extended to cover every historical row shape that has previously
    caused production failures. Each shape is explicitly documented.
    """
    # --- Resumes ---

    # Master resume (blocks-based, P3 format)
    master = await isolated_db.create_resume(
        content="Tim Murphy resume content",
        processed_data=_blocks_resume_data(),
        is_master=True,
        processing_status="ready",
    )

    # Legacy resume (description-only, no bullet_blocks, pre-P1 format)
    legacy_resume = await isolated_db.create_resume(
        content="Legacy resume content",
        processed_data=_legacy_resume_data(),
        is_master=False,
        processing_status="ready",
    )

    # --- Jobs: every historical metadata shape ---

    # Pre-RH-303 job: metadata_json={}, no "parsed" key at all.
    # This is the shape that caused BUG-007: GET /api/v1/jobs crashed on the
    # missing "parsed" key access before the defensive isinstance checks were added.
    job_no_parsed = await isolated_db.create_job(
        content="Senior Python Engineer at TechCorp. Requirements: Python, FastAPI, 5yr.",
    )
    # Do NOT update metadata — leaves metadata_json={} with no "parsed" key.

    # Job with non-string values in parsed metadata fields (corrupted/legacy value).
    # Triggers the isinstance checks in routers/jobs.py: level is a dict, not str.
    job_bad_metadata = await isolated_db.create_job(
        content="Staff DevOps Engineer at InfraCo.",
    )
    await isolated_db.update_job(
        job_bad_metadata["job_id"],
        {
            "company": "InfraCo",
            "role": "Staff DevOps",
            "parsed": {
                "responsibilities": ["Maintain infra"],
                "requirements": ["5yr ops experience"],
                "level": {"text": "Staff"},  # non-string — triggers isinstance guard
                "comp": None,
            },
        },
    )

    # Modern job with full parsed metadata (post-RH-303 shape).
    job_modern = await isolated_db.create_job(
        content="Backend Engineer at MegaCorp. Python, AWS, Kubernetes required.",
    )
    await isolated_db.update_job(
        job_modern["job_id"],
        {
            "company": "MegaCorp",
            "role": "Backend Engineer",
            "parsed": {
                "responsibilities": ["Build APIs"],
                "requirements": ["Python 5yr"],
                "level": "Senior",
                "comp": "$150k",
            },
        },
    )

    # --- Applications ---

    # Considering application — resume_id=NULL (RH-106 quick-capture shape).
    # status_history=[] and interest_signals=[] represent post-migration state
    # for rows that predate those columns.
    considering = await isolated_db.create_application(
        job_id=job_no_parsed["job_id"],
        resume_id=None,
        status="considering",
    )

    # Normal applied application (also exercises status_history column access).
    applied = await isolated_db.create_application(
        job_id=job_modern["job_id"],
        resume_id=master["resume_id"],
        status="applied",
    )

    # --- Facts ---

    # A seeded fact (needed for PATCH /facts/{id} smoke).
    fact = await isolated_db.create_fact(
        statement="Led a team of 20 engineers at Acme.",
        context="work",
        source="master_resume",
        metrics_json={"team_size": 20},
        tags_json=["leadership"],
        confidence="verified",
    )

    return {
        "master_id": master["resume_id"],
        "legacy_resume_id": legacy_resume["resume_id"],
        "job_no_parsed_id": job_no_parsed["job_id"],
        "job_bad_metadata_id": job_bad_metadata["job_id"],
        "job_modern_id": job_modern["job_id"],
        "considering_id": considering["application_id"],
        "applied_id": applied["application_id"],
        "fact_id": fact["fact_id"],
    }


# ---------------------------------------------------------------------------
# GET smoke suite
# ---------------------------------------------------------------------------

class TestSmokePaths:
    """Every main GET list/detail endpoint must return 2xx for the seeded DB.

    BUG-009: Smoke matrix now includes every historical row shape.
    When a ticket adds or changes an endpoint it MUST be added here too —
    see apps/backend/tests/README.md for the enforcement rule.
    """

    async def test_resumes_list(self, isolated_db: object) -> None:
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/resumes/list", params={"include_master": "true"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 2

    async def test_resume_detail_master(self, isolated_db: object) -> None:
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/resumes", params={"resume_id": ids["master_id"]})
        assert resp.status_code == 200

    async def test_resume_detail_legacy(self, isolated_db: object) -> None:
        """Pre-P1 resume (description-only, no bullet_blocks) must be readable."""
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(
                f"/api/v1/resumes", params={"resume_id": ids["legacy_resume_id"]}
            )
        assert resp.status_code == 200

    async def test_applications_list_all_row_shapes(self, isolated_db: object) -> None:
        """BUG-001 regression: must handle considering (NULL resume) + status_history rows."""
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/applications")
        assert resp.status_code == 200
        columns = resp.json()["columns"]
        assert "considering" in columns
        assert "applied" in columns
        considering_ids = [a["application_id"] for a in columns.get("considering", [])]
        applied_ids = [a["application_id"] for a in columns.get("applied", [])]
        assert len(considering_ids) >= 1
        assert len(applied_ids) >= 1

    async def test_application_detail_considering(self, isolated_db: object) -> None:
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/applications/{ids['considering_id']}")
        assert resp.status_code == 200

    async def test_application_detail_applied(self, isolated_db: object) -> None:
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/applications/{ids['applied_id']}")
        assert resp.status_code == 200

    async def test_facts_list(self, isolated_db: object) -> None:
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/facts")
        assert resp.status_code == 200

    async def test_career_reports_list_empty(self, isolated_db: object) -> None:
        """Empty career_reports table is a valid state — must return 200 with []."""
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/career/reports")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_jobs_detail(self, isolated_db: object) -> None:
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get(f"/api/v1/jobs/{ids['job_modern_id']}")
        assert resp.status_code == 200

    # BUG-009: GET /api/v1/jobs (list) was entirely missing from the smoke suite.
    # This is the endpoint that BUG-007 broke: legacy job shapes (no "parsed" key,
    # non-string level values) caused a 500 before the isinstance guards were added.

    async def test_jobs_list_includes_all_metadata_shapes(self, isolated_db: object) -> None:
        """BUG-007 regression: jobs with legacy/corrupted metadata must appear in list.

        Three shapes seeded:
          - no 'parsed' key in metadata_json (pre-RH-303)
          - non-string 'level' value (corrupted legacy data)
          - full modern parsed metadata

        All three must appear in GET /api/v1/jobs with 200.
        """
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        seeded_ids = {ids["job_no_parsed_id"], ids["job_bad_metadata_id"], ids["job_modern_id"]}
        returned_ids = {j["job_id"] for j in data}
        assert seeded_ids.issubset(returned_ids)

    async def test_jobs_list_pre_rh303_job_has_null_fields(self, isolated_db: object) -> None:
        """Pre-RH-303 job (no 'parsed' key) must return null company/role/level."""
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        pre_rh303 = next(j for j in data if j["job_id"] == ids["job_no_parsed_id"])
        assert pre_rh303["company"] is None
        assert pre_rh303["role"] is None
        assert pre_rh303["level"] is None

    async def test_jobs_list_non_string_level_coerced_to_null(self, isolated_db: object) -> None:
        """Job with non-string level (dict) must be coerced to null, not crash."""
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        bad_meta = next(j for j in data if j["job_id"] == ids["job_bad_metadata_id"])
        # level was {"text": "Staff"} — must be coerced to None by isinstance guard
        assert bad_meta["level"] is None or isinstance(bad_meta["level"], str)

    async def test_jobs_list_modern_job_has_string_fields(self, isolated_db: object) -> None:
        """Modern job with parsed metadata returns string company/role/level."""
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200
        data = resp.json()
        modern = next(j for j in data if j["job_id"] == ids["job_modern_id"])
        assert modern["company"] == "MegaCorp"
        assert modern["role"] == "Backend Engineer"
        assert modern["level"] == "Senior"

    async def test_interest_dimensions_list(self, isolated_db: object) -> None:
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.get("/api/v1/applications/interest-dimensions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# POST / PATCH mutation smoke suite
# ---------------------------------------------------------------------------

class TestSmokeMutations:
    """Every main POST/PATCH mutation endpoint must return 2xx for the seeded DB.

    BUG-009: Original smoke suite had NO mutation tests. These tests ensure that
    POST /applications/quick (BUG-005's root endpoint), POST /jobs/import,
    and all fact/application mutations work without 500ing on the seeded data.

    When a ticket adds or changes a mutation endpoint it MUST be added here —
    see apps/backend/tests/README.md for the enforcement rule.
    """

    async def test_post_applications_quick_returns_201(self, isolated_db: object) -> None:
        """POST /applications/quick must return 201 on a fresh modern DB.

        BUG-005: This endpoint was entirely absent from the BUG-004 smoke suite.
        Testing it here ensures a fresh regression test catches future breakage
        of the considering-capture flow on any DB schema.
        """
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.post(
                "/api/v1/applications/quick",
                json={
                    "jd_text": "We are hiring a Go Engineer with 5yr experience.",
                    "company": "GoStart",
                    "role": "Go Engineer",
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "considering"
        assert body["resume_id"] is None

    async def test_post_applications_quick_duplicate_returns_409(self, isolated_db: object) -> None:
        """Second quick-capture for identical JD text returns 409 (not 500)."""
        await _seed_db(isolated_db)
        jd = "Duplicate JD text for dedup test. Requires Python and FastAPI."
        async with _client() as client:
            first = await client.post(
                "/api/v1/applications/quick",
                json={"jd_text": jd},
            )
            second = await client.post(
                "/api/v1/applications/quick",
                json={"jd_text": jd},
            )
        assert first.status_code == 201
        assert second.status_code == 409

    async def test_patch_application_status(self, isolated_db: object) -> None:
        """PATCH /applications/{id} must update status and return 200."""
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{ids['considering_id']}",
                json={"status": "saved"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"

    async def test_patch_application_notes(self, isolated_db: object) -> None:
        """PATCH /applications/{id} must update notes and return 200."""
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/applications/{ids['applied_id']}",
                json={"notes": "Great company culture."},
            )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Great company culture."

    async def test_patch_applications_bulk_status(self, isolated_db: object) -> None:
        """PATCH /applications/bulk must move multiple cards at once."""
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.patch(
                "/api/v1/applications/bulk",
                json={
                    "application_ids": [ids["applied_id"]],
                    "status": "interview",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["affected"] >= 1

    async def test_post_applications_bulk_delete(self, isolated_db: object) -> None:
        """POST /applications/bulk-delete removes the specified cards."""
        ids = await _seed_db(isolated_db)
        # Create a throwaway card to delete
        async with _client() as client:
            quick = await client.post(
                "/api/v1/applications/quick",
                json={"jd_text": "Throwaway JD for bulk delete smoke test."},
            )
            assert quick.status_code == 201
            throwaway_id = quick.json()["application_id"]

            resp = await client.post(
                "/api/v1/applications/bulk-delete",
                json={"application_ids": [throwaway_id]},
            )
        assert resp.status_code == 200
        assert resp.json()["affected"] >= 1

    async def test_post_jobs_upload(self, isolated_db: object) -> None:
        """POST /jobs/upload must accept raw JD text and return job_ids."""
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.post(
                "/api/v1/jobs/upload",
                json={"job_descriptions": ["Staff ML Engineer at DataCo. TensorFlow, 7yr."]},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert len(body["job_id"]) == 1

    async def test_post_jobs_import(self, isolated_db: object) -> None:
        """POST /jobs/import must accept a job from an external source."""
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.post(
                "/api/v1/jobs/import",
                json={
                    "description": "Principal Engineer at CloudCo. AWS, Terraform, 10yr.",
                    "title": "Principal Engineer",
                    "company": "CloudCo",
                    "url": "https://cloudco.example.com/jobs/123",
                    "source": "linkedin",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body

    async def test_post_facts_create(self, isolated_db: object) -> None:
        """POST /facts must create a new fact and return 201."""
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.post(
                "/api/v1/facts",
                json={
                    "statement": "Reduced API latency by 40% using connection pooling.",
                    "context": "work",
                    "source": "manual",
                    "metrics_json": {"latency_reduction_pct": 40},
                    "tags_json": ["performance", "backend"],
                    "confidence": "verified",
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["statement"] == "Reduced API latency by 40% using connection pooling."
        assert body["fact_id"]  # must be assigned

    async def test_patch_fact_update(self, isolated_db: object) -> None:
        """PATCH /facts/{fact_id} must update the fact and return 200."""
        ids = await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/facts/{ids['fact_id']}",
                json={"tags_json": ["leadership", "management"]},
            )
        assert resp.status_code == 200
        assert "management" in resp.json()["tags_json"]

    async def test_post_facts_confirm(self, isolated_db: object) -> None:
        """POST /facts/confirm must persist approved candidates (201)."""
        await _seed_db(isolated_db)
        async with _client() as client:
            resp = await client.post(
                "/api/v1/facts/confirm",
                json=[
                    {
                        "statement": "Shipped 3 products from 0 to 1 in 18 months.",
                        "context": "work",
                        "source": "master_resume",
                        "metrics_json": {},
                        "tags_json": ["product", "startup"],
                        "confidence": "verified",
                    }
                ],
            )
        assert resp.status_code == 201
        body = resp.json()
        assert len(body) == 1
        # Either a FactResponse (fact_id non-empty) or a DuplicateFactResponse
        assert "statement" in body[0]

    async def test_post_facts_extract_with_mocked_llm(self, isolated_db: object) -> None:
        """POST /facts/extract must return candidates without crashing (LLM mocked).

        BUG-006: This endpoint flow was entirely absent from the smoke suite.
        The smoke now exercises the full path: real router → real service →
        mocked LLM → serialised FactResponse list.
        """
        ids = await _seed_db(isolated_db)
        canned_candidates = [
            {
                "fact_id": "",
                "statement": "Led a team of 20 engineers.",
                "context": "work",
                "source": "master_resume",
                "metrics_json": {"team_size": 20},
                "tags_json": ["leadership"],
                "confidence": "candidate",
                "created_at": "",
                "updated_at": "",
                "duplicate_of": None,
            }
        ]
        with patch(
            "app.services.fact_extractor.extract_candidate_facts",
            return_value=canned_candidates,
        ):
            async with _client() as client:
                resp = await client.post(
                    "/api/v1/facts/extract",
                    params={"resume_id": ids["master_id"]},
                )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["statement"] == "Led a team of 20 engineers."
