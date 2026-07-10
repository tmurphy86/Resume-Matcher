"""Service tests for fact_extractor — async functions with mocked LLM and db."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.fact_extractor import (
    confirm_facts,
    extract_candidate_facts,
    import_resume_facts,
    persist_variant_to_blocks,
)


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
        mock_db.list_facts = AsyncMock(return_value=[])

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
        mock_db.list_facts = AsyncMock(return_value=[])

        candidates = [
            {**SAMPLE_CANDIDATE, "statement": "Fact A"},
            {**SAMPLE_CANDIDATE, "statement": "Fact B"},
        ]
        result = await confirm_facts(candidates)

        assert len(result) == 2
        assert mock_db.create_fact.call_count == 2


# ---------------------------------------------------------------------------
# TestDedup (new tests for RH-203)
# ---------------------------------------------------------------------------


class TestDedup:
    """Tests for dedup behavior in confirm_facts() and extract_candidate_facts()."""

    @patch("app.services.fact_extractor.db")
    async def test_confirm_detects_exact_duplicate(self, mock_db):
        """Exact duplicate (ratio=1.0): confirm returns DuplicateFactResponse, doesn't persist."""
        existing_fact = {
            "fact_id": "fact-existing-1",
            "statement": "Led a team of 8 engineers delivering a payment system processing $2M/month",
            "context": "Acme Corp — Senior Engineer",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": [],
            "confidence": "verified",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        mock_db.list_facts = AsyncMock(return_value=[existing_fact])
        mock_db.create_fact = AsyncMock()

        # The candidate has the exact same statement as the existing fact
        candidate = {
            "statement": "Led a team of 8 engineers delivering a payment system processing $2M/month",
            "context": "Acme Corp — Senior Engineer",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": [],
            "confidence": "candidate",
        }

        result = await confirm_facts([candidate])

        # Should return a duplicate response
        assert len(result) == 1
        assert result[0]["status"] == "duplicate"
        assert result[0]["existing_fact_id"] == "fact-existing-1"
        assert result[0]["statement"] == candidate["statement"]

        # Should NOT have persisted the fact
        mock_db.create_fact.assert_not_called()

    @patch("app.services.fact_extractor.db")
    async def test_confirm_detects_near_duplicate_above_threshold(self, mock_db):
        """Near-dup at threshold (0.9): confirm returns DuplicateFactResponse, doesn't persist."""
        existing_fact = {
            "fact_id": "fact-existing-2",
            "statement": "Led a team of 8 engineers delivering a payment system processing $2M/month",
            "context": "Acme Corp",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": [],
            "confidence": "verified",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        mock_db.list_facts = AsyncMock(return_value=[existing_fact])
        mock_db.create_fact = AsyncMock()

        # Candidate with very similar statement (should trigger dedup)
        candidate = {
            "statement": "Led a team of 8 engineers delivering a payment system processing $2m/month",  # lowercase 'm'
            "context": "Acme",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": [],
            "confidence": "candidate",
        }

        result = await confirm_facts([candidate])

        assert len(result) == 1
        assert result[0]["status"] == "duplicate"
        assert result[0]["existing_fact_id"] == "fact-existing-2"
        mock_db.create_fact.assert_not_called()

    @patch("app.services.fact_extractor.db")
    async def test_confirm_persists_distinct_fact_below_threshold(self, mock_db):
        """Distinct fact below threshold: confirm persists and returns FactResponse."""
        existing_fact = {
            "fact_id": "fact-existing-3",
            "statement": "Led a team of 8 engineers",
            "context": "Acme",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": [],
            "confidence": "verified",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        mock_db.list_facts = AsyncMock(return_value=[existing_fact])

        new_fact = {
            "fact_id": "fact-new-1",
            "statement": "Improved API performance by 40%",
            "context": "XYZ Corp",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": [],
            "confidence": "verified",
            "created_at": "2026-01-02T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
        }
        mock_db.create_fact = AsyncMock(return_value=new_fact)

        candidate = {
            "statement": "Improved API performance by 40%",
            "context": "XYZ Corp",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": [],
            "confidence": "candidate",
        }

        result = await confirm_facts([candidate])

        # Should persist and return FactResponse
        assert len(result) == 1
        assert result[0]["fact_id"] == "fact-new-1"
        assert result[0]["statement"] == "Improved API performance by 40%"
        assert result[0]["confidence"] == "verified"
        # Should not have status field (that's only in DuplicateFactResponse)
        assert "status" not in result[0]

        # Should have persisted the fact
        mock_db.create_fact.assert_called_once()

    @patch("app.services.fact_extractor.db")
    async def test_confirm_mixed_duplicates_and_new_facts(self, mock_db):
        """Confirm processes mix of duplicates and new facts correctly."""
        existing_fact = {
            "fact_id": "fact-existing-4",
            "statement": "Led a team of 8 engineers",
            "context": "Acme",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": [],
            "confidence": "verified",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        mock_db.list_facts = AsyncMock(return_value=[existing_fact])

        def _create_fact_side_effect(**kwargs):
            return {
                "fact_id": "fact-new-2",
                "statement": kwargs["statement"],
                "context": kwargs.get("context", ""),
                "source": kwargs.get("source", ""),
                "metrics_json": kwargs.get("metrics_json", {}),
                "tags_json": kwargs.get("tags_json", []),
                "confidence": kwargs["confidence"],
                "created_at": "2026-01-02T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
            }

        mock_db.create_fact = AsyncMock(side_effect=_create_fact_side_effect)

        candidates = [
            {
                "statement": "Led a team of 8 engineers",  # Duplicate
                "context": "Acme",
                "source": "workExperience",
                "metrics_json": {},
                "tags_json": [],
                "confidence": "candidate",
            },
            {
                "statement": "Improved API performance by 40%",  # New
                "context": "XYZ Corp",
                "source": "workExperience",
                "metrics_json": {},
                "tags_json": [],
                "confidence": "candidate",
            },
        ]

        result = await confirm_facts(candidates)

        assert len(result) == 2
        # First result should be duplicate
        assert result[0]["status"] == "duplicate"
        assert result[0]["existing_fact_id"] == "fact-existing-4"
        # Second result should be persisted
        assert result[1]["fact_id"] == "fact-new-2"
        assert "status" not in result[1]
        # Should have only persisted the second one
        assert mock_db.create_fact.call_count == 1

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_extract_annotates_duplicate_of_field(self, mock_db, mock_llm):
        """Extract annotates candidates with duplicate_of field."""
        existing_fact = {
            "fact_id": "fact-existing-5",
            "statement": "Led a team of 8 engineers delivering a payment system processing $2M/month",
            "context": "Acme Corp",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": [],
            "confidence": "verified",
        }

        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-dedup-1",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_llm.return_value = [
            {
                "statement": "Led a team of 8 engineers delivering a payment system processing $2M/month",  # Duplicate
                "context": "Acme Corp",
                "source": "workExperience",
            },
            {
                "statement": "Improved API performance by 40%",  # Distinct
                "context": "XYZ Corp",
                "source": "workExperience",
            },
        ]
        mock_db.list_facts = AsyncMock(return_value=[existing_fact])

        result = await extract_candidate_facts("resume-dedup-1")

        assert len(result) == 2

        # First candidate should be annotated as duplicate
        assert result[0]["duplicate_of"] == "fact-existing-5"

        # Second candidate should have duplicate_of=None
        assert result[1]["duplicate_of"] is None

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_extract_annotates_all_as_none_when_no_existing_facts(
        self, mock_db, mock_llm
    ):
        """Extract annotates duplicate_of=None when no existing facts."""
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-dedup-2",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_llm.return_value = [
            {
                "statement": "Led a team of 8 engineers",
                "context": "Acme Corp",
                "source": "workExperience",
            }
        ]
        mock_db.list_facts = AsyncMock(return_value=[])

        result = await extract_candidate_facts("resume-dedup-2")

        assert len(result) == 1
        assert result[0]["duplicate_of"] is None

    @patch("app.services.fact_extractor.db")
    async def test_confirm_later_candidate_dedup_against_earlier_persisted(
        self, mock_db
    ):
        """Later candidates can dedup against facts persisted earlier in the same confirm call."""
        existing_facts = []

        async def _list_facts():
            return existing_facts

        async def _create_fact(**kwargs):
            fact = {
                "fact_id": f"fact-{len(existing_facts)}",
                "statement": kwargs["statement"],
                "context": kwargs.get("context", ""),
                "source": kwargs.get("source", ""),
                "metrics_json": kwargs.get("metrics_json", {}),
                "tags_json": kwargs.get("tags_json", []),
                "confidence": kwargs["confidence"],
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
            existing_facts.append(fact)
            return fact

        mock_db.list_facts = AsyncMock(side_effect=_list_facts)
        mock_db.create_fact = AsyncMock(side_effect=_create_fact)

        candidates = [
            {
                "statement": "Fact A",
                "context": "Context A",
                "source": "source",
                "metrics_json": {},
                "tags_json": [],
                "confidence": "candidate",
            },
            {
                "statement": "Fact A",  # Exact duplicate of first candidate
                "context": "Context A",
                "source": "source",
                "metrics_json": {},
                "tags_json": [],
                "confidence": "candidate",
            },
        ]

        result = await confirm_facts(candidates)

        # First should be persisted
        assert result[0]["fact_id"] == "fact-0"
        assert "status" not in result[0]

        # Second should be flagged as duplicate of the first
        assert result[1]["status"] == "duplicate"
        assert result[1]["existing_fact_id"] == "fact-0"

        # Should have only called create_fact once
        assert mock_db.create_fact.call_count == 1


# ---------------------------------------------------------------------------
# TestImportResumeFacts (RH-210)
# ---------------------------------------------------------------------------

# A minimal fact dict that list_facts would return.
_EXISTING_FACT_BASE: dict = {
    "fact_id": "fact-existing",
    "statement": "",
    "context": "Some Context",
    "source": "workExperience",
    "metrics_json": {},
    "tags_json": [],
    "confidence": "verified",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}


class TestImportResumeFacts:
    """Tests for import_resume_facts() with mocked LLM and db."""

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_new_group(self, mock_db: MagicMock, mock_llm: AsyncMock) -> None:
        """Statement with no similar existing fact → group='new', existing_fact_id=None."""
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "import-resume-1",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_llm.return_value = [
            {
                "statement": "Completely unrelated statement about something else",
                "context": "New Corp",
                "source": "workExperience",
            }
        ]
        # Existing fact is totally different → similarity well below 0.5
        mock_db.list_facts = AsyncMock(
            return_value=[
                {
                    **_EXISTING_FACT_BASE,
                    "statement": "Quantum physics research on superconductors",
                }
            ]
        )

        result = await import_resume_facts("import-resume-1")

        assert len(result) == 1
        assert result[0]["group"] == "new"
        assert result[0]["existing_fact_id"] is None
        assert result[0]["existing_statement"] is None

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_duplicate_group(self, mock_db: MagicMock, mock_llm: AsyncMock) -> None:
        """Statement with similarity >= 0.9 → group='duplicate', existing_fact_id set."""
        statement = "Led a team of 8 engineers delivering a payment system processing $2M/month"
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "import-resume-2",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_llm.return_value = [
            {
                "statement": statement,
                "context": "Acme Corp",
                "source": "workExperience",
            }
        ]
        existing_fact = {**_EXISTING_FACT_BASE, "fact_id": "fact-dup-1", "statement": statement}
        # list_facts is called twice: once inside extract_candidate_facts (for duplicate_of),
        # once inside import_resume_facts (for grouping).
        mock_db.list_facts = AsyncMock(return_value=[existing_fact])

        result = await import_resume_facts("import-resume-2")

        assert len(result) == 1
        assert result[0]["group"] == "duplicate"
        assert result[0]["existing_fact_id"] == "fact-dup-1"
        assert result[0]["existing_statement"] == statement

    @patch("app.services.fact_extractor._compute_similarity")
    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_variant_of_group(
        self, mock_db: MagicMock, mock_llm: AsyncMock, mock_sim: MagicMock
    ) -> None:
        """Similarity in [0.5, 0.9) → group='variant_of', existing_fact_id set."""
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "import-resume-3",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_llm.return_value = [
            {
                "statement": "Managed a squad of engineers on a billing platform",
                "context": "Beta Corp",
                "source": "workExperience",
            }
        ]
        existing_fact = {
            **_EXISTING_FACT_BASE,
            "fact_id": "fact-var-1",
            "statement": "Led a team of engineers on a payments system",
        }
        mock_db.list_facts = AsyncMock(return_value=[existing_fact])
        # Pin similarity to a value firmly in the variant band.
        mock_sim.return_value = 0.7

        result = await import_resume_facts("import-resume-3")

        assert len(result) == 1
        assert result[0]["group"] == "variant_of"
        assert result[0]["existing_fact_id"] == "fact-var-1"
        assert result[0]["existing_statement"] == existing_fact["statement"]

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_resume_not_found(self, mock_db: MagicMock, mock_llm: AsyncMock) -> None:
        """HTTPException(404) when resume doesn't exist."""
        from fastapi import HTTPException

        mock_db.get_resume = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await import_resume_facts("nonexistent-resume")

        assert exc_info.value.status_code == 404
        mock_llm.assert_not_called()

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_no_processed_data(self, mock_db: MagicMock, mock_llm: AsyncMock) -> None:
        """HTTPException(404) when resume has no processed_data."""
        from fastapi import HTTPException

        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-no-data",
                "processed_data": None,
            }
        )

        with pytest.raises(HTTPException) as exc_info:
            await import_resume_facts("resume-no-data")

        assert exc_info.value.status_code == 404
        mock_llm.assert_not_called()


# ---------------------------------------------------------------------------
# TestPersistVariantToBlocks (RH-302)
# ---------------------------------------------------------------------------

# Processed data with a bullet_block that cites fact-001.
_PROCESSED_DATA_WITH_BLOCK: dict = {
    "personalInfo": {"name": "Jane Doe", "title": "Engineer"},
    "summary": "Backend engineer.",
    "summary_blocks": [],
    "workExperience": [
        {
            "id": 1,
            "title": "Senior Engineer",
            "company": "Acme Corp",
            "years": "Jan 2021 - Present",
            "description": ["Led a team"],
            "bullet_blocks": [
                {
                    "id": "block-1",
                    "active_variant_id": "variant-1",
                    "variants": [
                        {
                            "id": "variant-1",
                            "text": "Led a team of engineers",
                            "tags": [],
                            "fact_ids": ["fact-001"],
                        }
                    ],
                }
            ],
        }
    ],
    "education": [],
    "personalProjects": [],
    "additional": {"technicalSkills": []},
    "customSections": {},
}

_MASTER_RESUME: dict = {
    "resume_id": "master-resume-1",
    "is_master": True,
    "processed_data": _PROCESSED_DATA_WITH_BLOCK,
}


class TestPersistVariantToBlocks:
    """Tests for persist_variant_to_blocks() — RH-302."""

    @patch("app.services.fact_extractor.db")
    async def test_variant_appended_to_existing_block(self, mock_db: MagicMock) -> None:
        """Variant is appended to every block that cites the existing_fact_id."""
        import copy

        master = copy.deepcopy(_MASTER_RESUME)
        mock_db.get_master_resume = AsyncMock(return_value=master)
        mock_db.update_resume = AsyncMock(return_value=master)

        result = await persist_variant_to_blocks(
            candidate_statement="Managed a squad of 8 engineers",
            existing_fact_id="fact-001",
        )

        assert result["status"] == "ok"
        assert result["matched_blocks"] is True

        # Verify update_resume was called with the new variant appended.
        call_args = mock_db.update_resume.call_args
        updated_data: dict = call_args.args[1]["processed_data"]
        block = updated_data["workExperience"][0]["bullet_blocks"][0]
        texts = [v["text"] for v in block["variants"]]
        assert "Managed a squad of 8 engineers" in texts
        # Original variant should still be there.
        assert "Led a team of engineers" in texts
        # New variant must cite the fact.
        new_variant = next(v for v in block["variants"] if v["text"] == "Managed a squad of 8 engineers")
        assert "fact-001" in new_variant["fact_ids"]

    @patch("app.services.fact_extractor.db")
    async def test_block_created_when_absent(self, mock_db: MagicMock) -> None:
        """No existing block cites the fact → new BulletBlock appended to summary_blocks."""
        import copy

        master = copy.deepcopy(_MASTER_RESUME)
        mock_db.get_master_resume = AsyncMock(return_value=master)
        mock_db.update_resume = AsyncMock(return_value=master)

        result = await persist_variant_to_blocks(
            candidate_statement="Completely new accomplishment",
            existing_fact_id="fact-999",  # no block cites this
        )

        assert result["status"] == "ok"
        assert result["matched_blocks"] is False

        call_args = mock_db.update_resume.call_args
        updated_data: dict = call_args.args[1]["processed_data"]
        summary_blocks = updated_data["summary_blocks"]
        assert len(summary_blocks) == 1
        new_block = summary_blocks[0]
        assert len(new_block["variants"]) == 1
        new_variant = new_block["variants"][0]
        assert new_variant["text"] == "Completely new accomplishment"
        assert "fact-999" in new_variant["fact_ids"]
        # active_variant_id must point to the new variant.
        assert new_block["active_variant_id"] == new_variant["id"]

    @patch("app.services.fact_extractor.db")
    async def test_dedup_same_text_not_appended_twice(self, mock_db: MagicMock) -> None:
        """Same candidate_statement already exists in the block → not appended again."""
        import copy

        # Block already has the exact text we want to append.
        master = copy.deepcopy(_MASTER_RESUME)
        existing_text = "Led a team of engineers"
        mock_db.get_master_resume = AsyncMock(return_value=master)
        mock_db.update_resume = AsyncMock(return_value=master)

        result = await persist_variant_to_blocks(
            candidate_statement=existing_text,
            existing_fact_id="fact-001",
        )

        assert result["status"] == "ok"
        assert result["matched_blocks"] is True

        call_args = mock_db.update_resume.call_args
        updated_data: dict = call_args.args[1]["processed_data"]
        block = updated_data["workExperience"][0]["bullet_blocks"][0]
        # Should still have exactly 1 variant (no duplicate added).
        assert len(block["variants"]) == 1

    @patch("app.services.fact_extractor.db")
    async def test_raises_404_when_no_master_resume(self, mock_db: MagicMock) -> None:
        """HTTPException(404) when no master resume exists."""
        from fastapi import HTTPException

        mock_db.get_master_resume = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await persist_variant_to_blocks(
                candidate_statement="Some statement",
                existing_fact_id="fact-001",
            )

        assert exc_info.value.status_code == 404
        mock_db.update_resume.assert_not_called()

    @patch("app.services.fact_extractor.db")
    async def test_raises_404_when_no_processed_data(self, mock_db: MagicMock) -> None:
        """HTTPException(404) when master resume has no processed_data."""
        from fastapi import HTTPException

        mock_db.get_master_resume = AsyncMock(
            return_value={"resume_id": "master-1", "is_master": True, "processed_data": None}
        )

        with pytest.raises(HTTPException) as exc_info:
            await persist_variant_to_blocks(
                candidate_statement="Some statement",
                existing_fact_id="fact-001",
            )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestBug003Regression — silent-empty extract guard
# ---------------------------------------------------------------------------


class TestBug003Regression:
    """Regression tests for BUG-003: extract silently returned [] when the LLM
    responded with a shape that had no recognised wrapper key.

    Root cause: FACT_EXTRACTION_PROMPT asked for a bare JSON array, but
    ``_extract_json`` (brace-balance scan) extracted only the FIRST fact dict
    from ``[{...}, ...]``, producing ``{"statement": "...", ...}`` with no
    ``"facts"`` key.  ``raw.get("facts") or ...`` then returned ``None``, and
    ``candidates`` was silently set to ``[]``.

    The fix:
    1. Prompt now asks for ``{"facts": [...]}`` so the LLM output is a dict
       that ``_extract_json`` can extract cleanly.
    2. The service raises ``HTTPException(500)`` when the LLM returns a dict
       with no recognised wrapper key, making the failure explicit.
    3. Each candidate gets a temporary ``fact_id`` UUID for frontend key/select.
    """

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_raises_500_when_llm_returns_flat_fact_dict(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """BUG-003 regression: LLM returns a single flat fact dict (no 'facts'
        wrapper key) → HTTPException(500) instead of silent empty list.

        This is exactly what happened before the fix: ``_extract_json`` pulled
        the first ``{...}`` out of ``[{...}]``, leaving a dict like
        ``{"statement": "...", "context": "..."}`` with no recognised wrapper.
        Pre-fix code returned ``[]`` without any error; post-fix code raises so
        the frontend shows "Extraction failed" rather than an empty modal.
        """
        from fastapi import HTTPException

        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-bug003",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_db.list_facts = AsyncMock(return_value=[])
        # Simulate what _extract_json returned in the buggy scenario: a single
        # flat fact dict extracted from the first { in the LLM array response.
        mock_llm.return_value = {
            "statement": "Led a team of 8 engineers",
            "context": "Acme Corp",
            "source": "workExperience",
            "metrics_json": {},
            "tags_json": ["leadership"],
            "confidence": "candidate",
        }

        with pytest.raises(HTTPException) as exc_info:
            await extract_candidate_facts("resume-bug003")

        assert exc_info.value.status_code == 500
        assert "Fact extraction failed" in exc_info.value.detail

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_facts_wrapper_returns_candidates(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """Post-fix: LLM returns {"facts": [...]} → candidates returned correctly.

        This is the format the updated FACT_EXTRACTION_PROMPT instructs, and
        the format that ``complete_json`` + ``_extract_json`` can parse
        correctly because they both handle ``{...}`` objects.
        """
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-bug003-fixed",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_db.list_facts = AsyncMock(return_value=[])
        mock_llm.return_value = {"facts": [SAMPLE_CANDIDATE]}

        result = await extract_candidate_facts("resume-bug003-fixed")

        assert len(result) == 1
        assert result[0]["statement"] == SAMPLE_CANDIDATE["statement"]
        assert result[0]["confidence"] == "candidate"

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_each_candidate_gets_unique_fact_id(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """Each candidate gets a unique temporary fact_id for frontend key tracking.

        Pre-fix all candidates had fact_id='' (FactResponse default), causing
        React duplicate-key collisions and broken per-item checkbox state.
        """
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-uuid-test",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_db.list_facts = AsyncMock(return_value=[])
        mock_llm.return_value = {
            "facts": [
                {**SAMPLE_CANDIDATE, "statement": "Fact A"},
                {**SAMPLE_CANDIDATE, "statement": "Fact B"},
            ]
        }

        result = await extract_candidate_facts("resume-uuid-test")

        assert len(result) == 2
        ids = [r["fact_id"] for r in result]
        # Each ID must be a non-empty string and all must be distinct.
        assert all(isinstance(fid, str) and fid for fid in ids)
        assert ids[0] != ids[1]

    @patch("app.services.fact_extractor.complete_json", new_callable=AsyncMock)
    @patch("app.services.fact_extractor.db")
    async def test_empty_facts_list_returns_empty_not_error(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """{"facts": []} is a valid LLM response (no facts found) → returns [],
        does NOT raise.  This is distinct from the BUG-003 scenario where the
        key was absent entirely.
        """
        mock_db.get_resume = AsyncMock(
            return_value={
                "resume_id": "resume-empty-facts",
                "processed_data": SAMPLE_PROCESSED_DATA,
            }
        )
        mock_db.list_facts = AsyncMock(return_value=[])
        mock_llm.return_value = {"facts": []}

        result = await extract_candidate_facts("resume-empty-facts")

        assert result == []
