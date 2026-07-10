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
- generate_career_report: happy path, missing report, LLM errors, invalid citations
- CAREER_ADVICE_PROMPT: placeholder + canned response validation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.career_intelligence import (
    _build_archetypes_scores_block,
    _build_job_descriptions_block,
    _narrative_to_markdown,
    _validate_clustering_result,
    _validate_narrative_result,
    cluster_jds,
    generate_career_report,
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


# ---------------------------------------------------------------------------
# _validate_narrative_result
# ---------------------------------------------------------------------------


class TestValidateNarrativeResult:
    def test_valid_narrative_passes(self) -> None:
        narrative = {
            "target": ["Backend Engineer"],
            "stretch": [{"name": "ML Engineer", "gap_closing_plan": "Learn MLflow"}],
            "deprioritize": ["Frontend Dev"],
            "market_observations": "Backend roles are in high demand.",
            "cited_fact_ids": [],
            "cited_jd_ids": [],
        }
        result = _validate_narrative_result(narrative)
        assert result["target"] == ["Backend Engineer"]

    def test_non_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="instead of dict"):
            _validate_narrative_result("not a dict")

    def test_missing_required_key_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required keys"):
            _validate_narrative_result(
                {
                    "target": [],
                    "stretch": [],
                    # "deprioritize" and "market_observations" missing
                }
            )

    def test_extra_keys_allowed(self) -> None:
        """Extra keys in the narrative are ignored (the LLM may add extras)."""
        narrative = {
            "target": [],
            "stretch": [],
            "deprioritize": [],
            "market_observations": "...",
            "extra_key": "should be ignored",
        }
        result = _validate_narrative_result(narrative)
        assert "extra_key" in result  # preserved but not required


# ---------------------------------------------------------------------------
# _narrative_to_markdown
# ---------------------------------------------------------------------------


class TestNarrativeToMarkdown:
    def test_full_narrative_rendered(self) -> None:
        narrative = {
            "target": ["Backend Engineer"],
            "stretch": [{"name": "ML Engineer", "gap_closing_plan": "Learn MLflow and PyTorch."}],
            "deprioritize": ["Frontend Dev"],
            "market_observations": "Strong demand for Python backends.",
            "cited_fact_ids": [],
            "cited_jd_ids": [],
        }
        md = _narrative_to_markdown(narrative)
        assert "## Target Roles" in md
        assert "Backend Engineer" in md
        assert "## Stretch Opportunities" in md
        assert "ML Engineer" in md
        assert "Learn MLflow" in md
        assert "## Deprioritize" in md
        assert "Frontend Dev" in md
        assert "## Market Observations" in md
        assert "Python backends" in md

    def test_empty_sections_omitted(self) -> None:
        narrative = {
            "target": [],
            "stretch": [],
            "deprioritize": [],
            "market_observations": "",
        }
        md = _narrative_to_markdown(narrative)
        assert md.strip() == ""

    def test_string_items_in_stretch(self) -> None:
        """Stretch items that are plain strings (not dicts) render without error."""
        narrative = {
            "target": [],
            "stretch": ["ML Engineer"],
            "deprioritize": [],
            "market_observations": "",
        }
        md = _narrative_to_markdown(narrative)
        assert "ML Engineer" in md


# ---------------------------------------------------------------------------
# _build_archetypes_scores_block
# ---------------------------------------------------------------------------


class TestBuildArchetypesScoresBlock:
    def test_includes_archetype_names_and_scores(self) -> None:
        archetypes = [
            {
                "name": "Backend Engineer",
                "description": "Builds server-side systems.",
                "jd_ids": ["job-A"],
            }
        ]
        scores = {"Backend Engineer": {"attraction": 4.5, "fit": 0.75, "gaps": []}}
        block = _build_archetypes_scores_block(archetypes, scores)
        assert "Backend Engineer" in block
        assert "4.50" in block
        assert "75%" in block

    def test_gaps_listed(self) -> None:
        archetypes = [
            {
                "name": "ML Engineer",
                "description": "ML pipelines.",
                "jd_ids": ["job-B"],
            }
        ]
        scores = {
            "ML Engineer": {
                "attraction": 2.0,
                "fit": 0.3,
                "gaps": ["MLflow experience", "PyTorch skills"],
            }
        }
        block = _build_archetypes_scores_block(archetypes, scores)
        assert "MLflow experience" in block
        assert "PyTorch skills" in block


# ---------------------------------------------------------------------------
# generate_career_report — integration-style with mocked db + LLM
# ---------------------------------------------------------------------------

# Canned LLM narrative response
_VALID_NARRATIVE_RESULT = {
    "target": ["Backend Engineer"],
    "stretch": [{"name": "ML Engineer", "gap_closing_plan": "Complete MLflow course."}],
    "deprioritize": [],
    "market_observations": "Strong Python demand across all archetypes.",
    "cited_fact_ids": [],
    "cited_jd_ids": ["job-A"],
}

