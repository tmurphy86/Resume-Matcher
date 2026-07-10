'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { ProvenanceData } from '@/components/common/resume_previewer_context';
import { useTranslations } from '@/lib/i18n';

interface ProvenancePanelProps {
  provenance: ProvenanceData | null | undefined;
  unverifiedCount: number;
  jobId?: string | null;
  selectedKeyword?: string | null;
  onClearKeyword?: () => void;
}

export function ProvenancePanel({
  provenance,
  unverifiedCount,
  selectedKeyword,
  onClearKeyword,
}: ProvenancePanelProps) {
  const { t } = useTranslations();
  const [isExpanded, setIsExpanded] = useState(false);

  if (!provenance) {
    return null;
  }

  const hasDetails =
    (provenance.uncovered_items && provenance.uncovered_items.length > 0) ||
    (provenance.broken_items && provenance.broken_items.length > 0);

  return (
    <div className="border border-black shadow-sw-sm bg-white">
      {/* Selected gap highlight bar */}
      {selectedKeyword && (
        <div className="flex items-center justify-between gap-3 p-3 border-b border-primary bg-[#EFF6FF]">
          <span className="font-mono text-xs text-ink font-bold">
            {t('tailor.provenance.selectedGap', { keyword: selectedKeyword })}
          </span>
          <button
            onClick={onClearKeyword}
            className="font-mono text-xs text-primary hover:text-primary/80 transition-colors font-bold"
            aria-label={t('tailor.provenance.clearGap')}
          >
            ×
          </button>
        </div>
      )}
      {/* Status bar */}
      <div className="flex items-center gap-4 p-3 border-b border-black">
        <h3 className="font-serif text-sm font-bold uppercase tracking-tight mr-auto">
          {t('tailor.provenance.title')}
        </h3>
        <span className="font-mono text-xs text-success font-bold">
          {provenance.covered} {t('tailor.provenance.covered')}
        </span>
        <span className="font-mono text-xs text-warning font-bold">
          {provenance.uncovered} {t('tailor.provenance.uncovered')}
        </span>
        <span className="font-mono text-xs text-destructive font-bold">
          {provenance.broken} {t('tailor.provenance.broken')}
        </span>
        {hasDetails && (
          <button
            onClick={() => setIsExpanded((v) => !v)}
            className="font-mono text-xs text-ink-soft hover:text-ink transition-colors"
            aria-label={isExpanded ? 'Collapse provenance details' : 'Expand provenance details'}
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>
        )}
      </div>

      {/* Warning rows */}
      <div className="p-3 space-y-2">
        {provenance.uncovered > 0 && (
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-xs text-warning">
              {provenance.uncovered} {t('tailor.provenance.uncovered')} blocks
            </span>
            <Link
              href="/facts?tab=interview"
              className="font-mono text-xs text-primary underline hover:opacity-80 transition-opacity"
            >
              {t('tailor.provenance.verifyGaps')}
            </Link>
          </div>
        )}
        {unverifiedCount > 0 && (
          <p className="font-mono text-xs text-warning font-bold">
            {t('tailor.provenance.unverifiedWarning', { count: String(unverifiedCount) })}
          </p>
        )}
      </div>

      {/* Collapsible detail list */}
      {isExpanded && hasDetails && (
        <div className="border-t border-black p-3 space-y-4">
          {provenance.uncovered_items && provenance.uncovered_items.length > 0 && (
            <div>
              <p className="font-mono text-xs font-bold uppercase tracking-wider mb-2">
                {t('tailor.provenance.uncoveredItems')}
              </p>
              <ul className="space-y-1">
                {provenance.uncovered_items.map((item, idx) => (
                  <li key={idx} className="border border-black p-2 bg-[#FFF7ED]">
                    <span className="font-mono text-xs text-warning font-bold">{item.section}</span>
                    <p className="font-mono text-xs text-ink-soft mt-0.5 line-clamp-2">
                      {item.text}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {provenance.broken_items && provenance.broken_items.length > 0 && (
            <div>
              <p className="font-mono text-xs font-bold uppercase tracking-wider mb-2">
                {t('tailor.provenance.brokenItems')}
              </p>
              <ul className="space-y-1">
                {provenance.broken_items.map((item, idx) => (
                  <li key={idx} className="border border-black p-2 bg-[#FEF2F2]">
                    <span className="font-mono text-xs text-destructive font-bold">
                      {item.section}
                    </span>
                    <span className="font-mono text-xs text-ink-soft ml-2">[{item.fact_id}]</span>
                    <p className="font-mono text-xs text-ink-soft mt-0.5 line-clamp-2">
                      {item.text}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
