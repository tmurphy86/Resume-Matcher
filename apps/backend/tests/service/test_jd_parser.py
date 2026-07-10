"""Service tests for jd_parser — async with mocked LLM and db."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.jd_parser import backfill_parse_jobs, parse_job_description

# ---------------------------------------------------------------------------
# Shared fixtures / sample data
# ---------------------------------------------------------------------------

SAMPLE_JD = (
    "We are looking for a Senior Python Engineer to join our platform team. "
    "Responsibilities include designing scalable APIs and mentoring junior engineers. "
    "Requirements: 5+ years Python, experience with FastAPI and AWS. "
    "Compensation: $150,000 - $180,000."
)

SAMPLE_PARSED_RESPONSE = {
    "responsibilities": [
        "Design scalable APIs",
        "Mentor junior engineers",
    ],
    "requirements": [
        "5+ years Python experience",
        "Experience with FastAPI and AWS",
    ],
    "level": "Senior",
    "comp": "$150,000 - $180,000",
}

SAMPLE_JOB = {
    "job_id": "job-001",
    "content": SAMPLE_JD,
    "resume_id": None,
    "created_at": "2026-01-01T00:00:00+00:00",
}


# ---------------------------------------------------------------------------
# TestParseJobDescription — happy path and error handling
# ---------------------------------------------------------------------------


class TestParseJobDescription:
    """Tests for parse_job_description() with mocked LLM and db."""

    @patch("app.services.jd_parser.complete_json", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_happy_path_stores_parsed(self, mock_db: AsyncMock, mock_llm: AsyncMock) -> None:
        """Happy path: LLM returns valid dict → stored in metadata_json['parsed']."""
        mock_llm.return_value = SAMPLE_PARSED_RESPONSE
        mock_db.get_job = AsyncMock(return_value=SAMPLE_JOB)
        mock_db.update_job = AsyncMock(return_value={**SAMPLE_JOB, "parsed": SAMPLE_PARSED_RESPONSE})

        result = await parse_job_description("job-001", SAMPLE_JD)

        assert result is not None
        assert result["responsibilities"] == SAMPLE_PARSED_RESPONSE["responsibilities"]
        assert result["requirements"] == SAMPLE_PARSED_RESPONSE["requirements"]
        assert result["level"] == "Senior"
        assert result["comp"] == "$150,000 - $180,000"

        # Must persist via update_job with the parsed key.
        mock_db.update_job.assert_called_once()
        call_args = mock_db.update_job.call_args
        assert call_args.args[0] == "job-001"
        assert "parsed" in call_args.args[1]

    @patch("app.services.jd_parser.complete_json", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_malformed_llm_output_returns_none(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """Malformed LLM output (non-dict) → logged, returns None, no update_job call."""
        mock_llm.return_value = "this is not a dict"
        mock_db.get_job = AsyncMock(return_value=SAMPLE_JOB)
        mock_db.update_job = AsyncMock()

        result = await parse_job_description("job-001", SAMPLE_JD)

        assert result is None
        mock_db.update_job.assert_not_called()

    @patch("app.services.jd_parser.complete_json", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_llm_exception_returns_none(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """LLM raises an exception → logged, returns None, upload not blocked."""
        mock_llm.side_effect = RuntimeError("LLM timed out")
        mock_db.update_job = AsyncMock()

        result = await parse_job_description("job-001", SAMPLE_JD)

        assert result is None
        mock_db.update_job.assert_not_called()

    @patch("app.services.jd_parser.complete_json", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_partial_llm_response_uses_defaults(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """LLM returns dict missing optional fields → level/comp default to None."""
        mock_llm.return_value = {
            "responsibilities": ["Build things"],
            "requirements": ["5 years experience"],
            # level and comp intentionally absent
        }
        mock_db.get_job = AsyncMock(return_value=SAMPLE_JOB)
        mock_db.update_job = AsyncMock(return_value=SAMPLE_JOB)

        result = await parse_job_description("job-001", SAMPLE_JD)

        assert result is not None
        assert result["level"] is None
        assert result["comp"] is None
        assert result["responsibilities"] == ["Build things"]
        assert result["requirements"] == ["5 years experience"]

    @patch("app.services.jd_parser.complete_json", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_wrong_types_in_llm_response_coerced(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """LLM returns wrong types for list fields → coerced to empty lists."""
        mock_llm.return_value = {
            "responsibilities": "Not a list",
            "requirements": None,
            "level": "Mid",
            "comp": None,
        }
        mock_db.get_job = AsyncMock(return_value=SAMPLE_JOB)
        mock_db.update_job = AsyncMock(return_value=SAMPLE_JOB)

        result = await parse_job_description("job-001", SAMPLE_JD)

        assert result is not None
        assert result["responsibilities"] == []
        assert result["requirements"] == []
        assert result["level"] == "Mid"

    @patch("app.services.jd_parser.complete_json", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_job_not_found_after_create_returns_none(
        self, mock_db: AsyncMock, mock_llm: AsyncMock
    ) -> None:
        """db.get_job returns None after LLM call → returns None, no update."""
        mock_llm.return_value = SAMPLE_PARSED_RESPONSE
        mock_db.get_job = AsyncMock(return_value=None)
        mock_db.update_job = AsyncMock()

        result = await parse_job_description("job-ghost", SAMPLE_JD)

        assert result is None
        mock_db.update_job.assert_not_called()


# ---------------------------------------------------------------------------
# TestBackfillParseJobs — backfill endpoint logic
# ---------------------------------------------------------------------------


class TestBackfillParseJobs:
    """Tests for backfill_parse_jobs() with mocked db and LLM."""

    @patch("app.services.jd_parser.parse_job_description", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_skips_already_parsed_jobs(
        self, mock_db: AsyncMock, mock_parse: AsyncMock
    ) -> None:
        """Jobs with existing 'parsed' key are skipped."""
        already_parsed_job = {
            **SAMPLE_JOB,
            "job_id": "job-already",
            "parsed": {"responsibilities": [], "requirements": [], "level": None, "comp": None},
        }
        mock_db.list_jobs = AsyncMock(return_value=[already_parsed_job])

        summary = await backfill_parse_jobs()

        assert summary["total"] == 1
        assert summary["skipped"] == 1
        assert summary["parsed"] == 0
        assert summary["failed"] == 0
        mock_parse.assert_not_called()

    @patch("app.services.jd_parser.parse_job_description", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_parses_jobs_missing_parsed(
        self, mock_db: AsyncMock, mock_parse: AsyncMock
    ) -> None:
        """Jobs without 'parsed' key are sent to parse_job_description."""
        unparsed_job = {**SAMPLE_JOB, "job_id": "job-unparsed"}
        mock_db.list_jobs = AsyncMock(return_value=[unparsed_job])
        mock_parse.return_value = SAMPLE_PARSED_RESPONSE

        summary = await backfill_parse_jobs()

        assert summary["total"] == 1
        assert summary["skipped"] == 0
        assert summary["parsed"] == 1
        assert summary["failed"] == 0
        mock_parse.assert_called_once_with("job-unparsed", unparsed_job["content"])

    @patch("app.services.jd_parser.parse_job_description", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_counts_failed_parses(
        self, mock_db: AsyncMock, mock_parse: AsyncMock
    ) -> None:
        """parse_job_description returning None is counted as a failure."""
        unparsed_job = {**SAMPLE_JOB, "job_id": "job-fail"}
        mock_db.list_jobs = AsyncMock(return_value=[unparsed_job])
        mock_parse.return_value = None  # parse failure

        summary = await backfill_parse_jobs()

        assert summary["total"] == 1
        assert summary["failed"] == 1
        assert summary["parsed"] == 0

    @patch("app.services.jd_parser.parse_job_description", new_callable=AsyncMock)
    @patch("app.services.jd_parser.db")
    async def test_mixed_skipped_and_parsed(
        self, mock_db: AsyncMock, mock_parse: AsyncMock
    ) -> None:
        """Mix of already-parsed and unparsed jobs processed correctly."""
        jobs = [
            {**SAMPLE_JOB, "job_id": "job-A", "parsed": {"responsibilities": []}},
            {**SAMPLE_JOB, "job_id": "job-B"},  # needs parsing
            {**SAMPLE_JOB, "job_id": "job-C"},  # needs parsing
        ]
        mock_db.list_jobs = AsyncMock(return_value=jobs)
        mock_parse.return_value = SAMPLE_PARSED_RESPONSE

        summary = await backfill_parse_jobs()

        assert summary["total"] == 3
        assert summary["skipped"] == 1
        assert summary["parsed"] == 2
        assert summary["failed"] == 0
        assert mock_parse.call_count == 2

    @patch("app.services.jd_parser.db")
    async def test_empty_jobs_table(self, mock_db: AsyncMock) -> None:
        """Empty jobs table → all counts zero."""
        mock_db.list_jobs = AsyncMock(return_value=[])

        summary = await backfill_parse_jobs()

        assert summary["total"] == 0
        assert summary["skipped"] == 0
        assert summary["parsed"] == 0
        assert summary["failed"] == 0