_SAMPLE_REPORT = {
    "id": 1,
    "created_at": "2026-07-10T00:00:00+00:00",
    "archetypes_json": _VALID_LLM_RESULT["archetypes"],
    "jd_ids_json": ["job-A", "job-B"],
    "scores_json": None,
    "advice_md": None,
    "model_used": None,
}

_UPDATED_REPORT = {
    **_SAMPLE_REPORT,
    "scores_json": {
        "Backend Engineer": {"attraction": 4.5, "fit": 0.5, "gaps": []},
        "ML Engineer": {"attraction": 0.0, "fit": 0.0, "gaps": []},
    },
    "advice_md": "## Target Roles\n- **Backend Engineer**",
    "model_used": "openai/gpt-4o",
}


class TestGenerateCareerReport:
    """Tests for generate_career_report() with mocked db + LLM."""

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_happy_path_updates_report(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """Happy path: LLM returns valid narrative → report updated and returned."""
        mock_db.get_career_reports = AsyncMock(return_value=[_SAMPLE_REPORT])
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, _JOB_B])
        mock_db.list_applications = AsyncMock(return_value=[])
        mock_db.get_master_resume = AsyncMock(
            return_value={"resume_id": "r1", "processed_data": {}}
        )
        mock_db.update_career_report = AsyncMock(return_value=_UPDATED_REPORT)
        mock_llm.return_value = _VALID_NARRATIVE_RESULT

        with patch("app.services.career_intelligence.get_llm_config") as mock_cfg, \
             patch("app.services.career_intelligence.get_model_name") as mock_mn:
            mock_mn.return_value = "openai/gpt-4o"
            mock_cfg.return_value = MagicMock()
            report = await generate_career_report()

        assert report["id"] == 1
        assert report["scores_json"] is not None
        assert report["advice_md"] is not None
        mock_db.update_career_report.assert_called_once()
        call_kwargs = mock_db.update_career_report.call_args.kwargs
        assert call_kwargs["report_id"] == 1
        # scores_json is now a list of dicts (not a dict keyed by name)
        scores_list = call_kwargs["scores_json"]
        assert isinstance(scores_list, list)
        assert any(s["archetype_name"] == "Backend Engineer" for s in scores_list)

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_no_career_reports_raises_400(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """No career reports in DB → HTTP 400."""
        mock_db.get_career_reports = AsyncMock(return_value=[])

        with pytest.raises(HTTPException) as exc_info:
            await generate_career_report()

        assert exc_info.value.status_code == 400
        mock_llm.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_no_master_resume_raises_400(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """No master resume → HTTP 400."""
        mock_db.get_career_reports = AsyncMock(return_value=[_SAMPLE_REPORT])
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, _JOB_B])
        mock_db.list_applications = AsyncMock(return_value=[])
        mock_db.get_master_resume = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await generate_career_report()

        assert exc_info.value.status_code == 400
        mock_llm.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_llm_exception_raises_500(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """LLM raises an exception → HTTP 500, no update."""
        mock_db.get_career_reports = AsyncMock(return_value=[_SAMPLE_REPORT])
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, _JOB_B])
        mock_db.list_applications = AsyncMock(return_value=[])
        mock_db.get_master_resume = AsyncMock(
            return_value={"resume_id": "r1", "processed_data": {}}
        )
        mock_db.update_career_report = AsyncMock()
        mock_llm.side_effect = RuntimeError("LLM timeout")

        with pytest.raises(HTTPException) as exc_info:
            await generate_career_report()

        assert exc_info.value.status_code == 500
        mock_db.update_career_report.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_malformed_llm_output_raises_500(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """LLM returns non-dict → HTTP 500, no update."""
        mock_db.get_career_reports = AsyncMock(return_value=[_SAMPLE_REPORT])
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, _JOB_B])
        mock_db.list_applications = AsyncMock(return_value=[])
        mock_db.get_master_resume = AsyncMock(
            return_value={"resume_id": "r1", "processed_data": {}}
        )
        mock_db.update_career_report = AsyncMock()
        mock_llm.return_value = "not a dict"

        with pytest.raises(HTTPException) as exc_info:
            await generate_career_report()

        assert exc_info.value.status_code == 500
        mock_db.update_career_report.assert_not_called()

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_invalid_cited_fact_ids_are_ignored(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """LLM cites a non-existent fact_id → fact IDs are not validated (no IDs
        in prompt), so advice_md still contains valid Markdown (not an error marker)."""
        narrative_with_bad_fact_ids = {
            **_VALID_NARRATIVE_RESULT,
            "cited_fact_ids": ["nonexistent-fact-uuid"],
            "cited_jd_ids": [],  # no jd_ids cited → jd validation passes
        }
        mock_db.get_career_reports = AsyncMock(return_value=[_SAMPLE_REPORT])
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, _JOB_B])
        mock_db.list_applications = AsyncMock(return_value=[])
        mock_db.get_master_resume = AsyncMock(
            return_value={"resume_id": "r1", "processed_data": {}}
        )
        mock_db.update_career_report = AsyncMock(return_value=_UPDATED_REPORT)
        mock_llm.return_value = narrative_with_bad_fact_ids

        with patch("app.services.career_intelligence.get_llm_config"), \
             patch("app.services.career_intelligence.get_model_name", return_value=None):
            await generate_career_report()

        call_kwargs = mock_db.update_career_report.call_args.kwargs
        # Fact IDs are no longer validated — bad fact IDs are silently ignored.
        assert "[CITATION ERROR" not in call_kwargs["advice_md"]
        assert "##" in call_kwargs["advice_md"]

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_invalid_cited_jd_ids_flags_report(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """LLM cites a jd_id that does not exist → advice_md set to error marker."""
        narrative_with_bad_jd = {
            **_VALID_NARRATIVE_RESULT,
            "cited_fact_ids": [],
            "cited_jd_ids": ["invented-jd-id"],
        }
        mock_db.get_career_reports = AsyncMock(return_value=[_SAMPLE_REPORT])
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, _JOB_B])
        mock_db.list_applications = AsyncMock(return_value=[])
        mock_db.get_master_resume = AsyncMock(
            return_value={"resume_id": "r1", "processed_data": {}}
        )
        updated_with_error = {**_SAMPLE_REPORT, "advice_md": "[CITATION ERROR: invalid IDs cited]"}
        mock_db.update_career_report = AsyncMock(return_value=updated_with_error)
        mock_llm.return_value = narrative_with_bad_jd

        with patch("app.services.career_intelligence.get_llm_config"), \
             patch("app.services.career_intelligence.get_model_name", return_value=None):
            report = await generate_career_report()

        call_kwargs = mock_db.update_career_report.call_args.kwargs
        assert call_kwargs["advice_md"] == "[CITATION ERROR: invalid IDs cited]"

    @patch("app.services.career_intelligence.complete_json", new_callable=AsyncMock)
    @patch("app.services.career_intelligence.db")
    async def test_valid_cited_ids_produce_markdown(
        self, mock_db: MagicMock, mock_llm: AsyncMock
    ) -> None:
        """Valid cited IDs → advice_md contains real Markdown (not error marker)."""
        narrative_clean = {
            **_VALID_NARRATIVE_RESULT,
            "cited_fact_ids": ["fact-1"],
            "cited_jd_ids": ["job-A"],
        }
        mock_db.get_career_reports = AsyncMock(return_value=[_SAMPLE_REPORT])
        mock_db.list_jobs = AsyncMock(return_value=[_JOB_A, _JOB_B])
        mock_db.list_applications = AsyncMock(return_value=[])
        mock_db.get_master_resume = AsyncMock(
            return_value={"resume_id": "r1", "processed_data": {}}
        )
        mock_db.update_career_report = AsyncMock(return_value=_UPDATED_REPORT)
        mock_llm.return_value = narrative_clean

        with patch("app.services.career_intelligence.get_llm_config"), \
             patch("app.services.career_intelligence.get_model_name", return_value=None):
            await generate_career_report()

        call_kwargs = mock_db.update_career_report.call_args.kwargs
        assert "[CITATION ERROR" not in call_kwargs["advice_md"]
        assert "##" in call_kwargs["advice_md"]  # has Markdown headings


