"""Service tests for fact_extractor — async functions with mocked LLM and db."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.fact_extractor import confirm_facts, extract_candidate_facts


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_PROCESSED_DATA = {
    "personalInfo": {"name": "Jane Doe", "title": "Engineer"},
    "summary": "Backend engineer with 6 years experience.",
    "workExperience": [
        {
            "id": 1,
            "title": "Senior Engineer",
            "company": "Acme Corp",
            "years": "Jan 2021 - Present",
            "description": [
                "Led a team of 8 engineers delivering a payment system processing $2M/month",
                "Improved API performance by 40%",
            ],
        }
    ],
    "education": [],
    "personalProjects": [],
    "additional": {"technicalSkills": ["Python", "FastAPI"]},
    "customSections": {},
}

SAMPLE_CANDIDATE = {
    "statement": "Led a team of 8 engineers delivering a payment system processing $2M/month",
    "context": "Acme Corp — Senior Engineer",
    "source": "workExperience",
    "metrics_json": {"amount": "2M", "unit": "USD/month"},
    "tags_json": ["leadership", "quantified"],
    "confidence": "candidate",
}


# ---------------------------------------------------------------------------
# TestExtractCandidateFacts
# ---------------------------------------------------------------------------


class TestExtractCandidateFacts:
    """Tests for extract_candidate_facts() with mocked LLM and db."""

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_returns_candidate_list(self, mock_db, mock_llm):
        """Happy path: LLM returns a list, each item gets confidence='candidate'."""
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-123",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_llm.return_value = [SAMPLE_CANDIDATE]

        result = await extract_candidate_facts("resume-123")

        assert len(result) == 1
        assert result[0]["confidence"] == "candidate"
        assert result[0]["statement"] == SAMPLE_CANDIDATE["statement"]
        # Must NOT persist — db.create_fact should not have been called
        mock_db.create_fact.assert_not_called()

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_handles_wrapped_llm_response(self, mock_db, mock_llm):
        """LLM returns {'facts': [...]} instead of a bare list — should unwrap it."""
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-456",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_llm.return_value = {"facts": [SAMPLE_CANDIDATE]}

        result = await extract_candidate_facts("resume-456")

        assert len(result) == 1
        assert result[0]["confidence"] == "candidate"

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_raises_404_for_missing_resume(self, mock_db, mock_llm):
        """db.get_resume returns None → HTTPException 404."""
        from fastapi import HTTPException

        mock_db.get_resume = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await extract_candidate_facts("nonexistent-id")

        assert exc_info.value.status_code == 404
        mock_llm.assert_not_called()

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_raises_404_for_no_processed_data(self, mock_db, mock_llm):
        """Resume exists but processed_data is None/absent → HTTPException 404."""
        from fastapi import HTTPException

        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-789",
                "processed_data": None,
            }
        )

        with pytest.raises(HTTPException) as exc_info:
            await extract_candidate_facts("resume-789")

        assert exc_info.value.status_code == 404
        mock_llm.assert_not_called()

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_normalizes_missing_source(self, mock_db, mock_llm):
        """Item with no source field gets source='resume:<id>'."""
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-abc",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_llm.return_value = [
            {
                "statement": "Built something",
                "context": "Acme",
                # source intentionally omitted
            }
        ]

        result = await extract_candidate_facts("resume-abc")

        assert result[0]["source"] == "resume:resume-abc"

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_skips_non_dict_items(self, mock_db, mock_llm):
        """Non-dict items in the LLM output are skipped silently."""
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-xyz",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_llm.return_value = [
            SAMPLE_CANDIDATE,
            "not a dict",
            42,
            None,
        ]

        result = await extract_candidate_facts("resume-xyz")

        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestConfirmFacts
# ---------------------------------------------------------------------------


class TestConfirmFacts:
    """Tests for confirm_facts() with mocked db."""

    @patch("app.services.fact_extractor.db")
    async def test_persists_with_verified_confidence(self, mock_db):
        """Each candidate is persisted with confidence='verified'."""
        persisted_fact = {
            "fact_id": "fact-001",
            "statement": SAMPLE_CANDIDATE["statement"],
            "context": SAMPLE_CANDIDATE["context"],
            "source": SAMPLE_CANDIDATE["source"],
            "metrics_json": SAMPLE_CANDIDATE["metrics_json"],
            "tags_json": SAMPLE_CANDIDATE["tags_json"],
            "confidence": "verified",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        mock_db.create_fact = AsyncMock(return_value=persisted_fact)

        result = await confirm_facts([SAMPLE_CANDIDATE])

        assert len(result) == 1
        # verify db.create_fact was called with confidence="verified"
        call_kwargs = mock_db.create_fact.call_args.kwargs
        assert call_kwargs["confidence"] == "verified"
        assert call_kwargs["statement"] == SAMPLE_CANDIDATE["statement"]

    @patch("app.services.fact_extractor.db")
    async def test_persists_all_candidates(self, mock_db):
        """Multiple candidates are each persisted as separate facts."""

        async def _make_fact(**kwargs):
            return {
                "fact_id": "fact-x",
                "statement": kwargs["statement"],
                "context": kwargs.get("context", ""),
                "source": kwargs.get("source", ""),
                "metrics_json": kwargs.get("metrics_json", {}),
                "tags_json": kwargs.get("tags_json", []),
                "confidence": kwargs["confidence"],
                "created_at": "",
                "updated_at": "",
            }

        mock_db.create_fact = AsyncMock(side_effect=_make_fact)

        candidates = [
            {**SAMPLE_CANDIDATE, "statement": "Fact A"},
            {**SAMPLE_CANDIDATE, "statement": "Fact B"},
        ]
        result = await confirm_facts(candidates)

        assert len(result) == 2
        assert mock_db.create_fact.call_count == 2
