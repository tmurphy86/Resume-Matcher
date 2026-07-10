/**
 * Pure helper functions for block-variant management (ADR-002).
 *
 * Extracted from app/(default)/tailor/page.tsx so they can be unit-tested
 * without rendering the full page (RH-301).
 */

import type { ProcessedResume, BlockVariant, BulletBlock } from '@/lib/api/resume';

/**
 * Returns a deep copy of `data` with the `active_variant_id` of the specified
 * block updated.  Searches both `summary_blocks` and `workExperience[*].bullet_blocks`.
 */
export function switchBlockVariant(
  data: ProcessedResume,
  blockId: string,
  variantId: string
): ProcessedResume {
  const updated: ProcessedResume = {
    ...data,
    summary_blocks: data.summary_blocks?.map((b) =>
      b.id === blockId ? { ...b, active_variant_id: variantId } : b
    ),
    workExperience: data.workExperience?.map((exp) => ({
      ...exp,
      bullet_blocks: exp.bullet_blocks?.map((b) =>
        b.id === blockId ? { ...b, active_variant_id: variantId } : b
      ),
    })),
  };
  return updated;
}

/**
 * Returns a deep copy of `data` with a new `BlockVariant` inserted into the
 * appropriate block.  For summary changes, targets `summary_blocks[0]`.  For
 * description changes, parses the field_path pattern
 * `workExperience[N].description[M]` and targets `workExperience[N].bullet_blocks[M]`.
 * If no matching block exists, a new one is created.
 *
 * Dedup guard: if a variant with the same `id` already exists in the target block,
 * it is not appended again.
 */
export function addVariantToResumeData(
  data: ProcessedResume,
  fieldType: string,
  fieldPath: string,
  variant: BlockVariant,
  newBlockId: string
): ProcessedResume {
  const updated: ProcessedResume = {
    ...data,
    summary_blocks: data.summary_blocks ? [...data.summary_blocks] : [],
    workExperience: data.workExperience ? data.workExperience.map((e) => ({ ...e })) : [],
  };

  if (fieldType === 'summary') {
    const blocks = updated.summary_blocks!;
    if (blocks.length === 0) {
      blocks.push({ id: newBlockId, active_variant_id: variant.id, variants: [variant] });
    } else {
      const block = { ...blocks[0], variants: [...blocks[0].variants] };
      if (!block.variants.some((v) => v.id === variant.id)) {
        block.variants.push(variant);
      }
      blocks[0] = block;
    }
    return updated;
  }

  if (fieldType === 'description') {
    const match = fieldPath.match(/workExperience\[(\d+)\](?:\.description\[(\d+)\])?/);
    if (match && updated.workExperience) {
      const expIdx = parseInt(match[1], 10);
      const descIdx = match[2] !== undefined ? parseInt(match[2], 10) : 0;
      const exp = updated.workExperience[expIdx];
      if (exp) {
        const blocks: BulletBlock[] = exp.bullet_blocks ? [...exp.bullet_blocks] : [];
        const existingBlock = blocks[descIdx];
        if (existingBlock) {
          const block: BulletBlock = { ...existingBlock, variants: [...existingBlock.variants] };
          if (!block.variants.some((v) => v.id === variant.id)) {
            block.variants.push(variant);
          }
          blocks[descIdx] = block;
        } else {
          blocks.push({ id: newBlockId, active_variant_id: variant.id, variants: [variant] });
        }
        updated.workExperience[expIdx] = { ...exp, bullet_blocks: blocks };
      }
    }
    return updated;
  }

  return updated;
}
