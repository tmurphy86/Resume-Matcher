"""Service tests for career_intelligence — canned LLM responses, no real LLM calls.

Tests cover:
- Happy path: valid clustering result → CareerReport persisted
- Malformed output (non-dict) → HTTPException(500), no persistence
- Missing archetypes key → HTTPException(500), no persistence
- Unassigned job IDs → HTTPException(500), no persistence
- Duplicate job ID across archetypes → HTTPException(500), no persistence
- Invented job IDs from LLM → HTTPException(500), no persistence
- No parsed jobs → HTTPException(400)
- ARCHETYPE_CLUSTER_PROMPT: format/placeholder test with canned LLM response
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.career_intelligence import (
    _build_job_descriptions_block,
    _validate_clustering_result,
    cluster_jds,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_PARSED_A = {
    "responsibilities": ["Design scalable APIs", "Mentor engineers"],
    "requirements": ["5+ years Python", "FastAPI"],
    "level": "Senior",
    "comp": "$150k",
}

_PARSED_B = {
    "responsibilities": ["Manage ML pipelines", "Collaborate with data scientists"],
    "requirements": ["Python", "MLflow", "3+ years ML experience"],
    "level": "Mid",
    "comp": None,
}

_JOB_A = {
    "job_id": "job-A",
    "content": "Senior Python Engineer",
    "created_at": "2026-01-01T00:00:00+00:00",
    "parsed": _PARSED_A,
}

_JOB_B = {
    "job_id": "job-B",
    "content": "ML Engineer",
    "created_at": "2026-01-02T00:00:00+00:00",
    "parsed": _PARSED_B,
}

_VALID_LLM_RESULT = {
    "archetypes": [
        {
            "name": "Backend Engineer",
            "description": "Builds and maintains server-side systems.",
            "jd_ids": ["job-A"],
            "responsibilities": ["Design APIs", "Mentor team members"],
        },
        {
            "name": "ML Engineer",
            "description": "Owns machine-learning pipelines end to end.",
            "jd_ids": ["job-B"],
            "responsibilities": ["Manage ML pipelines", "Collaborate with data scientists"],
        },
    ]
}


# ---------------------------------------------------------------------------
# _build_job_descriptions_block
# ---------------------------------------------------------------------------


class TestBuildJobDescriptionsBlock:
    """Unit tests for the prompt-building helper."""

    def test_includes_job_id_and_level(self) -> None:
        block = _build_job_descriptions_block([_JOB_A])
        assert "job-A" in block
        assert "Senior" in block

    def test_includes_responsibilities(self) -> None:
        block = _build_job_descriptions_block([_JOB_A])
        assert "Design scalable APIs" in block

    def test_omits_none_comp(self) -> None:
        block = _build_job_descriptions_block([_JOB_B])
        # comp is None for _JOB_B — should not appear as "None"
        assert "Comp: None" not in block

    def test_multiple_jobs(self) -> None:
        block = _build_job_descriptions_block([_JOB_A, _JOB_B])
        assert "job-A" in block
        assert "job-B" in block

    def test_empty_list(self) -> None:
        block = _build_job_descriptions_block([])
        assert block.strip() == ""


# ---------------------------------------------------------------------------
# _validate_clustering_result
# ---------------------------------------------------------------------------


class TestValidateClusteringResult:
    """Unit tests for result validation logic."""

    def test_valid_result_returns_archetypes(self) -> None:
        archetypes = _validate_clustering_result(
            _VALID_LLM_RESULT, {"job-A", "job-B"}
        )
        assert len(archetypes) == 2
        assert archetypes[0]["name"] == "Backend Engineer"

    def test_non_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="instead of dict"):
            _validate_clustering_result("not a dict", {"job-A"})

    def test_missing_archetypes_key_raises(self) -> None:
        with pytest.raises(ValueError, match="missing 'archetypes'"):
            _validate_clustering_result({"other": []}, {"job-A"})

    def test_archetype_not_dict_raises(self) -> None:
        result = {"archetypes": ["not-a-dict"]}
        with pytest.raises(ValueError, match="not a dict"):
            _validate_clustering_result(result, set())

    def test_archetype_missing_keys_raises(self) -> None:
        result = {
            "archetypes": [
                {"name": "X", "jd_ids": ["job-A"]}  # missing description + responsibilities
            ]
        }
        with pytest.raises(ValueError, match="missing keys"):
            _validate_clustering_result(result, {"job-A"})

    def test_unassigned_job_id_raises(self) -> None:
        result = {
            "archetypes": [
                {
                    "name": "X",
                    "description": "Desc",
                    "jd_ids": ["job-A"],
                    "responsibilities": [],
                }
            ]
        }
        with pytest.raises(ValueError, match="not assigned"):
            _validate_clustering_result(result, {"job-A", "job-B"})

    def test_duplicate_job_id_raises(self) -> None:
        result = {
            "archetypes": [
                {
                    "name": "X",
                    "description": "Desc",
                    "jd_ids": ["job-A"],
                    "responsibilities": [],
                },
                {
                    "name": "Y",
                    "description": "Desc2",
                    "jd_ids": ["job-A"],  # duplicate!
                    "responsibilities": [],
                },
            ]
        }
        with pytest.raises(ValueError, match="multiple archetypes"):
            _validate_clustering_result(result, {"job-A"})

    def test_invented_job_id_raises(self) -> None:
        result = {
            "archetypes": [
                {
                    "name": "X",
                    "description": "Desc",
                    "jd_ids": ["job-Z"],  # not in expected
                    "responsibilities": [],
                }
            ]
        }
        with pytest.raises(ValueError, match="invented"):
            _validate_clustering_result(result, {"job-A"})


# ---------------------------------------------------------------------------
# cluster_jds — integration-style with mocked db + LLM
# ---------------------------------------------------------------------------


class TestClusterJds:
    """Tests for the top-level cluster_jds() service function."""

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_happy_path_returns_report(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """Valid LLM response → report persisted and returned."""
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, _JOB_B])
        mock_llm.return_value = _VALID_LLM_RESULT
        expected_report = {
            "id": 1,
            "created_at": "2026-07-10T00:00:00+00:00",
            "archetypes_json": _VALID_LLM_RESULT["archetypes"],
            "jd_ids_json": ["job-A", "job-B"],
            "scores_json": None,
            "advice_md": None,
            "model_used": None,
        }
        mock_db.create_career_report = AsyncMock(return_value=expected_report)

        report = await cluster_jds()

        assert report["id"] == 1
        assert report["scores_json"] is None
        assert report["advice_md"] is None
        mock_db.create_career_report.assert_called_once()
        call_kwargs = mock_db.create_career_report.call_args.kwargs
        assert len(call_kwargs["archetypes_json"]) == 2
        assert set(call_kwargs["jd_ids_json"]) == {"job-A", "job-B"}
        assert call_kwargs["scores_json"] is None
        assert call_kwargs["advice_md"] is None
        assert call_kwargs["model_used"] is None

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_no_parsed_jobs_raises_400(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """No parsed jobs available → HTTP 400 raised."""
        unparsed_job = {**_JOB_A, "parsed": None}
        del unparsed_job["parsed"]  # ensure key absent
        mock_db.list_jobs = AsyncMock(return_value=[unparsed_job])

        with pytest.raises(HTTPException) as exc_info:
            await cluster_jds()

        assert exc_info.value.status_code == 400
        mock_llm.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_empty_jobs_table_raises_400(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """Empty jobs table → HTTP 400 raised."""
        mock_db.list_jobs = AsyncMock(return_value=[])

        with pytest.raises(HTTPException) as exc_info:
            await cluster_jds()

        assert exc_info.value.status_code == 400
        mock_llm.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_llm_exception_raises_500(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """LLM raises an exception → HTTP 500, no persistence."""
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A])
        mock_llm.side_effect = RuntimeError("LLM timed out")
        mock_db.create_career_report = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await cluster_jds()

        assert exc_info.value.status_code == 500
        mock_db.create_career_report.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_malformed_llm_output_raises_500(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """LLM returns non-dict → HTTP 500, no persistence."""
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A])
        mock_llm.return_value = "this is not valid JSON structure"
        mock_db.create_career_report = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await cluster_jds()

        assert exc_info.value.status_code == 500
        mock_db.create_career_report.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_unassigned_job_ids_raises_500(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """LLM assigns job-A but omits job-B → HTTP 500, no persistence."""
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, _JOB_B])
        # Only assigns job-A; job-B goes missing.
        mock_llm.return_value = {
            "archetypes": [
                {
                    "name": "Backend Engineer",
                    "description": "Builds server-side systems.",
                    "jd_ids": ["job-A"],
                    "responsibilities": ["Design APIs"],
                }
            ]
        }
        mock_db.create_career_report = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await cluster_jds()

        assert exc_info.value.status_code == 500
        mock_db.create_career_report.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_duplicate_job_id_in_archetypes_raises_500(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """LLM assigns job-A to two archetypes → HTTP 500, no persistence."""
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A])
        mock_llm.return_value = {
            "archetypes": [
                {
                    "name": "Backend Engineer",
                    "description": "Desc 1.",
                    "jd_ids": ["job-A"],
                    "responsibilities": ["Design APIs"],
                },
                {
                    "name": "Duplicate Archetype",
                    "description": "Desc 2.",
                    "jd_ids": ["job-A"],  # duplicate assignment
                    "responsibilities": ["Duplicate work"],
                },
            ]
        }
        mock_db.create_career_report = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await cluster_jds()

        assert exc_info.value.status_code == 500
        mock_db.create_career_report.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_only_parsed_jobs_sent_to_llm(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """Jobs without 'parsed' key are excluded from the clustering prompt."""
        unparsed_job = {
            "job_id": "job-NOPARSED",
            "content": "Some raw JD without parsing",
            "created_at": "2026-01-03T00:00:00+00:00",
        }
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, unparsed_job])
        mock_llm.return_value = {
            "archetypes": [
                {
                    "name": "Backend Engineer",
                    "description": "Desc.",
                    "jd_ids": ["job-A"],  # only job-A; unparsed job excluded
                    "responsibilities": ["Design APIs"],
                }
            ]
        }
        mock_db.create_career_report = AsyncMock(return_value={
            "id": 2,
            "created_at": "2026-07-10T00:00:00+00:00",
            "archetypes_json": mock_llm.return_value["archetypes"],
            "jd_ids_json": ["job-A"],
            "scores_json": None,
            "advice_md": None,
            "model_used": None,
        })

        report = await cluster_jds()

        # Prompt must not include the unparsed job.
        call_args = mock_llm.call_args
        prompt_text: str = call_args.args[0]
        assert "job-NOPARSED" not in prompt_text
        assert "job-A" in prompt_text
        # Only one job in jd_ids_json.
        assert report["jd_ids_json"] == ["job-A"]


# ---------------------------------------------------------------------------
# ARCHETYPE_CLUSTER_PROMPT — deterministic parser test
# ---------------------------------------------------------------------------


class TestArchetypeClusterPrompt:
    """Verify the prompt template and validate a canned LLM response string."""

    def test_prompt_contains_required_placeholders(self) -> None:
        from app.prompts.templates import ARCHETYPE_CLUSTER_PROMPT

        assert "{output_language}" in ARCHETYPE_CLUSTER_PROMPT
        assert "{job_descriptions_block}" in ARCHETYPE_CLUSTER_PROMPT
        assert "{max_archetypes}" in ARCHETYPE_CLUSTER_PROMPT

    def test_prompt_formats_without_error(self) -> None:
        from app.prompts.templates import ARCHETYPE_CLUSTER_PROMPT

        rendered = ARCHETYPE_CLUSTER_PROMPT.format(
            output_language="English",
            max_archetypes=10,
            job_descriptions_block="--- JOB ID: job-1 ---\nResponsibilities:\n  - Build things",
        )
        assert "job-1" in rendered
        assert "English" in rendered

    def test_canned_response_validates(self) -> None:
        """A canned LLM JSON response passes _validate_clustering_result."""
        canned: dict = {
            "archetypes": [
                {
                    "name": "Platform Engineer",
                    "description": "Owns backend infrastructure.",
                    "jd_ids": ["job-1", "job-2"],
                    "responsibilities": ["Build services", "On-call rotation"],
                }
            ]
        }
        result = _validate_clustering_result(canned, {"job-1", "job-2"})
        assert result[0]["name"] == "Platform Engineer"
        assert set(result[0]["jd_ids"]) == {"job-1", "job-2"}
