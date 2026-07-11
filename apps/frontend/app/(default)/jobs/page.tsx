'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import ArrowLeft from 'lucide-react/dist/esm/icons/arrow-left';
import X from 'lucide-react/dist/esm/icons/x';
import Loader2 from 'lucide-react/dist/esm/icons/loader-2';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useTranslations } from '@/lib/i18n';
import { listJobs, getJob, type JobSummary, type JobDetail } from '@/lib/api/jobs';

export default function JobsPage() {
  const { t } = useTranslations();

  // ── Data ──────────────────────────────────────────────────────────────────
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Filters ───────────────────────────────────────────────────────────────
  const [search, setSearch] = useState('');
  const [archetypeFilter, setArchetypeFilter] = useState('');

  // ── Detail panel ──────────────────────────────────────────────────────────
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [detail, setDetail] = useState<JobDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // ── Load jobs ─────────────────────────────────────────────────────────────
  const loadJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listJobs();
      setJobs(data);
    } catch (err) {
      setError(t('jobs.errors.loadFailed'));
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  // ── Load detail on selection ──────────────────────────────────────────────
  useEffect(() => {
    if (!selectedJobId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setDetailError(null);
    getJob(selectedJobId)
      .then(setDetail)
      .catch((err) => {
        setDetailError(t('jobs.errors.detailFailed'));
        console.error('Failed to load job detail:', err);
      })
      .finally(() => setDetailLoading(false));
  }, [selectedJobId, t]);

  // ── Derived ───────────────────────────────────────────────────────────────
  const archetypes = Array.from(
    new Set(jobs.map((j) => j.archetype).filter((a): a is string => Boolean(a)))
  ).sort();

  const filtered = jobs.filter((job) => {
    const matchSearch = !search || job.snippet.toLowerCase().includes(search.toLowerCase());
    const matchArchetype = !archetypeFilter || job.archetype === archetypeFilter;
    return matchSearch && matchArchetype;
  });

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    });
  };

  const toggleJob = (jobId: string) => setSelectedJobId((prev) => (prev === jobId ? null : jobId));

  // ── Render ────────────────────────────────────────────────────────────────
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
            <h1 className="font-serif text-4xl uppercase tracking-tight text-black md:text-5xl">
              {t('jobs.title')}
            </h1>
            <p className="mt-2 font-mono text-xs text-ink-soft">{t('jobs.subtitle')}</p>
          </div>

          {/* Filter bar */}
          <div className="flex flex-col gap-3 border-b border-black p-4 sm:flex-row sm:gap-4">
            <Input
              placeholder={t('jobs.searchPlaceholder')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="sm:max-w-xs"
              aria-label={t('jobs.searchPlaceholder')}
            />
            <select
              value={archetypeFilter}
              onChange={(e) => setArchetypeFilter(e.target.value)}
              className="border border-black bg-background px-3 py-2 font-mono text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-700 sm:max-w-xs"
              aria-label={t('jobs.filterByArchetype')}
            >
              <option value="">{t('jobs.allArchetypes')}</option>
              {archetypes.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </div>

          {/* Body: list + optional detail split */}
          <div className={selectedJobId ? 'flex divide-x divide-black' : undefined}>
            {/* Job list */}
            <div className={selectedJobId ? 'w-2/5 overflow-y-auto' : 'w-full'}>
              {loading ? (
                <div className="flex items-center justify-center p-16">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                </div>
              ) : error ? (
                <div className="p-8 font-mono text-sm text-destructive">{error}</div>
              ) : filtered.length === 0 ? (
                <div className="p-12 text-center font-mono text-sm text-ink-soft">
                  {search || archetypeFilter ? t('jobs.emptyFiltered') : t('jobs.empty')}
                </div>
              ) : (
                <ul>
                  {filtered.map((job) => (
                    <li
                      key={job.job_id}
                      className={`cursor-pointer border-b border-black transition-colors last:border-b-0 hover:bg-secondary/50 ${
                        selectedJobId === job.job_id ? 'bg-secondary' : ''
                      }`}
                      onClick={() => toggleJob(job.job_id)}
                    >
                      <div className="p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          {(job.company || job.role) && (
                            <span className="font-sans text-sm font-bold">
                              {[job.company, job.role].filter(Boolean).join(' — ')}
                            </span>
                          )}
                          {job.level && (
                            <span className="border border-black px-1.5 py-0.5 font-mono text-xs text-ink-soft">
                              {job.level}
                            </span>
                          )}
                          {job.archetype && (
                            <span className="border border-primary px-1.5 py-0.5 font-mono text-xs text-primary">
                              {job.archetype}
                            </span>
                          )}
                        </div>
                        <p className="mt-1.5 line-clamp-2 font-sans text-xs text-ink-soft">
                          {job.snippet}
                        </p>
                        <p className="mt-1 font-mono text-xs text-ink-soft">
                          {t('jobs.capturedOn')} {formatDate(job.created_at)}
                          <span className="ml-2 text-ink-soft/50">{job.job_id}</span>
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Detail panel */}
            {selectedJobId && (
              <div className="flex-1 overflow-y-auto">
                {/* Panel header */}
                <div className="flex items-center justify-between border-b border-black p-4">
                  <span className="font-mono text-xs uppercase text-ink-soft">
                    {detail
                      ? [detail.company, detail.role].filter(Boolean).join(' — ') || selectedJobId
                      : selectedJobId}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedJobId(null)}
                    className="border border-black"
                    aria-label={t('jobs.detail.close')}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>

                {detailLoading ? (
                  <div className="flex items-center justify-center p-16">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  </div>
                ) : detailError ? (
                  <div className="p-8 font-mono text-sm text-destructive">{detailError}</div>
                ) : detail ? (
                  <div className="flex flex-col divide-y divide-black">
                    {/* Applications link */}
                    <div className="p-4">
                      <p className="mb-1 font-mono text-xs uppercase tracking-wider text-ink-soft">
                        {t('jobs.detail.applicationsLinked')}
                      </p>
                      {detail.application_ids.length > 0 ? (
                        <Link
                          href="/tracker"
                          className="font-mono text-xs text-primary underline hover:no-underline"
                        >
                          {t('jobs.viewApplications')} ({detail.application_ids.length})
                        </Link>
                      ) : (
                        <span className="font-mono text-xs text-ink-soft">
                          {t('jobs.noApplications')}
                        </span>
                      )}
                    </div>

                    {/* Parsed: responsibilities + requirements side-by-side */}
                    {detail.responsibilities.length > 0 || detail.requirements.length > 0 ? (
                      <div className="grid grid-cols-1 divide-y divide-black md:grid-cols-2 md:divide-x md:divide-y-0">
                        <div className="p-4">
                          <p className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-soft">
                            {t('jobs.detail.responsibilities')}
                          </p>
                          <ul className="space-y-1">
                            {detail.responsibilities.map((r, i) => (
                              <li key={i} className="flex gap-2 font-sans text-sm">
                                <span className="mt-0.5 shrink-0 font-mono text-xs text-ink-soft">
                                  &mdash;
                                </span>
                                {r}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div className="p-4">
                          <p className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-soft">
                            {t('jobs.detail.requirements')}
                          </p>
                          <ul className="space-y-1">
                            {detail.requirements.map((r, i) => (
                              <li key={i} className="flex gap-2 font-sans text-sm">
                                <span className="mt-0.5 shrink-0 font-mono text-xs text-ink-soft">
                                  &mdash;
                                </span>
                                {r}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    ) : (
                      <div className="p-4 font-mono text-xs text-ink-soft">
                        {t('jobs.detail.noParsed')}
                      </div>
                    )}

                    {/* Raw JD */}
                    <div className="p-4">
                      <p className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-soft">
                        {t('jobs.detail.rawJd')}
                      </p>
                      <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed">
                        {detail.content}
                      </pre>
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
