"""Unit tests for provenance lint service."""

from app.schemas.models import (
    ResumeData,
    Experience,
    BulletBlock,
    BlockVariant,
)
from app.services.provenance import check_provenance


KNOWN_IDS = {"fact-1", "fact-2"}


class TestCoveredState:
    """Tests for covered (provenance-linked) blocks."""

    def test_block_with_known_fact_ids_is_covered(self) -> None:
        """Active variant with fact_ids that exist should be marked covered."""
        experience = Experience(
            title="Engineer",
            company="Acme",
            location=None,
            years="",
            description=[],
            bullet_blocks=[
                BulletBlock(
                    id="bb-1",
                    active_variant_id="v-1",
                    variants=[BlockVariant(id="v-1", text="Did X", fact_ids=["fact-1"])],
                )
            ],
        )
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[experience],
            education=[],
            personalProjects=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 1
        assert result["uncovered"] == []
        assert result["broken"] == []

    def test_summary_blocks_with_known_fact_ids_are_covered(self) -> None:
        """Summary blocks with valid fact_ids should be marked covered."""
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[],
            education=[],
            skills=[],
            personalProjects=[],
            certifications=[],
            summary_blocks=[
                BulletBlock(
                    id="sb-1",
                    active_variant_id="v-1",
                    variants=[
                        BlockVariant(id="v-1", text="Summary text", fact_ids=["fact-1", "fact-2"])
                    ],
                )
            ],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 1
        assert result["uncovered"] == []
        assert result["broken"] == []


class TestUncoveredState:
    """Tests for uncovered (no provenance) blocks."""

    def test_block_with_empty_fact_ids_is_uncovered(self) -> None:
        """Active variant with empty fact_ids should be marked uncovered."""
        experience = Experience(
            title="Engineer",
            company="Acme",
            location=None,
            years="",
            description=[],
            bullet_blocks=[
                BulletBlock(
                    id="bb-1",
                    active_variant_id="v-1",
                    variants=[BlockVariant(id="v-1", text="Did X", fact_ids=[])],
                )
            ],
        )
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[experience],
            education=[],
            personalProjects=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 0
        assert len(result["uncovered"]) == 1
        uncovered = result["uncovered"][0]
        assert uncovered["section"] == "workExperience:Acme:Engineer"
        assert uncovered["block_id"] == "bb-1"
        assert uncovered["variant_id"] == "v-1"
        assert uncovered["text"] == "Did X"
        assert result["broken"] == []

    def test_legacy_bullet_is_uncovered(self) -> None:
        """Legacy bullets (description items, no blocks) should be marked uncovered."""
        experience = Experience(
            title="Engineer",
            company="Acme",
            location=None,
            years="",
            description=["bullet 1", "bullet 2"],
            bullet_blocks=[],
        )
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[experience],
            education=[],
            personalProjects=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 0
        assert len(result["uncovered"]) == 2
        assert result["broken"] == []

        # Check first uncovered entry
        uncovered_1 = result["uncovered"][0]
        assert uncovered_1["section"] == "workExperience:Acme:Engineer"
        assert uncovered_1["block_id"] is None
        assert uncovered_1["variant_id"] is None
        assert uncovered_1["text"] == "bullet 1"

        # Check second uncovered entry
        uncovered_2 = result["uncovered"][1]
        assert uncovered_2["text"] == "bullet 2"

    def test_summary_block_with_empty_fact_ids_is_uncovered(self) -> None:
        """Summary blocks with empty fact_ids should be marked uncovered."""
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[],
            education=[],
            skills=[],
            personalProjects=[],
            certifications=[],
            summary_blocks=[
                BulletBlock(
                    id="sb-1",
                    active_variant_id="v-1",
                    variants=[BlockVariant(id="v-1", text="Summary text", fact_ids=[])],
                )
            ],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 0
        assert len(result["uncovered"]) == 1
        uncovered = result["uncovered"][0]
        assert uncovered["section"] == "summary"
        assert uncovered["block_id"] == "sb-1"
        assert uncovered["variant_id"] == "v-1"
        assert result["broken"] == []


