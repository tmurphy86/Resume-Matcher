"""Unit tests for the variant/block layer added in RH-103.

Covers:
- Legacy payloads (no bullet_blocks / summary_blocks) validate unchanged.
- BulletBlock payloads round-trip through model_dump + re-parse.
- Active-variant switching re-derives description / summary.
- fact_ids provenance survives round-trip.
"""

import pytest

from app.schemas.models import (
    BlockVariant,
    BulletBlock,
    Experience,
    ResumeData,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_block(
    block_id: str,
    active: str,
    *,
    variant_a_text: str = "Variant A text",
    variant_b_text: str = "Variant B text",
) -> dict:
    """Return a raw dict representing a BulletBlock with two variants."""
    return {
        "id": block_id,
        "active_variant_id": active,
        "variants": [
            {"id": "va", "text": variant_a_text, "tags": ["exec"], "fact_ids": []},
            {"id": "vb", "text": variant_b_text, "tags": ["fsi"], "fact_ids": []},
        ],
    }


# ---------------------------------------------------------------------------
# 1. Legacy payload validates unchanged
# ---------------------------------------------------------------------------

class TestLegacyPayload:
    def test_experience_without_bullet_blocks(self) -> None:
        """An Experience dict with no bullet_blocks key must parse unchanged."""
        raw: dict = {
            "id": 1,
            "title": "Engineer",
            "company": "Acme",
            "years": "2020-2023",
            "description": ["Built things", "Shipped features"],
        }
        exp = Experience.model_validate(raw)
        assert exp.description == ["Built things", "Shipped features"]
        assert exp.bullet_blocks == []

    def test_resume_data_without_summary_blocks(self) -> None:
        """A ResumeData dict with no summary_blocks key must parse unchanged."""
        raw: dict = {"summary": "I am a software engineer."}
        rd = ResumeData.model_validate(raw)
        assert rd.summary == "I am a software engineer."
        assert rd.summary_blocks == []

    def test_experience_description_not_overridden_when_blocks_empty(self) -> None:
        """description must stay as-is when bullet_blocks is explicitly empty."""
        exp = Experience.model_validate(
            {
                "description": ["Line one", "Line two"],
                "bullet_blocks": [],
            }
        )
        assert exp.description == ["Line one", "Line two"]


# ---------------------------------------------------------------------------
# 2. Blocks payload round-trips
# ---------------------------------------------------------------------------

class TestBlockRoundTrip:
    def test_experience_with_two_blocks_round_trips(self) -> None:
        """Experience with two BulletBlocks must survive model_dump + re-parse."""
        raw: dict = {
            "id": 7,
            "title": "Lead Dev",
            "company": "Corp",
            "years": "2021-2024",
            "description": [],
            "bullet_blocks": [
                _make_block("blk1", "va", variant_a_text="Led team", variant_b_text="Managed team"),
                _make_block("blk2", "vb", variant_a_text="Built API", variant_b_text="Scaled API"),
            ],
        }
        exp1 = Experience.model_validate(raw)
        dumped = exp1.model_dump()
        exp2 = Experience.model_validate(dumped)
        assert exp2.bullet_blocks == exp1.bullet_blocks
        assert exp2.description == exp1.description

    def test_block_variant_fields_preserved(self) -> None:
        """All BlockVariant fields survive a round-trip."""
        bv = BlockVariant(id="v1", text="Hello", tags=["a", "b"], fact_ids=["f1"])
        restored = BlockVariant.model_validate(bv.model_dump())
        assert restored == bv


# ---------------------------------------------------------------------------
# 3. Active-variant switch changes derived description
# ---------------------------------------------------------------------------

class TestActiveVariantSwitch:
    def _build_exp(self, active: str) -> Experience:
        raw: dict = {
            "bullet_blocks": [
                _make_block(
                    "blk1",
                    active,
                    variant_a_text="Drove revenue growth by 30%",
                    variant_b_text="Increased sales across FSI verticals",
                ),
            ],
        }
        return Experience.model_validate(raw)

    def test_active_vb_yields_vb_text(self) -> None:
        exp = self._build_exp("vb")
        assert exp.description == ["Increased sales across FSI verticals"]

    def test_active_va_yields_va_text(self) -> None:
        exp = self._build_exp("va")
        assert exp.description == ["Drove revenue growth by 30%"]

    def test_switching_active_id_changes_description(self) -> None:
        """Re-parsing with a different active_variant_id must change description."""
        exp_a = self._build_exp("va")
        exp_b = self._build_exp("vb")
        assert exp_a.description != exp_b.description
        assert exp_a.description == ["Drove revenue growth by 30%"]
        assert exp_b.description == ["Increased sales across FSI verticals"]

    def test_missing_active_variant_skips_block(self) -> None:
        """If active_variant_id doesn't match any variant, the block is skipped."""
        raw: dict = {
            "bullet_blocks": [
                {
                    "id": "blk1",
                    "active_variant_id": "nonexistent",
                    "variants": [
                        {"id": "va", "text": "Some text", "tags": [], "fact_ids": []},
                    ],
                }
            ],
        }
        exp = Experience.model_validate(raw)
        assert exp.description == []

    def test_multiple_blocks_build_description_list(self) -> None:
        """Each block contributes one line to description (active variant only)."""
        raw: dict = {
            "bullet_blocks": [
                _make_block("b1", "va", variant_a_text="Line one A", variant_b_text="Line one B"),
                _make_block("b2", "vb", variant_a_text="Line two A", variant_b_text="Line two B"),
                _make_block("b3", "va", variant_a_text="Line three A", variant_b_text="Line three B"),
            ],
        }
        exp = Experience.model_validate(raw)
        assert exp.description == ["Line one A", "Line two B", "Line three A"]


# ---------------------------------------------------------------------------
# 4. ResumeData with summary_blocks non-empty
# ---------------------------------------------------------------------------

class TestSummaryBlocks:
    def test_single_summary_block_derives_summary(self) -> None:
        """When one summary block is present, summary reflects its active variant."""
        rd = ResumeData.model_validate(
            {
                "summary": "Old summary",
                "summary_blocks": [
                    {
                        "id": "sb1",
                        "active_variant_id": "sv_exec",
                        "variants": [
                            {
                                "id": "sv_exec",
                                "text": "Seasoned executive with P&L ownership.",
                                "tags": ["executive"],
                                "fact_ids": ["fact-001"],
                            },
                            {
                                "id": "sv_ic",
                                "text": "Staff engineer with distributed systems focus.",
                                "tags": ["ic"],
                                "fact_ids": ["fact-002"],
                            },
                        ],
                    }
                ],
            }
        )
        assert rd.summary == "Seasoned executive with P&L ownership."

    def test_summary_block_variant_switch(self) -> None:
        """Changing active_variant_id must change the derived summary."""
        def _make_rd(active: str) -> ResumeData:
            return ResumeData.model_validate(
                {
                    "summary_blocks": [
                        {
                            "id": "sb1",
                            "active_variant_id": active,
                            "variants": [
                                {"id": "sv1", "text": "Summary for FSI.", "tags": [], "fact_ids": []},
                                {"id": "sv2", "text": "Summary for Tech.", "tags": [], "fact_ids": []},
                            ],
                        }
                    ]
                }
            )

        rd1 = _make_rd("sv1")
        rd2 = _make_rd("sv2")
        assert rd1.summary == "Summary for FSI."
        assert rd2.summary == "Summary for Tech."

    def test_multiple_summary_blocks_joined(self) -> None:
        """Multiple summary blocks are joined with a blank line."""
        rd = ResumeData.model_validate(
            {
                "summary_blocks": [
                    {
                        "id": "sb1",
                        "active_variant_id": "v1",
                        "variants": [{"id": "v1", "text": "Part one.", "tags": [], "fact_ids": []}],
                    },
                    {
                        "id": "sb2",
                        "active_variant_id": "v2",
                        "variants": [{"id": "v2", "text": "Part two.", "tags": [], "fact_ids": []}],
                    },
                ]
            }
        )
        assert rd.summary == "Part one.\n\nPart two."

    def test_empty_summary_blocks_leaves_summary_unchanged(self) -> None:
        """summary_blocks=[] must leave summary exactly as provided."""
        rd = ResumeData.model_validate(
            {"summary": "Unchanged summary.", "summary_blocks": []}
        )
        assert rd.summary == "Unchanged summary."


# ---------------------------------------------------------------------------
# 5. BlockVariant with fact_ids round-trip
# ---------------------------------------------------------------------------

class TestFactIdsProvenance:
    def test_fact_ids_survive_round_trip(self) -> None:
        """fact_ids must be preserved exactly through model_dump + re-parse."""
        bv = BlockVariant(
            id="v-provenance",
            text="Led cross-functional team of 12.",
            tags=["leadership"],
            fact_ids=["fact-101", "fact-202", "fact-303"],
        )
        restored = BlockVariant.model_validate(bv.model_dump())
        assert restored.fact_ids == ["fact-101", "fact-202", "fact-303"]

    def test_fact_ids_default_to_empty_list(self) -> None:
        """fact_ids defaults to [] so old block data without the key validates."""
        bv = BlockVariant.model_validate({"id": "v1", "text": "Something."})
        assert bv.fact_ids == []

    def test_fact_ids_in_experience_via_bullet_blocks(self) -> None:
        """fact_ids on BlockVariants inside Experience survive a full round-trip."""
        raw: dict = {
            "bullet_blocks": [
                {
                    "id": "blk1",
                    "active_variant_id": "va",
                    "variants": [
                        {
                            "id": "va",
                            "text": "Delivered project on time.",
                            "tags": [],
                            "fact_ids": ["f-42", "f-99"],
                        }
                    ],
                }
            ]
        }
        exp = Experience.model_validate(raw)
        dumped = exp.model_dump()
        exp2 = Experience.model_validate(dumped)
        assert exp2.bullet_blocks[0].variants[0].fact_ids == ["f-42", "f-99"]
