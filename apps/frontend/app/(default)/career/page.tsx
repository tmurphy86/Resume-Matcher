'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import ArrowLeft from 'lucide-react/dist/esm/icons/arrow-left';
import Loader2 from 'lucide-react/dist/esm/icons/loader-2';
import { Button } from '@/components/ui/button';
import { useTranslations } from '@/lib/i18n';
import { sanitizeHtml } from '@/lib/utils/html-sanitizer';
import {
  listCareerReports,
  generateCareerReport,
  clusterArchetypes,
  type CareerReport,
  type ArchetypeScore,
} from '@/lib/api/career';
import { listApplications, type Application } from '@/lib/api/tracker';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ATTRACTION_THRESHOLD = 2.5;
const FIT_THRESHOLD = 0.5;
const STALE_APP_THRESHOLD = 5;

// ---------------------------------------------------------------------------
// Outcome rate types and computation
// ---------------------------------------------------------------------------

interface StatusHistoryEntry {
  status: string;
  at: string;
}

type ApplicationWithHistory = Application & { status_history: StatusHistoryEntry[] };

const _RESPONSE_STATUSES = new Set(['response', 'interview', 'offer', 'accepted']);
const _INTERVIEW_STATUSES = new Set(['interview', 'offer', 'accepted']);

export function computeOutcomeRates(
  applications: ApplicationWithHistory[],
  archetypeJdIds: string[]
): { responseRate: number; interviewRate: number } {
  const memberIds = new Set(archetypeJdIds);
  const members = applications.filter((a) => memberIds.has(a.job_id));
  if (members.length === 0) return { responseRate: 0, interviewRate: 0 };

  let responseCount = 0;
  let interviewCount = 0;

  for (const app of members) {
    const history = app.status_history || [];
    const hasSeen = (set: Set<string>) => history.some((e) => set.has(e.status));
    if (hasSeen(_RESPONSE_STATUSES)) responseCount++;
    if (hasSeen(_INTERVIEW_STATUSES)) interviewCount++;
  }

  return {
    responseRate: responseCount / members.length,
    interviewRate: interviewCount / members.length,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function formatAttraction(val: number): string {
  return `${val.toFixed(1)} / 5.0`;
}

function formatFit(val: number): string {
  return `${Math.round(val * 100)}%`;
}

/** Convert plain markdown (subset) to HTML suitable for sanitizeHtml whitelist. */
function markdownToSafeHtml(md: string): string {
  // Very lightweight: bold, italic, paragraphs, line breaks.
  // `#` heading syntax is NOT parsed — headings are not in the whitelist.
  // Deliberately minimal — the sanitizeHtml call strips anything else.
  return md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

// ---------------------------------------------------------------------------
// Attraction×Fit 2×2 Quadrant
// ---------------------------------------------------------------------------

interface QuadrantProps {
  scores: ArchetypeScore[];
}

const QUADRANTS = [
  {
    key: 'stretch',
    labelKey: 'career.quadrant.stretch',
    descKey: 'career.quadrant.stretchDesc',
    highAttraction: true,
    highFit: false,
    borderColor: 'border-warning',
    textColor: 'text-warning',
  },
  {
    key: 'target',
    labelKey: 'career.quadrant.target',
    descKey: 'career.quadrant.targetDesc',
    highAttraction: true,
    highFit: true,
    borderColor: 'border-success',
    textColor: 'text-success',
  },
  {
    key: 'deprioritize',
    labelKey: 'career.quadrant.deprioritize',
    descKey: 'career.quadrant.deprioritizeDesc',
    highAttraction: false,
    highFit: false,
    borderColor: 'border-black',
    textColor: 'text-ink-soft',
  },
  {
    key: 'signal',
    labelKey: 'career.quadrant.signal',
    descKey: 'career.quadrant.signalDesc',
    highAttraction: false,
    highFit: true,
    borderColor: 'border-primary',
    textColor: 'text-primary',
  },
] as const;

function AttractionFitQuadrant({ scores }: QuadrantProps) {
  const { t } = useTranslations();

  const getNames = (highAttraction: boolean, highFit: boolean) =>
    scores
      .filter(
        (s) =>
          s.attraction >= ATTRACTION_THRESHOLD === highAttraction &&
          s.fit >= FIT_THRESHOLD === highFit
      )
      .map((s) => s.archetype_name);

  return (
    <div className="border border-black">
      {/* Axis labels */}
      <div className="border-b border-black bg-secondary px-4 py-2">
        <p className="font-mono text-xs uppercase tracking-wider text-ink-soft">
          {t('career.quadrant.title')}
        </p>
      </div>
      {/* Y-axis label + grid */}
      <div className="flex">
        {/* Y-axis */}
        <div className="flex w-8 shrink-0 items-center justify-center border-r border-black">
          <span
            className="font-mono text-[9px] uppercase tracking-widest text-ink-soft"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
          >
            {t('career.quadrant.yAxis')}
          </span>
        </div>
        {/* 2×2 grid */}
        <div className="flex-1">
          {/* High attraction row */}
          <div className="grid grid-cols-2">
            {QUADRANTS.filter((q) => q.highAttraction).map((q) => {
              const names = getNames(q.highAttraction, q.highFit);
              return (
                <div
                  key={q.key}
                  className={`min-h-[120px] border-b border-r border-black p-3 last:border-r-0`}
                >
                  <p
                    className={`font-mono text-[10px] uppercase tracking-wider ${q.textColor} mb-2`}
                  >
                    {t(q.labelKey)}
                  </p>
                  <p className="mb-2 font-mono text-[9px] text-ink-soft">{t(q.descKey)}</p>
                  <div className="flex flex-wrap gap-1">
                    {names.length === 0 ? (
                      <span className="font-mono text-[10px] text-ink-soft">—</span>
                    ) : (
                      names.map((name) => (
                        <span
                          key={name}
                          className={`border ${q.borderColor} px-1.5 py-0.5 font-mono text-[10px]`}
                        >
                          {name}
                        </span>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {/* Low attraction row */}
          <div className="grid grid-cols-2">
            {QUADRANTS.filter((q) => !q.highAttraction).map((q) => {
              const names = getNames(q.highAttraction, q.highFit);
              return (
                <div
                  key={q.key}
                  className={`min-h-[120px] border-r border-black p-3 last:border-r-0`}
                >
                  <p
                    className={`font-mono text-[10px] uppercase tracking-wider ${q.textColor} mb-2`}
                  >
                    {t(q.labelKey)}
                  </p>
                  <p className="mb-2 font-mono text-[9px] text-ink-soft">{t(q.descKey)}</p>
                  <div className="flex flex-wrap gap-1">
                    {names.length === 0 ? (
                      <span className="font-mono text-[10px] text-ink-soft">—</span>
                    ) : (
                      names.map((name) => (
                        <span
                          key={name}
                          className={`border ${q.borderColor} px-1.5 py-0.5 font-mono text-[10px]`}
                        >
                          {name}
                        </span>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {/* X-axis label */}
          <div className="border-t border-black px-3 py-1 text-center">
            <span className="font-mono text-[9px] uppercase tracking-widest text-ink-soft">
              {t('career.quadrant.xAxis')}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Archetype Card
// ---------------------------------------------------------------------------

interface ArchetypeCardProps {
  score: ArchetypeScore;
  jdCount: number;
  responseRate: number;
  interviewRate: number;
}

function ArchetypeCard({ score, jdCount, responseRate, interviewRate }: ArchetypeCardProps) {
  const { t } = useTranslations();
  const topGaps = score.gaps.slice(0, 3);

  return (
    <div className="border border-black bg-canvas shadow-[2px_2px_0px_black]">
      <div className="border-b border-black px-4 py-3">
        <h3 className="font-serif text-lg uppercase tracking-tight">{score.archetype_name}</h3>
        <p className="font-mono text-xs text-ink-soft">
          {jdCount} {t('career.card.jdCount')}
        </p>
      </div>
      <div className="grid grid-cols-2 divide-x divide-black border-b border-black">
        <div className="px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">
            {t('career.card.attraction')}
          </p>
          <p className="font-mono text-xl font-bold">{formatAttraction(score.attraction)}</p>
        </div>
        <div className="px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">
            {t('career.card.fit')}
          </p>
          <p className="font-mono text-xl font-bold">{formatFit(score.fit)}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 divide-x divide-black border-b border-black">
        <div className="px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">
            {t('career.card.responseRate')}
          </p>
          <p className="font-mono text-xl font-bold">{formatFit(responseRate)}</p>
        </div>
        <div className="px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">
            {t('career.card.interviewRate')}
          </p>
          <p className="font-mono text-xl font-bold">{formatFit(interviewRate)}</p>
        </div>
      </div>
      {topGaps.length > 0 && (
        <div className="px-4 py-3">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink-soft">
            {t('career.card.gaps')}
          </p>
          <ul className="flex flex-col gap-1">
            {topGaps.map((gap) => (
              <li key={gap}>
                <Link
                  href={`/tailor?gap=${encodeURIComponent(gap)}`}
                  className="font-mono text-xs text-primary underline hover:text-primary/70 transition-colors"
                >
                  {gap}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Report history item
// ---------------------------------------------------------------------------

interface ReportHistoryItemProps {
  report: CareerReport;
  isActive: boolean;
  onClick: () => void;
}

function ReportHistoryItem({ report, isActive, onClick }: ReportHistoryItemProps) {
  const { t } = useTranslations();
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full border border-black px-4 py-3 text-left transition-colors hover:bg-secondary ${
        isActive ? 'bg-secondary' : 'bg-canvas'
      }`}
    >
      <p className="font-mono text-xs">{formatDate(report.created_at)}</p>
      <p className="mt-0.5 font-mono text-[10px] text-ink-soft">
        {report.archetypes_json.length} {t('career.history.archetypes')}
        {' · '}
        {report.scores_json ? t('career.history.scored') : t('career.history.notScored')}
      </p>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function CareerPage() {
  const { t } = useTranslations();

  const [reports, setReports] = useState<CareerReport[]>([]);
  const [activeReport, setActiveReport] = useState<CareerReport | null>(null);
  const [applications, setApplications] = useState<ApplicationWithHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [clustering, setClustering] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // ── Load reports on mount ─────────────────────────────────────────────────
  const loadReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, appData] = await Promise.all([listCareerReports(), listApplications()]);
      setReports(data);
      if (data.length > 0) {
        setActiveReport(data[0]);
      }
      // Flatten the columnar response into a flat list for rate computation.
      const flat = Object.values(appData.columns).flat() as ApplicationWithHistory[];
      setApplications(flat);
    } catch (err) {
      setError(t('career.errors.loadFailed'));
      console.error('Failed to load career reports:', err);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  // ── Cluster archetypes ────────────────────────────────────────────────────
  const handleCluster = async () => {
    setClustering(true);
    setActionError(null);
    try {
      const report = await clusterArchetypes();
      setReports((prev) => [report, ...prev]);
      setActiveReport(report);
    } catch (err) {
      setActionError(t('career.errors.clusterFailed'));
      console.error('Clustering failed:', err);
    } finally {
      setClustering(false);
    }
  };

  // ── Generate report (scores + narrative) ──────────────────────────────────
  const handleGenerate = async () => {
    setGenerating(true);
    setActionError(null);
    try {
      const updated = await generateCareerReport();
      setReports((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setActiveReport(updated);
    } catch (err) {
      setActionError(t('career.errors.generateFailed'));
      console.error('Report generation failed:', err);
    } finally {
      setGenerating(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  const hasScores = activeReport?.scores_json && activeReport.scores_json.length > 0;

  // Stale-report nudge: count applications created after the latest report.
  const latestReport = reports.length > 0 ? reports[0] : null;
  const newAppsCount =
    latestReport != null
      ? applications.filter((a) => new Date(a.created_at) > new Date(latestReport.created_at))
          .length
      : 0;
  const showStaleBanner = newAppsCount >= STALE_APP_THRESHOLD;

  return (
    <div
      className="min-h-screen w-full bg-background px-4 py-6 md:px-8"
      style={{
        backgroundImage:
          'linear-gradient(rgba(29, 78, 216, 0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(29, 78, 216, 0.1) 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }}
    >
      <div className="mx-auto w-full max-w-[86rem]">
        {/* Back nav */}
        <Link
          href="/dashboard"
          className="mb-4 inline-flex items-center gap-1 font-mono text-xs uppercase text-ink-soft hover:text-primary"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          {t('nav.backToDashboard')}
        </Link>

        {/* Main card */}
        <div className="border border-black bg-background shadow-sw-lg">
          {/* Header */}
          <div className="border-b border-black p-8 md:p-10">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h1 className="font-serif text-4xl uppercase tracking-tight text-black md:text-5xl">
                  {t('career.title')}
                </h1>
                <p className="mt-2 font-mono text-xs text-ink-soft">{t('career.subtitle')}</p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  onClick={handleCluster}
                  disabled={clustering || generating}
                  variant="outline"
                  className="border border-black shadow-sw-sm hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all self-start"
                >
                  {clustering ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {t('career.clustering')}
                    </span>
                  ) : (
                    t('career.clusterButton')
                  )}
                </Button>
                <Button
                  onClick={handleGenerate}
                  disabled={generating || clustering || !activeReport}
                  className="border border-black bg-primary text-white shadow-sw-sm hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all self-start"
                >
                  {generating ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      {t('career.generating')}
                    </span>
                  ) : (
                    t('career.generateButton')
                  )}
                </Button>
              </div>
            </div>
            {actionError && (
              <p className="mt-3 font-mono text-sm text-destructive">{actionError}</p>
            )}
          </div>

          {/* Stale-report nudge */}
          {showStaleBanner && (
            <div className="border-b border-black px-8 py-3">
              <p className="border border-black bg-canvas shadow-[2px_2px_0px_black] px-4 py-2 font-mono text-sm">
                {t('career.staleReportBanner', { count: String(newAppsCount) })}
              </p>
            </div>
          )}

          {/* Body */}
          {loading ? (
            <div className="flex items-center justify-center p-16">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="p-8 font-mono text-sm text-destructive">{error}</div>
          ) : reports.length === 0 ? (
            <div className="p-12 text-center font-mono text-sm text-ink-soft">
              {t('career.empty')}
            </div>
          ) : (
            <div className="flex flex-col lg:flex-row">
              {/* Sidebar: report history */}
              <div className="w-full shrink-0 border-b border-black lg:w-64 lg:border-b-0 lg:border-r">
                <div className="border-b border-black bg-secondary px-4 py-2">
                  <p className="font-mono text-xs uppercase tracking-wider">
                    {t('career.history.title')}
                  </p>
                </div>
                <div className="flex flex-col divide-y divide-black">
                  {reports.map((r) => (
                    <ReportHistoryItem
                      key={r.id}
                      report={r}
                      isActive={activeReport?.id === r.id}
                      onClick={() => setActiveReport(r)}
                    />
                  ))}
                </div>
              </div>

              {/* Main content */}
              {activeReport && (
                <div className="flex-1 overflow-hidden">
                  {/* Quadrant — only shown when scores exist */}
                  {hasScores && (
                    <div className="border-b border-black p-6">
                      <AttractionFitQuadrant scores={activeReport.scores_json!} />
                    </div>
                  )}

                  {/* Archetype cards */}
                  {hasScores ? (
                    <div className="border-b border-black p-6">
                      <h2 className="mb-4 font-serif text-2xl uppercase tracking-tight">
                        {t('career.archetypes.title')}
                      </h2>
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                        {activeReport.scores_json!.map((score) => {
                          const archetype = activeReport.archetypes_json.find(
                            (a) => a.name === score.archetype_name
                          );
                          const rates = computeOutcomeRates(applications, archetype?.jd_ids ?? []);
                          return (
                            <ArchetypeCard
                              key={score.archetype_name}
                              score={score}
                              jdCount={archetype?.jd_ids.length ?? 0}
                              responseRate={rates.responseRate}
                              interviewRate={rates.interviewRate}
                            />
                          );
                        })}
                      </div>
                    </div>
                  ) : (
                    // Archetype list without scores
                    <div className="border-b border-black p-6">
                      <h2 className="mb-4 font-serif text-2xl uppercase tracking-tight">
                        {t('career.archetypes.title')}
                      </h2>
                      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                        {activeReport.archetypes_json.map((archetype) => (
                          <div
                            key={archetype.name}
                            className="border border-black bg-canvas shadow-[2px_2px_0px_black] p-4"
                          >
                            <h3 className="font-serif text-lg uppercase tracking-tight">
                              {archetype.name}
                            </h3>
                            <p className="mt-1 font-mono text-xs text-ink-soft">
                              {archetype.jd_ids.length} {t('career.card.jdCount')}
                            </p>
                            <p className="mt-2 text-sm leading-snug text-ink-soft">
                              {archetype.description}
                            </p>
                            <div className="mt-2 font-mono text-[10px] uppercase text-warning">
                              {t('career.archetypes.noScoresYet')}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Advice markdown */}
                  {activeReport.advice_md && (
                    <div className="p-6">
                      <h2 className="mb-4 font-serif text-2xl uppercase tracking-tight">
                        {t('career.advice.title')}
                      </h2>
                      <p className="font-mono text-xs text-black/60 mb-2">
                        {t('career.advice.unverified')}
                      </p>
                      <div
                        className="prose-sm max-w-none font-sans leading-relaxed [&_strong]:font-bold [&_em]:italic [&_a]:text-primary [&_a]:underline"
                        dangerouslySetInnerHTML={{
                          __html: sanitizeHtml(
                            `<p>${markdownToSafeHtml(activeReport.advice_md)}</p>`
                          ),
                        }}
                      />
                    </div>
                  )}

                  {/* No scores + no advice: prompt to generate */}
                  {!hasScores && !activeReport.advice_md && (
                    <div className="p-6 font-mono text-sm text-ink-soft">
                      {t('career.noReport')}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