class TestBrokenState:
    """Tests for broken (references to non-existent facts) blocks."""

    def test_block_with_unknown_fact_ids_is_broken(self) -> None:
        """Active variant with non-existent fact_ids should be marked broken."""
        experience = Experience(
            title="Engineer",
            company="Acme",
            location=None,
            years="",
            description=[],
            bullet_blocks=[
                BulletBlock(
                    id="bb-1",
                    active_variant_id="v-1",
                    variants=[
                        BlockVariant(id="v-1", text="Did X", fact_ids=["nonexistent-fact"])
                    ],
                )
            ],
        )
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[experience],
            education=[],
            personalProjects=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 0
        assert result["uncovered"] == []
        assert len(result["broken"]) == 1

        broken = result["broken"][0]
        assert broken["section"] == "workExperience:Acme:Engineer"
        assert broken["block_id"] == "bb-1"
        assert broken["variant_id"] == "v-1"
        assert broken["text"] == "Did X"
        assert broken["fact_ids"] == ["nonexistent-fact"]

    def test_block_with_partially_unknown_fact_ids_is_broken(self) -> None:
        """Active variant with some unknown fact_ids should be marked broken."""
        experience = Experience(
            title="Engineer",
            company="Acme",
            location=None,
            years="",
            description=[],
            bullet_blocks=[
                BulletBlock(
                    id="bb-1",
                    active_variant_id="v-1",
                    variants=[
                        BlockVariant(
                            id="v-1",
                            text="Did X",
                            fact_ids=["fact-1", "nonexistent-fact"],
                        )
                    ],
                )
            ],
        )
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[experience],
            education=[],
            personalProjects=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 0
        assert result["uncovered"] == []
        assert len(result["broken"]) == 1

    def test_summary_block_with_unknown_fact_ids_is_broken(self) -> None:
        """Summary blocks with non-existent fact_ids should be marked broken."""
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[],
            education=[],
            skills=[],
            personalProjects=[],
            certifications=[],
            summary_blocks=[
                BulletBlock(
                    id="sb-1",
                    active_variant_id="v-1",
                    variants=[
                        BlockVariant(id="v-1", text="Summary text", fact_ids=["bad-id"])
                    ],
                )
            ],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 0
        assert result["uncovered"] == []
        assert len(result["broken"]) == 1

        broken = result["broken"][0]
        assert broken["section"] == "summary"


class TestMixedState:
    """Tests for mixed covered/uncovered/broken scenarios."""

    def test_mixed_blocks(self) -> None:
        """Multiple experiences with mixed provenance states."""
        experience_1 = Experience(
            title="Engineer",
            company="Acme",
            location=None,
            years="",
            description=[],
            bullet_blocks=[
                BulletBlock(
                    id="bb-1",
                    active_variant_id="v-1",
                    variants=[BlockVariant(id="v-1", text="Did X", fact_ids=["fact-1"])],
                ),
                BulletBlock(
                    id="bb-2",
                    active_variant_id="v-2",
                    variants=[BlockVariant(id="v-2", text="Did Y", fact_ids=[])],
                ),
            ],
        )

        experience_2 = Experience(
            title="Developer",
            company="Beta",
            location=None,
            years="",
            description=[],
            bullet_blocks=[
                BulletBlock(
                    id="bb-3",
                    active_variant_id="v-3",
                    variants=[
                        BlockVariant(id="v-3", text="Did Z", fact_ids=["bad-id"])
                    ],
                )
            ],
        )

        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[experience_1, experience_2],
            education=[],
            skills=[],
            personalProjects=[],
            certifications=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 1
        assert len(result["uncovered"]) == 1
        assert len(result["broken"]) == 1


class TestEmptyResume:
    """Tests for empty resumes with no blocks."""

    def test_empty_resume_has_zero_coverage(self) -> None:
        """Empty resume should have zero covered blocks."""
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[],
            education=[],
            skills=[],
            personalProjects=[],
            certifications=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 0
        assert result["uncovered"] == []
        assert result["broken"] == []

    def test_experience_without_blocks_and_description_is_skipped(self) -> None:
        """Experience with no blocks and no description should not appear in report."""
        experience = Experience(
            title="Engineer",
            company="Acme",
            location=None,
            years="",
            description=[],
            bullet_blocks=[],
        )
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[experience],
            education=[],
            personalProjects=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert result["covered"] == 0
        assert result["uncovered"] == []
        assert result["broken"] == []


class TestSectionNames:
    """Tests for correct section naming."""

    def test_section_name_includes_company_and_title(self) -> None:
        """Section name should include company and title."""
        experience = Experience(
            title="Lead Engineer",
            company="Google",
            location=None,
            years="",
            description=["bullet"],
            bullet_blocks=[],
        )
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[experience],
            education=[],
            personalProjects=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert len(result["uncovered"]) == 1
        assert result["uncovered"][0]["section"] == "workExperience:Google:Lead Engineer"

    def test_section_name_fallback_for_empty_company_and_title(self) -> None:
        """Section name should fallback to generic name if company/title are empty."""
        experience = Experience(
            title="",
            company="",
            location=None,
            years="",
            description=["bullet"],
            bullet_blocks=[],
        )
        resume_data = ResumeData(
            personalInfo={"name": "Test"},
            summary="",
            workExperience=[experience],
            education=[],
            personalProjects=[],
        )

        result = check_provenance(resume_data, KNOWN_IDS)

        assert len(result["uncovered"]) == 1
        assert result["uncovered"][0]["section"] == "workExperience"
