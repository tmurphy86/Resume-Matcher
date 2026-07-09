"""Provenance lint service for checking resume content fact coverage."""

from app.schemas.models import ResumeData


def check_provenance(
    resume_data: ResumeData,
    known_fact_ids: set[str],
) -> dict:
    """Check provenance coverage for a resume's blocks.

    Returns a dict with:
    - covered: count of blocks/variants that have at least one valid fact_id
    - uncovered: list of {section, block_id, variant_id, text} for blocks with no fact_ids
                 or legacy bullets with no provenance tracking
    - broken: list of {section, block_id, variant_id, text, fact_ids} for variants
              whose fact_ids reference non-existent facts

    Args:
        resume_data: The structured resume data to check
        known_fact_ids: Set of all fact_ids that exist in the facts table

    Returns:
        Dict with coverage report
    """
    covered_count: int = 0
    uncovered_list: list[dict] = []
    broken_list: list[dict] = []

    # Check summary blocks
    if resume_data.summary_blocks:
        for block in resume_data.summary_blocks:
            # Find the active variant
            active_variant = next(
                (v for v in block.variants if v.id == block.active_variant_id),
                None,
            )
            if active_variant is None:
                continue

            if not active_variant.fact_ids:
                # Uncovered: no fact_ids
                uncovered_list.append(
                    {
                        "section": "summary",
                        "block_id": block.id,
                        "variant_id": active_variant.id,
                        "text": active_variant.text,
                    }
                )
            else:
                # Check if any fact_id doesn't exist
                missing_ids = [fid for fid in active_variant.fact_ids if fid not in known_fact_ids]
                if missing_ids:
                    broken_list.append(
                        {
                            "section": "summary",
                            "block_id": block.id,
                            "variant_id": active_variant.id,
                            "text": active_variant.text,
                            "fact_ids": active_variant.fact_ids,
                        }
                    )
                else:
                    covered_count += 1

    # Check work experience
    for experience in resume_data.workExperience:
        section_name = (
            f"workExperience:{experience.company}:{experience.title}"
            if experience.company or experience.title
            else "workExperience"
        )

        if experience.bullet_blocks:
            # Process blocks
            for block in experience.bullet_blocks:
                # Find the active variant
                active_variant = next(
                    (v for v in block.variants if v.id == block.active_variant_id),
                    None,
                )
                if active_variant is None:
                    continue

                if not active_variant.fact_ids:
                    # Uncovered: no fact_ids
                    uncovered_list.append(
                        {
                            "section": section_name,
                            "block_id": block.id,
                            "variant_id": active_variant.id,
                            "text": active_variant.text,
                        }
                    )
                else:
                    # Check if any fact_id doesn't exist
                    missing_ids = [fid for fid in active_variant.fact_ids if fid not in known_fact_ids]
                    if missing_ids:
                        broken_list.append(
                            {
                                "section": section_name,
                                "block_id": block.id,
                                "variant_id": active_variant.id,
                                "text": active_variant.text,
                                "fact_ids": active_variant.fact_ids,
                            }
                        )
                    else:
                        covered_count += 1
        elif experience.description:
            # Legacy bullets: no provenance tracking possible
            for bullet_text in experience.description:
                uncovered_list.append(
                    {
                        "section": section_name,
                        "block_id": None,
                        "variant_id": None,
                        "text": bullet_text,
                    }
                )

    return {
        "covered": covered_count,
        "uncovered": uncovered_list,
        "broken": broken_list,
    }
