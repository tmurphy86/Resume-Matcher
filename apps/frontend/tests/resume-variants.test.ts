/**
 * Unit tests for addVariantToResumeData / switchBlockVariant (RH-301).
 *
 * Pure function tests — no React rendering, no network calls.
 * Each test must fail if the target logic regresses.
 */

import { describe, expect, it } from 'vitest';
import { addVariantToResumeData, switchBlockVariant } from '@/lib/utils/resume-variants';
import type { ProcessedResume, BlockVariant } from '@/lib/api/resume';

// ─── Fixtures ─────────────────────────────────────────────────────

const existingVariant: BlockVariant = {
  id: 'v-existing',
  text: 'Led a team of five engineers to ship on time',
  tags: ['original'],
  fact_ids: ['f-1'],
};

const baseResume: ProcessedResume = {
  personalInfo: { name: 'Jane Doe' },
  summary: 'Experienced engineer',
  summary_blocks: [
    {
      id: 'sb-1',
      active_variant_id: 'v-existing',
      variants: [existingVariant],
    },
  ],
  workExperience: [
    {
      id: 1,
      title: 'Senior Engineer',
      company: 'Acme',
      bullet_blocks: [
        {
          id: 'bb-0',
          active_variant_id: 'v-existing',
          variants: [existingVariant],
        },
        {
          id: 'bb-1',
          active_variant_id: 'v-existing',
          variants: [existingVariant],
        },
      ],
    },
    {
      id: 2,
      title: 'Engineer',
      company: 'Initech',
      bullet_blocks: [],
    },
  ],
};

const newVariant: BlockVariant = {
  id: 'v-new',
  text: 'Guided a cross-functional team of 5 to deliver ahead of schedule',
  tags: ['targeted'],
  fact_ids: ['f-2'],
};

// ─── addVariantToResumeData ────────────────────────────────────────

describe('addVariantToResumeData — description field', () => {
  it('happy path: appends variant to workExperience[0].bullet_blocks[0]', () => {
    const result = addVariantToResumeData(
      baseResume,
      'description',
      'workExperience[0].description[0]',
      newVariant,
      'new-block-id'
    );

    const block = result.workExperience![0].bullet_blocks![0];
    expect(block.variants).toHaveLength(2);
    expect(block.variants[1]).toEqual(newVariant);
    // active_variant_id is not changed by addVariantToResumeData
    expect(block.active_variant_id).toBe('v-existing');
  });

  it('appends to a different bullet index: workExperience[0].description[1]', () => {
    const result = addVariantToResumeData(
      baseResume,
      'description',
      'workExperience[0].description[1]',
      newVariant,
      'new-block-id'
    );

    const block0 = result.workExperience![0].bullet_blocks![0];
    const block1 = result.workExperience![0].bullet_blocks![1];
    // block[0] untouched
    expect(block0.variants).toHaveLength(1);
    // block[1] has the new variant appended
    expect(block1.variants).toHaveLength(2);
    expect(block1.variants[1]).toEqual(newVariant);
  });

  it('dedup guard: same variant id is not appended twice', () => {
    // Attempt to add existingVariant (id='v-existing') to a block that already has it
    const result = addVariantToResumeData(
      baseResume,
      'description',
      'workExperience[0].description[0]',
      existingVariant, // same id as the one already in the block
      'would-not-be-used'
    );

    const block = result.workExperience![0].bullet_blocks![0];
    expect(block.variants).toHaveLength(1); // still 1 — dedup guard fired
  });

  it('does not mutate the original data', () => {
    const originalVariantCount = baseResume.workExperience![0].bullet_blocks![0].variants.length;
    addVariantToResumeData(
      baseResume,
      'description',
      'workExperience[0].description[0]',
      newVariant,
      'new-block-id'
    );
    expect(baseResume.workExperience![0].bullet_blocks![0].variants).toHaveLength(
      originalVariantCount
    );
  });
});

describe('addVariantToResumeData — summary field', () => {
  it('happy path: appends variant to summary_blocks[0]', () => {
    const result = addVariantToResumeData(
      baseResume,
      'summary',
      'summary',
      newVariant,
      'new-block-id'
    );

    const block = result.summary_blocks![0];
    expect(block.variants).toHaveLength(2);
    expect(block.variants[1]).toEqual(newVariant);
  });

  it('dedup guard: same summary variant is not appended twice', () => {
    const result = addVariantToResumeData(
      baseResume,
      'summary',
      'summary',
      existingVariant,
      'would-not-be-used'
    );

    expect(result.summary_blocks![0].variants).toHaveLength(1);
  });

  it('creates summary_blocks[0] when none exist', () => {
    const resumeWithoutSummaryBlocks: ProcessedResume = {
      ...baseResume,
      summary_blocks: [],
    };

    const result = addVariantToResumeData(
      resumeWithoutSummaryBlocks,
      'summary',
      'summary',
      newVariant,
      'block-created'
    );

    expect(result.summary_blocks).toHaveLength(1);
    expect(result.summary_blocks![0].id).toBe('block-created');
    expect(result.summary_blocks![0].variants[0]).toEqual(newVariant);
  });
});

describe('addVariantToResumeData — unknown field type', () => {
  it('returns a copy of the data unchanged for an unsupported field_type', () => {
    const result = addVariantToResumeData(
      baseResume,
      'skill', // not 'summary' or 'description'
      'additional.technicalSkills',
      newVariant,
      'new-block-id'
    );

    // workExperience and summary_blocks should be structurally identical
    expect(result.workExperience![0].bullet_blocks![0].variants).toHaveLength(1);
    expect(result.summary_blocks![0].variants).toHaveLength(1);
  });
});

// ─── switchBlockVariant ────────────────────────────────────────────

describe('switchBlockVariant', () => {
  it('switches active_variant_id on the matching summary block', () => {
    const result = switchBlockVariant(baseResume, 'sb-1', 'v-new');
    expect(result.summary_blocks![0].active_variant_id).toBe('v-new');
  });

  it('switches active_variant_id on the matching bullet block', () => {
    const result = switchBlockVariant(baseResume, 'bb-0', 'v-new');
    expect(result.workExperience![0].bullet_blocks![0].active_variant_id).toBe('v-new');
    // Other block is unchanged
    expect(result.workExperience![0].bullet_blocks![1].active_variant_id).toBe('v-existing');
  });

  it('does not mutate the original data', () => {
    switchBlockVariant(baseResume, 'sb-1', 'v-new');
    expect(baseResume.summary_blocks![0].active_variant_id).toBe('v-existing');
  });
});
