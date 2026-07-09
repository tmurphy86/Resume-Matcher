"""Service tests for interview_mode — async with mocked LLM and db."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.services.interview_mode import (
    _build_jd_gaps,
    _extract_metrics_from_answer,
    _format_uncovered_bullets,
    answer_gap_question,
    get_gap_questions,
)


# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

SAMPLE_JOB = {
    "job_id": "job-123",
    "content": "Senior Python engineer. Requires Kubernetes, FastAPI, PostgreSQL.",
    "keywords": {
        "required_skills": ["Kubernetes", "FastAPI"],
        "preferred_skills": ["PostgreSQL"],
        "key_responsibilities": ["Design scalable APIs"],
    },
}

SAMPLE_RESUME = {
    "resume_id": "resume-abc",
    "processed_data": {
        "personalInfo": {"name": "Jane Doe"},
        "summary": "Backend engineer.",
        "workExperience": [
            {
                "title": "Engineer",
                "company": "Acme",
                "description": ["Built REST APIs using FastAPI", "Led team of 5"],
            }
        ],
        "education": [],
        "personalProjects": [],
        "additional": {"technicalSkills": ["Python", "FastAPI"]},
        "customSections": {},
    },
}

SAMPLE_FACTS = [
    {
        "fact_id": "fact-001",
        "statement": "Led a team of 5 engineers.",
        "confidence": "verified",
        "context": "Acme",
        "source": "workExperience",
        "metrics_json": {},
        "tags_json": [],
    }
]

LLM_QUESTIONS_RESPONSE = {
    "questions": [
        {
            "question": "Can you describe a specific project where you used Kubernetes in production?",
            "gap_type": "skill",
            "jd_keyword": "Kubernetes",
        },
        {
            "question": "What was the largest PostgreSQL database you managed, and what were the performance challenges?",
            "gap_type": "achievement",
            "jd_keyword": "PostgreSQL",
        },
    ]
}


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


class TestBuildJdGaps:
    def test_returns_gaps_not_covered_by_facts(self) -> None:
        keywords = {
            "required_skills": ["Kubernetes", "FastAPI"],
            "preferred_skills": [],
            "key_responsibilities": [],
        }
        facts = [{"statement": "Built REST APIs using FastAPI", "fact_id": "f1"}]
        result = _build_jd_gaps(keywords, facts)
        assert "Kubernetes" in result
        assert "FastAPI" not in result  # FastAPI appears in facts

    def test_all_covered_returns_sentinel(self) -> None:
        keywords = {"required_skills": ["Python"], "preferred_skills": [], "key_responsibilities": []}
        facts = [{"statement": "Expert Python developer", "fact_id": "f1"}]
        result = _build_jd_gaps(keywords, facts)
        assert result == "No specific gaps identified."

    def test_empty_facts_all_are_gaps(self) -> None:
        keywords = {
            "required_skills": ["Docker"],
            "preferred_skills": ["Terraform"],
            "key_responsibilities": [],
        }
        result = _build_jd_gaps(keywords, [])
        assert "Docker" in result
        assert "Terraform" in result


class TestExtractMetricsFromAnswer:
    def test_extracts_percentage(self) -> None:
        metrics = _extract_metrics_from_answer("Improved API performance by 40%.")
        assert any("40%" in v for v in metrics.values())

    def test_extracts_multiplier(self) -> None:
        metrics = _extract_metrics_from_answer("Achieved 3x throughput improvement.")
        assert any("3x" in v for v in metrics.values())

    def test_extracts_dollar_amount(self) -> None:
        metrics = _extract_metrics_from_answer("Revenue grew to $2M monthly.")
        assert any("$2M" in v for v in metrics.values())

    def test_empty_answer_returns_empty_dict(self) -> None:
        metrics = _extract_metrics_from_answer("No numbers here.")
        assert metrics == {}


class TestFormatUncoveredBullets:
    def test_legacy_bullets_all_uncovered(self) -> None:
        resume_data = {
            "summary": "Engineer.",
            "workExperience": [
                {
                    "title": "Engineer",
                    "company": "Acme",
                    "description": ["Built APIs", "Led migration"],
                }
            ],
        }
        result = _format_uncovered_bullets(resume_data)
        assert "Built APIs" in result
        assert "Led migration" in result

    def test_empty_resume_returns_none(self) -> None:
        result = _format_uncovered_bullets({})
        assert result == "None"


# ---------------------------------------------------------------------------
# TestGetGapQuestions
# ---------------------------------------------------------------------------


class TestGetGapQuestions:
    @patch("app.services.interview_mode.complete_json", new_callable=AsyncMock)
    @patch("app.services.interview_mode.db")
    async def test_happy_path_returns_question_list(self, mock_db: AsyncMock, mock_llm: AsyncMock) -> None:
        """Happy path: returns list of question dicts from LLM."""
        mock_db.get_job = AsyncMock(return_value=SAMPLE_JOB)
        mock_db.get_resume = AsyncMock(return_value=SAMPLE_RESUME)
        mock_db.list_facts = AsyncMock(return_value=SAMPLE_FACTS)
        mock_llm.return_value = LLM_QUESTIONS_RESPONSE

        result = await get_gap_questions(job_id="job-123", resume_id="resume-abc")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["question"] == LLM_QUESTIONS_RESPONSE["questions"][0]["question"]
        assert result[0]["gap_type"] == "skill"
        assert result[0]["jd_keyword"] == "Kubernetes"

    @patch("app.services.interview_mode.db")
    async def test_job_not_found_raises_404(self, mock_db: AsyncMock) -> None:
        """db.get_job returns None → HTTPException 404."""
        mock_db.get_job = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_gap_questions(job_id="missing", resume_id="resume-abc")

        assert exc_info.value.status_code == 404

    @patch("app.services.interview_mode.db")
    async def test_resume_not_found_raises_404(self, mock_db: AsyncMock) -> None:
        """db.get_resume returns None → HTTPException 404."""
        mock_db.get_job = AsyncMock(return_value=SAMPLE_JOB)
        mock_db.get_resume = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_gap_questions(job_id="job-123", resume_id="missing")

        assert exc_info.value.status_code == 404

    @patch("app.services.interview_mode.complete_json", new_callable=AsyncMock)
    @patch("app.services.interview_mode.db")
    async def test_skips_non_dict_llm_items(self, mock_db: AsyncMock, mock_llm: AsyncMock) -> None:
        """Non-dict items in LLM output are skipped silently."""
        mock_db.get_job = AsyncMock(return_value=SAMPLE_JOB)
        mock_db.get_resume = AsyncMock(return_value=SAMPLE_RESUME)
        mock_db.list_facts = AsyncMock(return_value=[])
        mock_llm.return_value = {"questions": ["not a dict", {"question": "Valid?", "gap_type": "skill", "jd_keyword": "Go"}]}

        result = await get_gap_questions(job_id="job-123", resume_id="resume-abc")

        assert len(result) == 1
        assert result[0]["question"] == "Valid?"

    @patch("app.services.interview_mode.complete_json", new_callable=AsyncMock)
    @patch("app.services.interview_mode.db")
    async def test_uses_cached_keywords_from_job(self, mock_db: AsyncMock, mock_llm: AsyncMock) -> None:
        """If job has a keywords dict, LLM keyword extraction is skipped."""
        mock_db.get_job = AsyncMock(return_value=SAMPLE_JOB)  # has keywords
        mock_db.get_resume = AsyncMock(return_value=SAMPLE_RESUME)
        mock_db.list_facts = AsyncMock(return_value=[])
        mock_llm.return_value = {"questions": []}

        await get_gap_questions(job_id="job-123", resume_id="resume-abc")

        # LLM should be called ONCE (for questions), not twice (keyword extraction skipped)
        assert mock_llm.call_count == 1


# ---------------------------------------------------------------------------
# TestAnswerGapQuestion
# ---------------------------------------------------------------------------


class TestAnswerGapQuestion:
    @patch("app.services.interview_mode.get_gap_questions", new_callable=AsyncMock)
    @patch("app.services.interview_mode.db")
    async def test_persists_fact_with_correct_confidence(
        self, mock_db: AsyncMock, mock_get_gaps: AsyncMock
    ) -> None:
        """Answer is persisted with confidence='user_answered' and source='interview'."""
        persisted_fact = {
            "fact_id": "fact-new-1",
            "statement": "Deployed Kubernetes clusters on AWS EKS.",
            "confidence": "user_answered",
            "source": "interview",
            "context": "job-123",
            "metrics_json": {},
            "tags_json": ["interview", "user_answered"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        mock_db.create_fact = AsyncMock(return_value=persisted_fact)
        mock_get_gaps.return_value = []

        result = await answer_gap_question(
            question="Describe your Kubernetes experience.",
            answer="Deployed Kubernetes clusters on AWS EKS.",
            job_id="job-123",
            resume_id="resume-abc",
        )

        call_kwargs = mock_db.create_fact.call_args.kwargs
        assert call_kwargs["confidence"] == "user_answered"
        assert call_kwargs["source"] == "interview"
        assert call_kwargs["context"] == "job-123"
        assert "interview" in call_kwargs["tags_json"]
        assert "user_answered" in call_kwargs["tags_json"]

    @patch("app.services.interview_mode.get_gap_questions", new_callable=AsyncMock)
    @patch("app.services.interview_mode.db")
    async def test_returns_fact_and_gap_questions(
        self, mock_db: AsyncMock, mock_get_gaps: AsyncMock
    ) -> None:
        """Response contains both 'fact' and 'gap_questions' keys."""
        persisted_fact = {
            "fact_id": "fact-new-2",
            "statement": "Used PostgreSQL for 5 years.",
            "confidence": "user_answered",
            "source": "interview",
            "context": "job-123",
            "metrics_json": {},
            "tags_json": ["interview", "user_answered"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        remaining_gaps = [
            {"question": "Any Kubernetes experience?", "gap_type": "skill", "jd_keyword": "Kubernetes"}
        ]
        mock_db.create_fact = AsyncMock(return_value=persisted_fact)
        mock_get_gaps.return_value = remaining_gaps

        result = await answer_gap_question(
            question="Describe your PostgreSQL experience.",
            answer="Used PostgreSQL for 5 years.",
            job_id="job-123",
            resume_id="resume-abc",
        )

        assert "fact" in result
        assert "gap_questions" in result
        assert result["fact"]["fact_id"] == "fact-new-2"
        assert result["gap_questions"] == remaining_gaps

    @patch("app.services.interview_mode.get_gap_questions", new_callable=AsyncMock)
    @patch("app.services.interview_mode.db")
    async def test_extracts_metrics_from_answer(
        self, mock_db: AsyncMock, mock_get_gaps: AsyncMock
    ) -> None:
        """Metrics are extracted from the answer and stored in metrics_json."""
        mock_db.create_fact = AsyncMock(
            return_value={
                "fact_id": "fact-metric-1",
                "statement": "Scaled system to handle 50% more traffic.",
                "confidence": "user_answered",
                "source": "interview",
                "context": "job-123",
                "metrics_json": {"metric_0": "50%"},
                "tags_json": ["interview", "user_answered"],
                "created_at": "",
                "updated_at": "",
            }
        )
        mock_get_gaps.return_value = []

        await answer_gap_question(
            question="How did you scale the system?",
            answer="Scaled system to handle 50% more traffic.",
            job_id="job-123",
            resume_id="resume-abc",
        )

        call_kwargs = mock_db.create_fact.call_args.kwargs
        assert "metric_0" in call_kwargs["metrics_json"]
        assert call_kwargs["metrics_json"]["metric_0"] == "50%"

    @patch("app.services.interview_mode.get_gap_questions", new_callable=AsyncMock)
    @patch("app.services.interview_mode.db")
    async def test_gap_refresh_failure_still_returns_fact(
        self, mock_db: AsyncMock, mock_get_gaps: AsyncMock
    ) -> None:
        """If gap refresh fails, the persisted fact is still returned (graceful degradation)."""
        mock_db.create_fact = AsyncMock(
            return_value={
                "fact_id": "fact-003",
                "statement": "Answer text.",
                "confidence": "user_answered",
                "source": "interview",
                "context": "job-123",
                "metrics_json": {},
                "tags_json": ["interview", "user_answered"],
                "created_at": "",
                "updated_at": "",
            }
        )
        mock_get_gaps.side_effect = HTTPException(status_code=500, detail="LLM blip")

        result = await answer_gap_question(
            question="Q?",
            answer="Answer text.",
            job_id="job-123",
            resume_id="resume-abc",
        )

        assert result["fact"]["fact_id"] == "fact-003"
        assert result["gap_questions"] == []
