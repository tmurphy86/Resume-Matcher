"""Integration tests for the facts API (real isolated DB)."""

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
