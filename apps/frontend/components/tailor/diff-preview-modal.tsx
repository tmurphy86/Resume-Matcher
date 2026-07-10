'use client';

import { useState, useEffect, useRef } from 'react';
import {
  AlertTriangle,
  BookmarkPlus,
  Check,
  CheckCircle,
  X,
  ChevronDown,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useTranslations } from '@/lib/i18n';
import type {
  ResumeDiffSummary,
  ResumeFieldDiff,
  UnverifiedChange,
} from '@/components/common/resume_previewer_context';

interface DiffPreviewModalProps {
  isOpen: boolean;
  isConfirming?: boolean;
  onClose: () => void;
  onReject: () => void;
  onConfirm: () => void;
  diffSummary?: ResumeDiffSummary;
  detailedChanges?: ResumeFieldDiff[];
  errorMessage?: string;
  unverified?: UnverifiedChange[];
  /** When provided, enables "Save as variant" buttons on description/summary changes. */
  onSaveAsVariant?: (change: ResumeFieldDiff, tags: string[]) => Promise<void>;
}

export function DiffPreviewModal({
  isOpen,
  isConfirming = false,
  onClose,
  onReject,
  onConfirm,
  diffSummary,
  detailedChanges,
  errorMessage,
  unverified,
  onSaveAsVariant,
}: DiffPreviewModalProps) {
  const { t } = useTranslations();
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['summary', 'skills', 'descriptions', 'experience'])
  );

  // Elapsed timer while confirming
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (isConfirming) {
      setElapsed(0);
      intervalRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
      setElapsed(0);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isConfirming]);

  if (!diffSummary || !detailedChanges) {
    return (
      <Dialog
        open={isOpen}
        onOpenChange={(open) => {
          if (!open && !isConfirming) {
            onClose();
          }
        }}
      >
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col p-6 bg-background border-2 border-black shadow-sw-lg">
          <DialogHeader className="border-b-2 border-black pb-4 bg-white -mx-6 -mt-6 px-6 pt-6">
            <DialogTitle className="font-serif text-2xl font-bold uppercase tracking-tight">
              {t('tailor.missingDiffDialog.title')}
            </DialogTitle>
          </DialogHeader>

          <div className="mt-6 border-2 border-black bg-white p-4 font-mono text-xs text-ink-soft">
            {t('tailor.missingDiffDialog.description')}
          </div>
          <div className="mt-3 flex items-center gap-2 font-mono text-xs text-amber-700">
            <AlertTriangle className="w-4 h-4" />
            <span>{t('tailor.missingDiffDialog.confirmLabel')}</span>
          </div>

          <div className="flex justify-end items-center gap-3 pt-4 border-t-2 border-black bg-white -mx-6 -mb-6 px-6 py-4">
            <Button variant="outline" onClick={onClose} disabled={isConfirming} className="gap-2">
              {t('common.cancel')}
            </Button>
            <Button variant="warning" onClick={onConfirm} disabled={isConfirming} className="gap-2">
              {isConfirming ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {t('common.saving')}
                </>
              ) : (
                t('tailor.missingDiffDialog.confirmLabel')
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
    setExpandedSections(newExpanded);
  };

  // Build set of unverified field paths for badge lookup
  const unverifiedPaths = new Set((unverified ?? []).map((u) => u.path));

  // Group changes by type
  const summaryChanges = detailedChanges.filter((c) => c.field_type === 'summary');
  const skillChanges = detailedChanges.filter((c) => c.field_type === 'skill');
  const descChanges = detailedChanges.filter((c) => c.field_type === 'description');
  const certChanges = detailedChanges.filter((c) => c.field_type === 'certification');
  const experienceChanges = detailedChanges.filter((c) => c.field_type === 'experience');
  const educationChanges = detailedChanges.filter((c) => c.field_type === 'education');
  const projectChanges = detailedChanges.filter((c) => c.field_type === 'project');
  const languageChanges = detailedChanges.filter((c) => c.field_type === 'language');
  const awardChanges = detailedChanges.filter((c) => c.field_type === 'award');

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open && !isConfirming) {
          onClose();
        }
      }}
    >
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-hidden flex flex-col p-6 bg-background border-2 border-black shadow-sw-lg">
        <DialogHeader className="border-b-2 border-black pb-4 bg-white -mx-6 -mt-6 px-6 pt-6">
          <DialogTitle className="font-serif text-2xl font-bold uppercase tracking-tight">
            {t('tailor.diffModal.title')}
          </DialogTitle>
          <p className="font-mono text-xs text-ink-soft mt-2">
            {'// '}
            {t('tailor.diffModal.subtitle')}
          </p>
        </DialogHeader>

        {/* Summary cards */}
        <div className="border-2 border-black bg-white p-4 mt-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-3 h-3 bg-primary"></div>
            <h3 className="font-mono text-sm font-bold uppercase tracking-wider">
              {t('tailor.diffModal.summary')}
            </h3>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <StatCard
              label={t('tailor.diffModal.skillsAdded')}
              value={diffSummary.skills_added}
              variant="success"
            />
            <StatCard
              label={t('tailor.diffModal.skillsRemoved')}
              value={diffSummary.skills_removed}
              variant="warning"
            />
            <StatCard
              label={t('tailor.diffModal.certificationsAdded')}
              value={diffSummary.certifications_added}
              variant="info"
            />
            <StatCard
              label={t('tailor.diffModal.descriptionsModified')}
              value={diffSummary.descriptions_modified}
              variant="info"
            />
            <StatCard
              label={t('tailor.diffModal.highRiskChanges')}
              value={diffSummary.high_risk_changes}
              variant={diffSummary.high_risk_changes > 0 ? 'danger' : 'success'}
            />
          </div>

          {diffSummary.high_risk_changes > 0 && (
            <div className="mt-4 border-2 border-warning bg-[#FFF7ED] p-3 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
              <div>
                <p className="font-mono text-xs font-bold uppercase text-[#C2410C]">
                  {t('tailor.diffModal.warningTitle', {
                    count: diffSummary.high_risk_changes,
                  })}
                </p>
                <p className="font-mono text-xs text-[#C2410C] mt-1">
                  {t('tailor.diffModal.warningMessage')}
                </p>
              </div>
            </div>
          )}
        </div>

        {errorMessage && (
          <div className="mt-4 border-2 border-red-600 bg-red-50 p-3 font-mono text-xs text-red-700">
            {errorMessage}
          </div>
        )}

        {/* Detailed changes list */}
        <div className="flex-1 min-h-0 overflow-y-auto mt-4 space-y-4">
          {/* Summary changes */}
          {summaryChanges.length > 0 && (
            <ChangeSection
              title={t('tailor.diffModal.summaryChanges')}
              count={summaryChanges.length}
              isExpanded={expandedSections.has('summary')}
              onToggle={() => toggleSection('summary')}
            >
              {summaryChanges.map((change, idx) => (
                <ChangeItem
                  key={idx}
                  change={change}
                  isUnverified={unverifiedPaths.has(change.field_path)}
                  onSaveAsVariant={
                    onSaveAsVariant ? (tags) => onSaveAsVariant(change, tags) : undefined
                  }
                />
              ))}
            </ChangeSection>
          )}

          {/* Skill changes */}
          {skillChanges.length > 0 && (
            <ChangeSection
              title={t('tailor.diffModal.skillChanges')}
              count={skillChanges.length}
              isExpanded={expandedSections.has('skills')}
              onToggle={() => toggleSection('skills')}
            >
              {skillChanges.map((change, idx) => (
                <ChangeItem
                  key={idx}
                  change={change}
                  isUnverified={unverifiedPaths.has(change.field_path)}
                />
              ))}
            </ChangeSection>
          )}

          {/* Experience changes */}
          {experienceChanges.length > 0 && (
            <ChangeSection
              title={t('tailor.diffModal.experienceChanges')}
              count={experienceChanges.length}
              isExpanded={expandedSections.has('experience')}
              onToggle={() => toggleSection('experience')}
            >
              {experienceChanges.map((change, idx) => (
                <ChangeItem
                  key={idx}
                  change={change}
                  isUnverified={unverifiedPaths.has(change.field_path)}
                />
              ))}
            </ChangeSection>
          )}

          {/* Description changes */}
          {descChanges.length > 0 && (
            <ChangeSection
              title={t('tailor.diffModal.descriptionChanges')}
              count={descChanges.length}
              isExpanded={expandedSections.has('descriptions')}
              onToggle={() => toggleSection('descriptions')}
            >
              {descChanges.map((change, idx) => (
                <ChangeItem
                  key={idx}
                  change={change}
                  isUnverified={unverifiedPaths.has(change.field_path)}
                  onSaveAsVariant={
                    onSaveAsVariant ? (tags) => onSaveAsVariant(change, tags) : undefined
                  }
                />
              ))}
            </ChangeSection>
          )}

          {/* Education changes */}
          {educationChanges.length > 0 && (
            <ChangeSection
              title={t('tailor.diffModal.educationChanges')}
              count={educationChanges.length}
              isExpanded={expandedSections.has('education')}
              onToggle={() => toggleSection('education')}
            >
              {educationChanges.map((change, idx) => (
                <ChangeItem
                  key={idx}
                  change={change}
                  isUnverified={unverifiedPaths.has(change.field_path)}
                />
              ))}
            </ChangeSection>
          )}

          {/* Project changes */}
          {projectChanges.length > 0 && (
            <ChangeSection
              title={t('tailor.diffModal.projectChanges')}
              count={projectChanges.length}
              isExpanded={expandedSections.has('project')}
              onToggle={() => toggleSection('project')}
            >
              {projectChanges.map((change, idx) => (
                <ChangeItem
                  key={idx}
                  change={change}
                  isUnverified={unverifiedPaths.has(change.field_path)}
                />
              ))}
            </ChangeSection>
          )}

          {/* Certification changes */}
          {certChanges.length > 0 && (
            <ChangeSection
              title={t('tailor.diffModal.certificationChanges')}
              count={certChanges.length}
              isExpanded={expandedSections.has('certifications')}
              onToggle={() => toggleSection('certifications')}
            >
              {certChanges.map((change, idx) => (
                <ChangeItem
                  key={idx}
                  change={change}
                  isUnverified={unverifiedPaths.has(change.field_path)}
                />
              ))}
            </ChangeSection>
          )}

          {/* Language changes */}
          {languageChanges.length > 0 && (
            <ChangeSection
              title={t('tailor.diffModal.languageChanges')}
              count={languageChanges.length}
              isExpanded={expandedSections.has('languages')}
              onToggle={() => toggleSection('languages')}
            >
              {languageChanges.map((change, idx) => (
                <ChangeItem
                  key={idx}
                  change={change}
                  isUnverified={unverifiedPaths.has(change.field_path)}
                />
              ))}
            </ChangeSection>
          )}

          {/* Award changes */}
          {awardChanges.length > 0 && (
            <ChangeSection
              title={t('tailor.diffModal.awardChanges')}
              count={awardChanges.length}
              isExpanded={expandedSections.has('awards')}
              onToggle={() => toggleSection('awards')}
            >
              {awardChanges.map((change, idx) => (
                <ChangeItem
                  key={idx}
                  change={change}
                  isUnverified={unverifiedPaths.has(change.field_path)}
                />
              ))}
            </ChangeSection>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex justify-between items-center pt-4 border-t-2 border-black bg-white -mx-6 -mb-6 px-6 py-4">
          <Button variant="outline" onClick={onReject} disabled={isConfirming} className="gap-2">
            <X className="w-4 h-4" />
            {t('tailor.diffModal.rejectButton')}
          </Button>
          <div className="flex items-center gap-3">
            {isConfirming && elapsed > 0 && (
              <span className="font-mono text-xs text-steel-grey">{elapsed}s</span>
            )}
            <Button
              onClick={onConfirm}
              disabled={isConfirming}
              className="gap-2 bg-success hover:bg-green-800"
            >
              {isConfirming ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {t('common.saving')}
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4" />
                  {t('tailor.diffModal.confirmButton')}
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Helper component: stat card
interface StatCardProps {
  label: string;
  value: number;
  variant: 'success' | 'warning' | 'danger' | 'info';
}

function StatCard({ label, value, variant }: StatCardProps) {
  const colors = {
    success: 'border-success bg-[#F0FDF4] text-success',
    warning: 'border-warning bg-[#FFF7ED] text-warning',
    danger: 'border-destructive bg-[#FEF2F2] text-destructive',
    info: 'border-primary bg-[#EFF6FF] text-primary',
  };

  return (
    <div className={`border-2 p-3 ${colors[variant]}`}>
      <div className="font-mono text-2xl font-bold">{value}</div>
      <div className="font-mono text-xs uppercase tracking-wider mt-1">{label}</div>
    </div>
  );
}

// Helper component: collapsible change section
interface ChangeSectionProps {
  title: string;
  count: number;
  isExpanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function ChangeSection({ title, count, isExpanded, onToggle, children }: ChangeSectionProps) {
  return (
    <div className="border-2 border-black bg-white">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 hover:bg-paper-tint"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          <span className="font-mono text-sm font-bold uppercase tracking-wider">
            {title} ({count})
          </span>
        </div>
      </button>

      {isExpanded && <div className="border-t-2 border-black p-4 space-y-3">{children}</div>}
    </div>
  );
}

// Helper component: change item
interface ChangeItemProps {
  change: ResumeFieldDiff;
  isUnverified?: boolean;
  /** When provided, shows a "Save as variant" button (description/summary only). */
  onSaveAsVariant?: (tags: string[]) => Promise<void>;
}

function ChangeItem({ change, isUnverified, onSaveAsVariant }: ChangeItemProps) {
  const { t } = useTranslations();
  const [showSavePanel, setShowSavePanel] = useState(false);
  const [tags, setTags] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [savedOk, setSavedOk] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Background tint + leading glyph instead of left-stripe borders.
  // Side-stripe borders are an impeccable absolute_ban (BAN 1) — the most
  // overused dashboard "design touch". The leading +/-/~ glyph carries the
  // semantic load and the bg tint reinforces it.
  const typeBackgrounds = {
    added: 'bg-[#F0FDF4]',
    removed: 'bg-[#FEF2F2]',
    modified: 'bg-[#EFF6FF]',
  };

  const typeGlyphColors = {
    added: 'text-success',
    removed: 'text-destructive',
    modified: 'text-primary',
  };

  const typeLabels = {
    added: '+',
    removed: '-',
    modified: '~',
  };

  // "Save as variant" is relevant for description and summary changes that have new text.
  const canSaveAsVariant =
    onSaveAsVariant &&
    change.new_value &&
    (change.field_type === 'description' || change.field_type === 'summary');

  const handleSaveVariant = async () => {
    if (!onSaveAsVariant || !change.new_value) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      const tagList = tags
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      await onSaveAsVariant(tagList);
      setSavedOk(true);
      setShowSavePanel(false);
      setTags('');
    } catch {
      setSaveError(t('tailor.variants.errorSaving'));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className={`p-3 border border-black ${typeBackgrounds[change.change_type]}`}>
      <div className="flex items-start gap-2">
        <span
          className={`font-mono text-base font-bold uppercase tracking-wider ${typeGlyphColors[change.change_type]}`}
          aria-hidden="true"
        >
          {typeLabels[change.change_type]}
        </span>
        <div className="flex-1">
          {change.original_value && (
            <div className="line-through text-destructive font-mono text-sm mb-1">
              {change.original_value}
            </div>
          )}
          {change.new_value && (
            <div className="text-ink-soft font-mono text-sm">{change.new_value}</div>
          )}
        </div>
        {isUnverified && (
          <span className="font-mono text-xs font-bold text-warning border border-warning px-1 shrink-0">
            unverified
          </span>
        )}
        {change.change_type === 'added' && change.confidence === 'high' && (
          <AlertTriangle className="w-4 h-4 text-warning shrink-0" />
        )}
        {canSaveAsVariant && !savedOk && (
          <button
            onClick={() => setShowSavePanel((v) => !v)}
            className="font-mono text-xs text-primary hover:text-primary/80 flex items-center gap-1 shrink-0 transition-colors"
            aria-label={t('tailor.variants.saveAsVariant')}
            title={t('tailor.variants.saveAsVariant')}
          >
            <BookmarkPlus className="w-3.5 h-3.5" />
          </button>
        )}
        {savedOk && (
          <span className="font-mono text-xs text-success flex items-center gap-1 shrink-0">
            <Check className="w-3.5 h-3.5" />
            {t('tailor.variants.saved')}
          </span>
        )}
      </div>

      {/* Inline save-as-variant panel */}
      {showSavePanel && canSaveAsVariant && (
        <div className="mt-2 pt-2 border-t border-black flex items-center gap-2">
          <input
            type="text"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder={t('tailor.variants.tagPlaceholder')}
            className="flex-1 font-mono text-xs border border-black px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-primary min-w-0"
            aria-label={t('tailor.variants.tagLabel')}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.stopPropagation();
                void handleSaveVariant();
              }
            }}
          />
          <button
            onClick={() => void handleSaveVariant()}
            disabled={isSaving}
            className="font-mono text-xs border border-black bg-black text-white px-2 py-1 hover:bg-ink-soft disabled:opacity-50 shrink-0 flex items-center gap-1"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin" />
                {t('tailor.variants.saving')}
              </>
            ) : (
              t('tailor.variants.saveButton')
            )}
          </button>
          <button
            onClick={() => {
              setShowSavePanel(false);
              setTags('');
              setSaveError(null);
            }}
            className="font-mono text-xs text-ink-soft hover:text-ink shrink-0"
          >
            ×
          </button>
        </div>
      )}
      {saveError && <p className="mt-1 font-mono text-xs text-destructive">{saveError}</p>}
    </div>
  );
}
