'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Loader2 from 'lucide-react/dist/esm/icons/loader-2';
import Pencil from 'lucide-react/dist/esm/icons/pencil';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { useTranslations } from '@/lib/i18n';
import {
  getApplicationDetail,
  getInterestDimensions,
  updateApplication,
  type ApplicationDetail,
  type InterestDimension,
  type InterestSignal,
} from '@/lib/api/tracker';

interface CardDetailModalProps {
  applicationId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function CardDetailModal({
  applicationId,
  open,
  onOpenChange,
  onUpdated,
}: CardDetailModalProps) {
  const { t } = useTranslations();
  const router = useRouter();
  const [detail, setDetail] = useState<ApplicationDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [notes, setNotes] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [notesError, setNotesError] = useState<string | null>(null);

  // Interest signals state
  const [dimensions, setDimensions] = useState<InterestDimension[]>([]);
  const [signals, setSignals] = useState<InterestSignal[]>([]);
  const [savingSignals, setSavingSignals] = useState(false);
  const [signalsSaved, setSignalsSaved] = useState(false);
  const dimensionsFetchedRef = useRef(false);

  // Load interest dimensions once (cached across modal opens).
  useEffect(() => {
    if (dimensionsFetchedRef.current) return;
    dimensionsFetchedRef.current = true;
    getInterestDimensions()
      .then(setDimensions)
      .catch(() => {
        // Fail silently — interest panel simply won't render.
        dimensionsFetchedRef.current = false;
      });
  }, []);

  useEffect(() => {
    if (!open || !applicationId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    getApplicationDetail(applicationId)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setNotes(data.notes ?? '');
        setSignals(data.interest_signals ?? []);
        setNotesError(null);
        setSignalsSaved(false);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, applicationId]);

  // Keep textarea Enter from bubbling to dialog/global handlers.
  const handleNotesKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter') e.stopPropagation();
  };

  const handleSaveNotes = async () => {
    if (!applicationId) return;
    setSavingNotes(true);
    setNotesError(null);
    try {
      await updateApplication(applicationId, { notes });
      onUpdated();
    } catch {
      // Show a generic message — never echo raw backend error text inline,
      // which could contain sensitive values.
      setNotesError(t('common.error'));
    } finally {
      setSavingNotes(false);
    }
  };

  // Toggle a weight for a dimension. Clicking the same weight twice removes the signal.
  const handleWeightClick = (
    dimId: string,
    weight: number,
    existing: InterestSignal | undefined
  ) => {
    setSignalsSaved(false);
    if (existing && existing.weight === weight) {
      // Remove signal (toggle off).
      setSignals((prev) => prev.filter((s) => s.dimension !== dimId));
    } else {
      setSignals((prev) => {
        const filtered = prev.filter((s) => s.dimension !== dimId);
        return [...filtered, { dimension: dimId, weight, note: existing?.note }];
      });
    }
  };

  const handleSaveSignals = async () => {
    if (!applicationId) return;
    setSavingSignals(true);
    try {
      await updateApplication(applicationId, { interest_signals: signals });
      setSignalsSaved(true);
      onUpdated();
    } catch {
      // Fail silently on signals save — don't surface raw backend errors.
    } finally {
      setSavingSignals(false);
    }
  };

  // A resume is "available" only when resume_id exists AND the resume record is present.
  // Considering cards have resume_id === null (never had a resume).
  // Deleted resumes have resume_id set but resume === null.
  const hasResumeId = Boolean(detail?.resume_id);
  const resumeAvailable = hasResumeId && Boolean(detail?.resume);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{detail?.company || t('tracker.card.companyUnknown')}</DialogTitle>
          <DialogDescription>{detail?.role || t('tracker.card.roleUnknown')}</DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-steel-grey" />
          </div>
        ) : detail ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 font-mono text-xs uppercase text-ink-soft">
              <span className="border border-black bg-paper-tint px-2 py-0.5">
                {t(`tracker.columns.${detail.status}`)}
              </span>
              {detail.applied_at && (
                <span>
                  {new Date(detail.applied_at).toLocaleDateString('en-US', {
                    month: 'short',
                    year: 'numeric',
                  })}
                </span>
              )}
            </div>

            <div className="space-y-1">
              <Label>{t('tracker.modal.jobDescription')}</Label>
              <div className="max-h-48 overflow-y-auto whitespace-pre-wrap border border-black bg-background p-3 text-sm">
                {detail.job_content || t('tracker.modal.noJobDescription')}
              </div>
            </div>

            <div className="space-y-1">
              <Label htmlFor="card-notes">{t('tracker.modal.notes')}</Label>
              <Textarea
                id="card-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                onKeyDown={handleNotesKeyDown}
                placeholder={t('tracker.modal.notesPlaceholder')}
                rows={3}
              />
              <div className="flex items-center justify-end gap-3">
                {notesError && (
                  <span className="font-mono text-xs text-destructive">{notesError}</span>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleSaveNotes}
                  disabled={savingNotes}
                >
                  {savingNotes ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    t('tracker.modal.saveNotes')
                  )}
                </Button>
              </div>
            </div>

            {/* Resume availability notice */}
            {!hasResumeId && (
              <p className="font-mono text-xs text-ink-soft">{t('tracker.modal.noResume')}</p>
            )}
            {hasResumeId && !resumeAvailable && (
              <p className="font-mono text-xs text-warning">
                {t('tracker.modal.resumeUnavailable')}
              </p>
            )}

            {/* Interest signals panel */}
            {dimensions.length > 0 && (
              <div className="border-t border-black pt-4">
                <p className="mb-3 font-mono text-xs font-bold uppercase tracking-wide text-ink">
                  {t('tracker.interest.title')}
                </p>
                <div className="space-y-0">
                  {dimensions.map((dim) => {
                    const signal = signals.find((s) => s.dimension === dim.id);
                    return (
                      <div
                        key={dim.id}
                        className="flex items-center gap-3 border-b border-black/10 py-1.5 last:border-0"
                      >
                        <span className="flex-1 font-mono text-xs text-ink">{dim.label}</span>
                        <div className="flex gap-0.5">
                          {[1, 2, 3, 4, 5].map((w) => (
                            <button
                              key={w}
                              type="button"
                              onClick={() => handleWeightClick(dim.id, w, signal)}
                              className="h-4 w-4 border border-black font-mono text-[9px] text-ink hover:bg-primary hover:text-white"
                              style={{
                                background:
                                  signal && signal.weight >= w ? '#1D4ED8' : 'transparent',
                                color: signal && signal.weight >= w ? 'white' : 'black',
                              }}
                              aria-label={`${dim.label} weight ${w}`}
                            >
                              {w}
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-3 flex items-center gap-3">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleSaveSignals}
                    disabled={savingSignals}
                  >
                    {savingSignals ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : signalsSaved ? (
                      t('tracker.interest.saved')
                    ) : (
                      t('tracker.interest.save')
                    )}
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="py-6 text-center font-mono text-sm text-steel-grey">
            {t('tracker.modal.loadFailed')}
          </p>
        )}

        <DialogFooter>
          <Button
            onClick={() => {
              if (detail?.resume_id) router.push(`/builder?id=${detail.resume_id}`);
            }}
            disabled={!resumeAvailable}
          >
            <Pencil className="h-4 w-4" />
            {t('tracker.modal.editResume')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
