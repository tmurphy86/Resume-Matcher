"""Service tests for generate_multi_jd_diffs — mocked LLM."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.improver import generate_multi_jd_diffs
from app.schemas.models import ImproveDiffResult


def _make_llm_result(**kwargs: object) -> dict:
    base: dict = {
        "changes": [],
        "strategy_notes": "test strategy",
    }
    base.update(kwargs)
    return base


@pytest.mark.asyncio
class TestGenerateMultiJdDiffs:

    @patch("app.services.improver.complete_json", new_callable=AsyncMock)
    async def test_multi_jd_aggregates_requirements(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = _make_llm_result()
        common_line = "Experience with Python required"
        jds = [
            f"Job A\n{common_line}\nSome unique line A",
            f"Job B\n{common_line}\nSome unique line B",
            f"Job C\n{common_line}\nSome unique line C",
        ]
        await generate_multi_jd_diffs(
            original_resume="My resume",
            original_resume_data=None,
            archetype_name="Backend Engineer",
            job_descriptions=jds,
            language="en",
        )
        call_args = mock_llm.call_args
        prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
        assert "[3 occurrences] " + common_line in prompt

    @patch("app.services.improver.complete_json", new_callable=AsyncMock)
    async def test_multi_jd_calls_complete_json(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = _make_llm_result(
            changes=[
                {
                    "path": "summary",
                    "action": "replace",
                    "original": "old summary",
                    "value": "new summary",
                    "reason": "better match",
                    "fact_ids": [],
                }
            ]
        )
        await generate_multi_jd_diffs(
            original_resume="My resume",
            original_resume_data=None,
            archetype_name="Backend Engineer",
            job_descriptions=["JD one"],
            language="en",
        )
        mock_llm.assert_called_once()

    @patch("app.services.improver.complete_json", new_callable=AsyncMock)
    async def test_multi_jd_returns_diff_result(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = _make_llm_result(
            changes=[
                {
                    "path": "summary",
                    "action": "replace",
                    "original": "old",
                    "value": "new",
                    "reason": "test",
                    "fact_ids": [],
                }
            ]
        )
        result = await generate_multi_jd_diffs(
            original_resume="My resume",
            original_resume_data=None,
            archetype_name="Backend Engineer",
            job_descriptions=["JD one"],
            language="en",
        )
        assert isinstance(result, ImproveDiffResult)
        assert len(result.changes) == 1

    @patch("app.services.improver.complete_json", new_callable=AsyncMock)
    async def test_multi_jd_handles_single_jd(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = _make_llm_result()
        result = await generate_multi_jd_diffs(
            original_resume="My resume",
            original_resume_data=None,
            archetype_name="Backend Engineer",
            job_descriptions=["Only one JD here\nPython required"],
            language="en",
        )
        assert isinstance(result, ImproveDiffResult)
        call_args = mock_llm.call_args
        prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
        assert "Number of JDs: 1" in prompt

    @patch("app.services.improver.complete_json", new_callable=AsyncMock)
    async def test_multi_jd_propagates_language(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = _make_llm_result()
        await generate_multi_jd_diffs(
            original_resume="My resume",
            original_resume_data=None,
            archetype_name="Backend Engineer",
            job_descriptions=["JD text here"],
            language="es",
        )
        call_args = mock_llm.call_args
        prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
        assert "Spanish" in prompt
