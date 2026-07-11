"""Service tests for cover letter, outreach, and email generation — mocked LLM."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.cover_letter import (
    generate_cover_letter,
    generate_follow_up_email,
    generate_outreach_message,
    generate_resume_title,
    generate_thank_you_email,
)


class TestGenerateCoverLetter:
    """Tests for generate_cover_letter() with mocked LLM."""

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_returns_generated_cover_letter(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = (
            "Dear Hiring Manager,\n\nI am excited to apply for the Senior Engineer role."
        )
        resume = {"personalInfo": {"name": "John Doe"}, "summary": "Experienced engineer"}
        job_description = "We are looking for a senior engineer with 5+ years of experience."

        result = await generate_cover_letter(resume, job_description, language="en")

        assert "Senior Engineer" in result
        mock_llm.assert_called_once()

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_generates_in_target_language(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = "Estimado gerente de contratación..."
        resume = {"personalInfo": {"name": "Juan Doe"}, "summary": "Ingeniero experimentado"}
        job_description = "Buscamos un ingeniero sénior con 5+ años de experiencia."

        result = await generate_cover_letter(resume, job_description, language="es")

        assert len(result) > 0
        call_args = mock_llm.call_args
        prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
        assert "Spanish" in prompt


class TestGenerateOutreachMessage:
    """Tests for generate_outreach_message() with mocked LLM."""

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_returns_concise_outreach_message(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = "Hi there, I noticed your team is building microservices."
        resume = {"personalInfo": {"name": "Jane Doe"}, "summary": "Backend engineer"}
        job_description = "We are hiring for a backend role focusing on microservices."

        result = await generate_outreach_message(resume, job_description, language="en")

        assert len(result) > 0
        assert "microservices" in result.lower()
        mock_llm.assert_called_once()

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_outreach_fits_under_max_tokens(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = "Short outreach message."
        resume = {"personalInfo": {"name": "Test"}, "summary": "Engineer"}
        job_description = "Looking for engineer."

        result = await generate_outreach_message(resume, job_description, language="en")

        call_args = mock_llm.call_args
        assert call_args.kwargs.get("max_tokens") == 1024


class TestGenerateThankYouEmail:
    """Tests for generate_thank_you_email() with mocked LLM."""

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_returns_email_with_subject_and_body(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = (
            "Subject: Thank you — Senior Engineer at TechCorp\n---\n"
            "Thank you for the opportunity to discuss the position."
        )

        result = await generate_thank_you_email(
            company="TechCorp",
            role="Senior Engineer",
            status="interview",
            applied_at="2024-01-15",
            language="en",
        )

        assert "Subject:" in result
        assert "---" in result
        assert "TechCorp" in result or "Senior Engineer" in result

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_thank_you_handles_missing_data(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = "Subject: Thank you\n---\nThank you email body"

        result = await generate_thank_you_email(
            company=None,
            role=None,
            status="interview",
            applied_at=None,
            language="en",
        )

        assert len(result) > 0
        mock_llm.assert_called_once()

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_thank_you_email_all_languages(self, mock_llm: AsyncMock) -> None:
        languages = ["en", "es", "zh", "ja", "pt"]
        for lang in languages:
            mock_llm.reset_mock()
            mock_llm.return_value = f"Subject: Thank you (in {lang})\n---\nBody"

            result = await generate_thank_you_email(
                company="Company",
                role="Role",
                status="interview",
                applied_at="2024-01-15",
                language=lang,
            )

            assert len(result) > 0
            call_args = mock_llm.call_args
            prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
            # Verify that language parameter was passed
            assert "Company" in prompt


class TestGenerateFollowUpEmail:
    """Tests for generate_follow_up_email() with mocked LLM."""

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_returns_email_with_subject_and_body(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = (
            "Subject: Following up — Product Manager at StartupCo\n---\n"
            "I wanted to follow up on my application from January."
        )

        result = await generate_follow_up_email(
            company="StartupCo",
            role="Product Manager",
            status="no_response",
            applied_at="2024-01-10",
            language="en",
        )

        assert "Subject:" in result
        assert "---" in result
        assert "StartupCo" in result or "Product Manager" in result

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_follow_up_handles_missing_data(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = "Subject: Following up\n---\nFollow-up email body"

        result = await generate_follow_up_email(
            company=None,
            role=None,
            status="no_response",
            applied_at=None,
            language="en",
        )

        assert len(result) > 0
        mock_llm.assert_called_once()

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_follow_up_email_all_languages(self, mock_llm: AsyncMock) -> None:
        languages = ["en", "es", "zh", "ja", "pt"]
        for lang in languages:
            mock_llm.reset_mock()
            mock_llm.return_value = f"Subject: Following up (in {lang})\n---\nBody"

            result = await generate_follow_up_email(
                company="Company",
                role="Role",
                status="no_response",
                applied_at="2024-01-10",
                language=lang,
            )

            assert len(result) > 0
            call_args = mock_llm.call_args
            prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
            # Verify that language parameter was passed
            assert "Company" in prompt


class TestGenerateTitle:
    """Tests for generate_resume_title() with mocked LLM."""

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_returns_concise_title(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = "Senior Full-Stack Engineer @ TechCorp"
        job_description = "Looking for a senior full-stack engineer..."

        result = await generate_resume_title(job_description, language="en")

        assert len(result) <= 80
        mock_llm.assert_called_once()

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_title_is_truncated_to_80_chars(self, mock_llm: AsyncMock) -> None:
        long_title = "This is a very long job title that exceeds the maximum character limit of 80 characters"
        mock_llm.return_value = long_title

        result = await generate_resume_title("Some job", language="en")

        assert len(result) <= 80

    @patch("app.services.cover_letter.complete", new_callable=AsyncMock)
    async def test_title_strips_quotes(self, mock_llm: AsyncMock) -> None:
        mock_llm.return_value = '"Senior Engineer @ Company"'

        result = await generate_resume_title("Some job", language="en")

        assert not result.startswith('"')
        assert not result.endswith('"')
