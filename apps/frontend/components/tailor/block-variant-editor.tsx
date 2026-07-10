'use client';

import { useState } from 'react';
import { Check, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import type { BulletBlock } from '@/components/dashboard/resume-component';
import { useTranslations } from '@/lib/i18n';

// ─────────────────────────────────────────────
// Public types
// ─────────────────────────────────────────────

export interface BlockSection {
  /** Stable key, e.g. "summary" or "exp-0" */
  id: string;
  /** Human-readable label, e.g. "Software Engineer at Acme" */
  label: string;
  blocks: BulletBlock[];
  /** Called when the user switches the active variant. Must PATCH the backend. */
  onSwitchVariant: (blockId: string, variantId: string) => Promise<void>;
}

interface BlockVariantEditorProps {
  sections: BlockSection[];
}

// ─────────────────────────────────────────────
// BlockVariantEditor
// ─────────────────────────────────────────────

/**
 * Renders a collapsible panel showing all bullet/summary blocks that carry
 * saved variants.  Each variant is displayed as a chip; clicking a non-active
 * chip switches the active variant and persists the change via PATCH.
 *
 * Blocks-less legacy sections are handled by the caller — if `sections` is
 * empty this component returns null (graceful degradation).
 */
export function BlockVariantEditor({ sections }: BlockVariantEditorProps) {
  const { t } = useTranslations();
  const [isExpanded, setIsExpanded] = useState(true);

  if (sections.length === 0) return null;

  return (
    <div className="border border-black shadow-sw-sm bg-white">
      {/* ── Header ─────────────────────────────────────── */}
      <button
        onClick={() => setIsExpanded((v) => !v)}
        className="w-full flex items-center justify-between p-3 hover:bg-paper-tint transition-colors"
        aria-expanded={isExpanded}
        aria-controls="bve-body"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 shrink-0" />
          ) : (
            <ChevronRight className="w-4 h-4 shrink-0" />
          )}
          <h3 className="font-serif text-sm font-bold uppercase tracking-tight">
            {t('tailor.variants.title')}
          </h3>
        </div>
        <span className="font-mono text-xs text-ink-soft">
          {t('tailor.variants.sections', { count: String(sections.length) })}
        </span>
      </button>

      {/* ── Body ───────────────────────────────────────── */}
      {isExpanded && (
        <div id="bve-body" className="border-t border-black divide-y divide-black">
          {sections.map((section) => (
            <SectionRow key={section.id} section={section} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// SectionRow
// ─────────────────────────────────────────────

function SectionRow({ section }: { section: BlockSection }) {
  const { t } = useTranslations();
  /** blockId-variantId that is currently being switched */
  const [switching, setSwitching] = useState<string | null>(null);

  const handleSwitch = async (blockId: string, variantId: string) => {
    const key = `${blockId}-${variantId}`;
    setSwitching(key);
    try {
      await section.onSwitchVariant(blockId, variantId);
    } finally {
      setSwitching(null);
    }
  };

  return (
    <div className="p-3">
      <p className="font-mono text-xs font-bold uppercase tracking-wider text-ink-soft mb-2">
        {section.label}
      </p>
      <div className="space-y-2">
        {section.blocks.map((block) => {
          const activeVariant = block.variants.find((v) => v.id === block.active_variant_id);
          const isSwitchingBlock = switching !== null && switching.startsWith(`${block.id}-`);

          return (
            <div key={block.id} className="border border-black p-2 bg-paper-tint">
              {/* Active text preview */}
              <p className="font-mono text-xs text-ink mb-2 line-clamp-2">
                {activeVariant?.text ?? '—'}
              </p>

              {/* Variant chips */}
              <div
                className="flex flex-wrap gap-1"
                role="group"
                aria-label={t('tailor.variants.title')}
              >
                {block.variants.map((variant, idx) => {
                  const isActive = variant.id === block.active_variant_id;
                  const isSwitchingThis = switching === `${block.id}-${variant.id}`;
                  const chipLabel =
                    variant.tags.length > 0 ? variant.tags.join(' · ') : `v${idx + 1}`;

                  return (
                    <button
                      key={variant.id}
                      onClick={() => !isActive && handleSwitch(block.id, variant.id)}
                      disabled={isActive || isSwitchingBlock}
                      aria-pressed={isActive}
                      aria-label={
                        isActive
                          ? `${t('tailor.variants.active')}: ${chipLabel}`
                          : t('tailor.variants.switchTo', { tags: chipLabel })
                      }
                      className={[
                        'font-mono text-xs px-2 py-0.5 border flex items-center gap-1 transition-colors',
                        isActive
                          ? 'border-black bg-black text-white cursor-default'
                          : isSwitchingBlock
                            ? 'border-black bg-white text-ink-soft cursor-not-allowed'
                            : 'border-black bg-white text-ink hover:bg-paper-tint cursor-pointer',
                      ].join(' ')}
                    >
                      {isSwitchingThis && <Loader2 className="w-3 h-3 animate-spin" />}
                      {isActive && !isSwitchingThis && <Check className="w-3 h-3" />}
                      {chipLabel}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