# ---------------------------------------------------------------------------
# CAREER_ADVICE_PROMPT — deterministic parser test
# ---------------------------------------------------------------------------


class TestCareerAdvicePrompt:
    """Verify the advice prompt template and a canned LLM response."""

    def test_prompt_contains_required_placeholders(self) -> None:
        from app.prompts.templates import CAREER_ADVICE_PROMPT

        assert "{archetypes_with_scores}" in CAREER_ADVICE_PROMPT
        assert "{output_language}" in CAREER_ADVICE_PROMPT

    def test_prompt_formats_without_error(self) -> None:
        from app.prompts.templates import CAREER_ADVICE_PROMPT

        rendered = CAREER_ADVICE_PROMPT.format(
            archetypes_with_scores="--- ARCHETYPE: Backend Engineer ---\nFit: 75%",
            output_language="English",
        )
        assert "Backend Engineer" in rendered
        assert "English" in rendered

    def test_canned_response_validates(self) -> None:
        """A canned LLM narrative response passes _validate_narrative_result."""
        canned = {
            "target": ["Backend Engineer"],
            "stretch": [
                {
                    "name": "ML Engineer",
                    "gap_closing_plan": "Complete MLflow course and build a side project.",
                }
            ],
            "deprioritize": ["Frontend Developer"],
            "market_observations": "Backend Python roles dominate the current JD set.",
            "cited_fact_ids": [],
            "cited_jd_ids": [],
        }
        result = _validate_narrative_result(canned)
        assert result["target"] == ["Backend Engineer"]
        assert result["stretch"][0]["name"] == "ML Engineer"
        assert "MLflow" in result["stretch"][0]["gap_closing_plan"]
