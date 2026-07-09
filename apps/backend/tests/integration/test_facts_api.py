"""Integration tests for the facts API (real isolated DB)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestListFacts:
    async def test_empty_list_returns_empty_array(self, isolated_db):
        async with _client() as client:
            resp = await client.get("/api/v1/facts")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_facts(self, isolated_db):
        await isolated_db.create_fact(statement="Test fact 1", confidence="verified")
        await isolated_db.create_fact(
            statement="Test fact 2", confidence="user_answered", tags_json=["tag1"]
        )
        async with _client() as client:
            resp = await client.get("/api/v1/facts")
        assert resp.status_code == 200
        facts = resp.json()
        assert len(facts) == 2
        assert facts[0]["statement"] == "Test fact 1"
        assert facts[1]["statement"] == "Test fact 2"

    async def test_list_facts_filtered_by_tag(self, isolated_db):
        await isolated_db.create_fact(statement="Tagged fact", tags_json=["tag1", "tag2"])
        await isolated_db.create_fact(statement="Other fact", tags_json=["tag3"])
        async with _client() as client:
            resp = await client.get("/api/v1/facts?tag=tag1")
        assert resp.status_code == 200
        facts = resp.json()
        assert len(facts) == 1
        assert facts[0]["statement"] == "Tagged fact"

    async def test_list_facts_filtered_by_context(self, isolated_db):
        await isolated_db.create_fact(statement="Fact 1", context="Employer A")
        await isolated_db.create_fact(statement="Fact 2", context="Employer B")
        async with _client() as client:
            resp = await client.get("/api/v1/facts?context=Employer%20A")
        assert resp.status_code == 200
        facts = resp.json()
        assert len(facts) == 1
        assert facts[0]["statement"] == "Fact 1"

    async def test_list_facts_filtered_by_tag_and_context(self, isolated_db):
        await isolated_db.create_fact(
            statement="Fact 1", context="Employer A", tags_json=["tag1"]
        )
        await isolated_db.create_fact(
            statement="Fact 2", context="Employer A", tags_json=["tag2"]
        )
        await isolated_db.create_fact(
            statement="Fact 3", context="Employer B", tags_json=["tag1"]
        )
        async with _client() as client:
            resp = await client.get("/api/v1/facts?context=Employer%20A&tag=tag1")
        assert resp.status_code == 200
        facts = resp.json()
        assert len(facts) == 1
        assert facts[0]["statement"] == "Fact 1"


class TestCreateFact:
    async def test_create_fact(self, isolated_db):
        async with _client() as client:
            resp = await client.post(
                "/api/v1/facts",
                json={
                    "statement": "New fact",
                    "context": "Test context",
                    "confidence": "verified",
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["statement"] == "New fact"
        assert body["context"] == "Test context"
        assert body["confidence"] == "verified"
        assert "fact_id" in body
        assert "created_at" in body
        assert "updated_at" in body

    async def test_create_fact_with_metrics_and_tags(self, isolated_db):
        async with _client() as client:
            resp = await client.post(
                "/api/v1/facts",
                json={
                    "statement": "Fact with metrics",
                    "metrics_json": {"amount": "12.5M", "unit": "USD/yr"},
                    "tags_json": ["salary", "compensation"],
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["statement"] == "Fact with metrics"
        assert body["metrics_json"] == {"amount": "12.5M", "unit": "USD/yr"}
        assert body["tags_json"] == ["salary", "compensation"]

    async def test_create_fact_missing_statement_returns_422(self, isolated_db):
        async with _client() as client:
            resp = await client.post(
                "/api/v1/facts",
                json={
                    "context": "Test context",
                },
            )
        assert resp.status_code == 422


class TestUpdateFact:
    async def test_update_fact(self, isolated_db):
        fact = await isolated_db.create_fact(
            statement="Original fact", confidence="verified"
        )
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/facts/{fact['fact_id']}",
                json={"statement": "Updated fact", "confidence": "user_answered"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["statement"] == "Updated fact"
        assert body["confidence"] == "user_answered"

    async def test_update_fact_partial(self, isolated_db):
        fact = await isolated_db.create_fact(
            statement="Original", context="Context A", confidence="verified"
        )
        async with _client() as client:
            resp = await client.patch(
                f"/api/v1/facts/{fact['fact_id']}",
                json={"statement": "Updated"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["statement"] == "Updated"
        assert body["context"] == "Context A"  # unchanged

    async def test_update_nonexistent_fact_returns_404(self, isolated_db):
        async with _client() as client:
            resp = await client.patch(
                "/api/v1/facts/nonexistent",
                json={"statement": "Updated"},
            )
        assert resp.status_code == 404


class TestDeleteFact:
    async def test_delete_fact(self, isolated_db):
        fact = await isolated_db.create_fact(statement="Fact to delete")
        async with _client() as client:
            resp = await client.delete(f"/api/v1/facts/{fact['fact_id']}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "Fact deleted"
        assert body["affected"] == 1

        # Verify it's gone
        retrieved = await isolated_db.get_fact(fact["fact_id"])
        assert retrieved is None

    async def test_delete_nonexistent_fact_returns_404(self, isolated_db):
        async with _client() as client:
            resp = await client.delete("/api/v1/facts/nonexistent")
        assert resp.status_code == 404


class TestGetFactResponseSchema:
    async def test_fact_response_includes_all_fields(self, isolated_db):
        fact = await isolated_db.create_fact(
            statement="Complete fact",
            context="Context",
            source="resume_id:abc/experience",
            metrics_json={"value": 100},
            tags_json=["tag1"],
            confidence="user_answered",
        )
        async with _client() as client:
            resp = await client.get("/api/v1/facts")
        assert resp.status_code == 200
        facts = resp.json()
        assert len(facts) == 1
        body = facts[0]
        assert body["fact_id"] == fact["fact_id"]
        assert body["statement"] == "Complete fact"
        assert body["context"] == "Context"
        assert body["source"] == "resume_id:abc/experience"
        assert body["metrics_json"] == {"value": 100}
        assert body["tags_json"] == ["tag1"]
        assert body["confidence"] == "user_answered"
        assert "created_at" in body
        assert "updated_at" in body


# ---------------------------------------------------------------------------
# RH-202: Gap questions + answer flow (integration with real DB, mocked LLM)
# ---------------------------------------------------------------------------

_PROCESSED_DATA = {
    "personalInfo": {"name": "Jane Doe"},
    "summary": "Backend engineer.",
    "workExperience": [
        {
            "title": "Engineer",
            "company": "Acme",
            "description": ["Built REST APIs using FastAPI"],
        }
    ],
    "education": [],
    "personalProjects": [],
    "additional": {"technicalSkills": ["Python", "FastAPI"]},
    "customSections": {},
}

_LLM_QUESTIONS_RESPONSE = {
    "questions": [
        {
            "question": "Describe a project where you used Kubernetes.",
            "gap_type": "skill",
            "jd_keyword": "Kubernetes",
        }
    ]
}


class TestGapQuestionsAndAnswerFlow:
    @patch("app.services.interview_mode.extract_job_keywords", new_callable=AsyncMock)
    @patch("app.services.interview_mode.complete_json", new_callable=AsyncMock)
    async def test_gap_questions_returns_200(
        self, mock_llm: AsyncMock, mock_kw: AsyncMock, isolated_db
    ) -> None:
        """POST /facts/gap-questions returns 200 with a list of question dicts."""
        mock_kw.return_value = {
            "required_skills": ["Kubernetes"],
            "preferred_skills": [],
            "key_responsibilities": [],
        }
        mock_llm.return_value = _LLM_QUESTIONS_RESPONSE

        # Create job and resume in the isolated DB
        job = await isolated_db.create_job(content="Need Kubernetes and FastAPI skills.")
        resume = await isolated_db.create_resume(
            filename="test.pdf",
            content="Backend engineer.",
            processed_data=_PROCESSED_DATA,
            is_master=True,
        )

        async with _client() as client:
            resp = await client.post(
                "/api/v1/facts/gap-questions",
                params={"job_id": job["job_id"], "resume_id": resume["resume_id"]},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["question"] == _LLM_QUESTIONS_RESPONSE["questions"][0]["question"]
        assert body[0]["gap_type"] == "skill"
        assert body[0]["jd_keyword"] == "Kubernetes"

    @patch("app.services.interview_mode.extract_job_keywords", new_callable=AsyncMock)
    @patch("app.services.interview_mode.complete_json", new_callable=AsyncMock)
    async def test_answer_persists_fact_and_returns_201(
        self, mock_llm: AsyncMock, mock_kw: AsyncMock, isolated_db
    ) -> None:
        """POST /facts/answer returns 201, persists fact with correct confidence."""
        mock_kw.return_value = {
            "required_skills": ["Kubernetes"],
            "preferred_skills": [],
            "key_responsibilities": [],
        }
        mock_llm.return_value = {"questions": []}  # gap refresh returns empty

        job = await isolated_db.create_job(content="Need Kubernetes skills.")
        resume = await isolated_db.create_resume(
            filename="test.pdf",
            content="Resume text.",
            processed_data=_PROCESSED_DATA,
            is_master=True,
        )

        async with _client() as client:
            resp = await client.post(
                "/api/v1/facts/answer",
                json={
                    "question": "Describe your Kubernetes experience.",
                    "answer": "Managed 3 Kubernetes clusters in production for 2 years.",
                    "job_id": job["job_id"],
                    "resume_id": resume["resume_id"],
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert "fact" in body
        assert "gap_questions" in body

        fact = body["fact"]
        assert fact["confidence"] == "user_answered"
        assert fact["source"] == "interview"
        assert fact["context"] == job["job_id"]
        assert "interview" in fact["tags_json"]
        assert "user_answered" in fact["tags_json"]

        # Verify fact was actually persisted in the DB
        all_facts = await isolated_db.list_facts()
        assert any(f["fact_id"] == fact["fact_id"] for f in all_facts)

    async def test_gap_questions_job_not_found_returns_404(self, isolated_db) -> None:
        """POST /facts/gap-questions with unknown job_id → 404."""
        resume = await isolated_db.create_resume(
            filename="test.pdf",
            content="Resume.",
            processed_data=_PROCESSED_DATA,
            is_master=True,
        )
        async with _client() as client:
            resp = await client.post(
                "/api/v1/facts/gap-questions",
                params={"job_id": "nonexistent-job", "resume_id": resume["resume_id"]},
            )
        assert resp.status_code == 404

    async def test_gap_questions_resume_not_found_returns_404(self, isolated_db) -> None:
        """POST /facts/gap-questions with unknown resume_id → 404."""
        job = await isolated_db.create_job(content="Need skills.")
        async with _client() as client:
            resp = await client.post(
                "/api/v1/facts/gap-questions",
                params={"job_id": job["job_id"], "resume_id": "nonexistent-resume"},
            )
        assert resp.status_code == 404
