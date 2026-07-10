'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import ArrowLeft from 'lucide-react/dist/esm/icons/arrow-left';
import Pencil from 'lucide-react/dist/esm/icons/pencil';
import Trash2 from 'lucide-react/dist/esm/icons/trash-2';
import Loader2 from 'lucide-react/dist/esm/icons/loader-2';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { useTranslations } from '@/lib/i18n';
import { fetchResumeList } from '@/lib/api/resume';
import {
  listFacts,
  updateFact,
  deleteFact,
  extractFacts,
  confirmFacts,
  confirmVariant,
  importResumeFacts,
  type Fact,
  type ConfirmResult,
  type ImportedFact,
} from '@/lib/api/facts';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EditingState {
  factId: string;
  statement: string;
  context: string;
  source: string;
  tags: string;
  confidence: string;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function FactsPage() {
  const { t } = useTranslations();

  // ── Data ──────────────────────────────────────────────────────────────────
  const [facts, setFacts] = useState<Fact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Filters (client-side) ─────────────────────────────────────────────────
  const [tagFilter, setTagFilter] = useState('');
  const [contextFilter, setContextFilter] = useState('');

  // ── Inline edit ───────────────────────────────────────────────────────────
  const [editing, setEditing] = useState<EditingState | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // ── Delete confirm ────────────────────────────────────────────────────────
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // ── Import modal ──────────────────────────────────────────────────────────
  const [importOpen, setImportOpen] = useState(false);
  const [importResumes, setImportResumes] = useState<
    { resume_id: string; filename: string | null; title?: string | null }[]
  >([]);
  const [importSelectedId, setImportSelectedId] = useState<string>('');
  const [importLoading, setImportLoading] = useState(false);
  const [importResults, setImportResults] = useState<ImportedFact[]>([]);
  const [importError, setImportError] = useState<string | null>(null);
  const [importConfirming, setImportConfirming] = useState(false);
  const [selectedVariants, setSelectedVariants] = useState<Set<string>>(new Set());

  // ── Extract modal ─────────────────────────────────────────────────────────
  const [extractOpen, setExtractOpen] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Fact[]>([]);
  const [selectedCandidates, setSelectedCandidates] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);

  // ── Load facts ────────────────────────────────────────────────────────────
  const loadFacts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listFacts();
      setFacts(data);
    } catch (err) {
      setError(t('facts.errors.loadFailed'));
      console.error('Failed to load facts:', err);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadFacts();
  }, [loadFacts]);

  // ── Filtered facts ────────────────────────────────────────────────────────
  const filteredFacts = facts.filter((f) => {
    const tagMatch =
      tagFilter === '' ||
      f.tags_json.some((tag) => tag.toLowerCase().includes(tagFilter.toLowerCase()));
    const ctxMatch =
      contextFilter === '' || (f.context ?? '').toLowerCase().includes(contextFilter.toLowerCase());
    return tagMatch && ctxMatch;
  });

  // ── Inline edit handlers ──────────────────────────────────────────────────
  const startEdit = (fact: Fact) => {
    setSaveError(null);
    setEditing({
      factId: fact.fact_id,
      statement: fact.statement,
      context: fact.context ?? '',
      source: fact.source ?? '',
      tags: fact.tags_json.join(', '),
      confidence: fact.confidence,
    });
  };

  const cancelEdit = () => {
    setEditing(null);
    setSaveError(null);
  };

  const saveEdit = async () => {
    if (!editing) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateFact(editing.factId, {
        statement: editing.statement,
        context: editing.context || null,
        source: editing.source || null,
        tags_json: editing.tags
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        confidence: editing.confidence,
      });
      setFacts((prev) => prev.map((f) => (f.fact_id === updated.fact_id ? updated : f)));
      setEditing(null);
    } catch (err) {
      setSaveError(t('facts.errors.saveFailed'));
      console.error('Failed to save fact:', err);
    } finally {
      setSaving(false);
    }
  };

  // ── Delete handlers ───────────────────────────────────────────────────────
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleteError(null);
    try {
      await deleteFact(deleteTarget);
      setFacts((prev) => prev.filter((f) => f.fact_id !== deleteTarget));
      setDeleteTarget(null);
    } catch (err) {
      setDeleteError(t('facts.errors.deleteFailed'));
      console.error('Failed to delete fact:', err);
    }
  };

  // ── Extract flow ──────────────────────────────────────────────────────────
  const openExtract = async () => {
    setExtractOpen(true);
    setExtractError(null);
    setCandidates([]);
    setSelectedCandidates(new Set());
    setExtracting(true);
    try {
      const resumes = await fetchResumeList(true);
      const master = resumes.find((r) => r.is_master);
      if (!master) {
        setExtractError(t('facts.extractModal.noMasterResume'));
        return;
      }
      const extracted = await extractFacts(master.resume_id);
      setCandidates(extracted);
      // Pre-select all non-duplicate candidates
      setSelectedCandidates(
        new Set(extracted.filter((c) => !c.duplicate_of).map((c) => c.fact_id))
      );
    } catch (err) {
      setExtractError(t('facts.errors.extractFailed'));
      console.error('Failed to extract facts:', err);
    } finally {
      setExtracting(false);
    }
  };

  const toggleCandidate = (factId: string) => {
    setSelectedCandidates((prev) => {
      const next = new Set(prev);
      if (next.has(factId)) {
        next.delete(factId);
      } else {
        next.add(factId);
      }
      return next;
    });
  };

  const handleConfirmSelected = async () => {
    const selected = candidates.filter((c) => selectedCandidates.has(c.fact_id));
    if (selected.length === 0) return;
    setConfirming(true);
    setExtractError(null);
    try {
      const results: ConfirmResult[] = await confirmFacts(selected);
      // Count successfully saved facts (non-duplicate)
      const saved = results.filter((r): r is Fact => !('status' in r));
      setFacts((prev) => [...prev, ...saved]);
      setExtractOpen(false);
    } catch (err) {
      setExtractError(t('facts.errors.extractFailed'));
      console.error('Failed to confirm facts:', err);
    } finally {
      setConfirming(false);
    }
  };

  // ── Import flow ───────────────────────────────────────────────────────────
  const openImport = async () => {
    setImportOpen(true);
    setImportError(null);
    setImportResults([]);
    setImportSelectedId('');
    setSelectedVariants(new Set());
    setImportLoading(true);
    try {
      const allResumes = await fetchResumeList(true);
      const nonMaster = allResumes.filter((r) => !r.is_master && r.processing_status === 'ready');
      setImportResumes(nonMaster);
    } catch (err) {
      setImportError(t('facts.errors.loadFailed'));
      console.error('Failed to load resumes for import:', err);
    } finally {
      setImportLoading(false);
    }
  };

  const toggleVariant = (factId: string) => {
    setSelectedVariants((prev) => {
      const next = new Set(prev);
      if (next.has(factId)) {
        next.delete(factId);
      } else {
        next.add(factId);
      }
      return next;
    });
  };

  const runImport = async () => {
    if (!importSelectedId) return;
    setImportLoading(true);
    setImportError(null);
    setImportResults([]);
    setSelectedVariants(new Set());
    try {
      const results = await importResumeFacts(importSelectedId);
      setImportResults(results);
    } catch (err) {
      setImportError(t('facts.errors.extractFailed'));
      console.error('Failed to import resume facts:', err);
    } finally {
      setImportLoading(false);
    }
  };

  const handleConfirmImport = async () => {
    const newFacts = importResults.filter((r) => r.group === 'new');
    const variantFacts = importResults.filter(
      (r) => r.group === 'variant_of' && selectedVariants.has(r.fact_id)
    );
    if (newFacts.length === 0 && variantFacts.length === 0) return;
    setImportConfirming(true);
    setImportError(null);
    try {
      const savedFacts: Fact[] = [];
      if (newFacts.length > 0) {
        const results: ConfirmResult[] = await confirmFacts(newFacts);
        savedFacts.push(...results.filter((r): r is Fact => !('status' in r)));
      }
      // Persist each checked variant_of phrasing to the matching master-resume block(s).
      await Promise.all(
        variantFacts.map((r) => confirmVariant(r.statement, r.existing_fact_id ?? ''))
      );
      if (savedFacts.length > 0) {
        setFacts((prev) => [...prev, ...savedFacts]);
      }
      setImportOpen(false);
    } catch (err) {
      setImportError(t('facts.errors.extractFailed'));
      console.error('Failed to confirm imported facts:', err);
    } finally {
      setImportConfirming(false);
    }
  };

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
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <h1 className="font-serif text-4xl uppercase tracking-tight text-black md:text-5xl">
                {t('facts.title')}
              </h1>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  onClick={openExtract}
                  className="border border-black bg-primary text-white shadow-sw-sm hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all self-start"
                >
                  {t('facts.extractButton')}
                </Button>
                <Button
                  onClick={openImport}
                  variant="outline"
                  className="border border-black shadow-sw-sm hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none transition-all self-start"
                >
                  {t('facts.importModal.title')}
                </Button>
              </div>
            </div>
          </div>

          {/* Filter bar */}
          <div className="flex flex-col gap-3 border-b border-black p-4 sm:flex-row sm:gap-4">
            <Input
              placeholder={t('facts.filterByTag')}
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
              className="sm:max-w-xs"
              aria-label={t('facts.filterByTag')}
            />
            <Input
              placeholder={t('facts.filterByContext')}
              value={contextFilter}
              onChange={(e) => setContextFilter(e.target.value)}
              className="sm:max-w-xs"
              aria-label={t('facts.filterByContext')}
            />
          </div>

          {/* Content */}
          {loading ? (
            <div className="flex items-center justify-center p-16">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="p-8 font-mono text-sm text-destructive">{error}</div>
          ) : filteredFacts.length === 0 ? (
            <div className="p-12 text-center font-mono text-sm text-ink-soft">
              {t('facts.empty')}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-black bg-secondary">
                    <th className="border-r border-black px-4 py-3 text-left font-mono text-xs uppercase tracking-wider">
                      {t('facts.table.statement')}
                    </th>
                    <th className="border-r border-black px-4 py-3 text-left font-mono text-xs uppercase tracking-wider">
                      {t('facts.table.context')}
                    </th>
                    <th className="border-r border-black px-4 py-3 text-left font-mono text-xs uppercase tracking-wider">
                      {t('facts.table.source')}
                    </th>
                    <th className="border-r border-black px-4 py-3 text-left font-mono text-xs uppercase tracking-wider">
                      {t('facts.table.tags')}
                    </th>
                    <th className="border-r border-black px-4 py-3 text-left font-mono text-xs uppercase tracking-wider">
                      {t('facts.table.confidence')}
                    </th>
                    <th className="px-4 py-3 text-left font-mono text-xs uppercase tracking-wider">
                      {t('facts.table.actions')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFacts.map((fact) => (
                    <tr
                      key={fact.fact_id}
                      className="border-b border-black last:border-b-0 hover:bg-secondary/50"
                    >
                      {editing?.factId === fact.fact_id ? (
                        // ── Inline edit row ─────────────────────────────────
                        <>
                          <td className="border-r border-black px-3 py-2" colSpan={5}>
                            <div className="flex flex-col gap-2">
                              <textarea
                                className="w-full border border-black bg-transparent px-3 py-2 font-sans text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-700"
                                rows={3}
                                value={editing.statement}
                                onChange={(e) =>
                                  setEditing((prev) =>
                                    prev ? { ...prev, statement: e.target.value } : prev
                                  )
                                }
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') e.stopPropagation();
                                }}
                                placeholder={t('facts.table.statement')}
                              />
                              <div className="flex flex-wrap gap-2">
                                <Input
                                  className="w-36"
                                  placeholder={t('facts.table.context')}
                                  value={editing.context}
                                  onChange={(e) =>
                                    setEditing((prev) =>
                                      prev ? { ...prev, context: e.target.value } : prev
                                    )
                                  }
                                />
                                <Input
                                  className="w-36"
                                  placeholder={t('facts.table.source')}
                                  value={editing.source}
                                  onChange={(e) =>
                                    setEditing((prev) =>
                                      prev ? { ...prev, source: e.target.value } : prev
                                    )
                                  }
                                />
                                <Input
                                  className="w-48"
                                  placeholder={t('facts.table.tags')}
                                  value={editing.tags}
                                  onChange={(e) =>
                                    setEditing((prev) =>
                                      prev ? { ...prev, tags: e.target.value } : prev
                                    )
                                  }
                                />
                                <Input
                                  className="w-28"
                                  placeholder={t('facts.table.confidence')}
                                  value={editing.confidence}
                                  onChange={(e) =>
                                    setEditing((prev) =>
                                      prev ? { ...prev, confidence: e.target.value } : prev
                                    )
                                  }
                                />
                              </div>
                              {saveError && (
                                <p className="font-mono text-xs text-destructive">{saveError}</p>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            <div className="flex flex-col gap-1">
                              <Button
                                size="sm"
                                onClick={saveEdit}
                                disabled={saving}
                                className="border border-black bg-primary text-white shadow-sw-xs hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all"
                              >
                                {saving ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  t('facts.save')
                                )}
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={cancelEdit}
                                className="border border-black"
                              >
                                {t('facts.cancel')}
                              </Button>
                            </div>
                          </td>
                        </>
                      ) : (
                        // ── Read-only row ────────────────────────────────────
                        <>
                          <td className="border-r border-black px-4 py-3 align-top">
                            <span className="leading-snug">{fact.statement}</span>
                            <p className="mt-1 font-mono text-xs text-ink-soft">{fact.fact_id}</p>
                          </td>
                          <td className="border-r border-black px-4 py-3 align-top font-mono text-xs text-ink-soft">
                            {fact.context ?? '—'}
                          </td>
                          <td className="border-r border-black px-4 py-3 align-top font-mono text-xs text-ink-soft">
                            {fact.source ?? '—'}
                          </td>
                          <td className="border-r border-black px-4 py-3 align-top">
                            <div className="flex flex-wrap gap-1">
                              {fact.tags_json.map((tag) => (
                                <span
                                  key={tag}
                                  className="border border-black px-1.5 py-0.5 font-mono text-xs"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="border-r border-black px-4 py-3 align-top font-mono text-xs">
                            {fact.confidence}
                          </td>
                          <td className="px-4 py-3 align-top">
                            <div className="flex gap-2">
                              <button
                                type="button"
                                onClick={() => startEdit(fact)}
                                aria-label={t('facts.edit')}
                                className="flex h-7 w-7 items-center justify-center border border-black hover:bg-secondary transition-colors"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() => setDeleteTarget(fact.fact_id)}
                                aria-label={t('facts.delete')}
                                className="flex h-7 w-7 items-center justify-center border border-black text-destructive hover:bg-red-50 transition-colors"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ── Delete Confirm ─────────────────────────────────────────────────── */}
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setDeleteError(null);
          }
        }}
        title={t('facts.deleteConfirm')}
        description={t('facts.deleteConfirm')}
        errorMessage={deleteError ?? undefined}
        confirmLabel={t('facts.delete')}
        variant="danger"
        closeOnConfirm={false}
        onConfirm={confirmDelete}
      />

      {/* ── Import Modal ──────────────────────────────────────────────────── */}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="max-w-2xl p-0 gap-0">
          <DialogHeader className="border-b border-black p-6">
            <DialogTitle className="font-serif text-2xl uppercase tracking-tight">
              {t('facts.importModal.title')}
            </DialogTitle>
            <DialogDescription className="font-mono text-xs text-ink-soft mt-1">
              {t('facts.importModal.selectResume')}
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[60vh] overflow-y-auto p-6">
            {importLoading && importResults.length === 0 ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : importError && importResults.length === 0 ? (
              <p className="font-mono text-sm text-destructive">{importError}</p>
            ) : importResults.length === 0 ? (
              // Resume selection step
              importResumes.length === 0 ? (
                <p className="font-mono text-sm text-ink-soft">
                  {t('facts.importModal.noResumes')}
                </p>
              ) : (
                <div className="flex flex-col gap-2">
                  {importResumes.map((r) => (
                    <label
                      key={r.resume_id}
                      className="flex cursor-pointer items-center gap-3 border border-black p-3 hover:bg-secondary transition-colors"
                    >
                      <input
                        type="radio"
                        name="import-resume"
                        value={r.resume_id}
                        checked={importSelectedId === r.resume_id}
                        onChange={() => setImportSelectedId(r.resume_id)}
                        className="h-4 w-4 border-black accent-primary"
                      />
                      <span className="font-mono text-sm">
                        {r.title ?? r.filename ?? r.resume_id}
                      </span>
                    </label>
                  ))}
                </div>
              )
            ) : (
              // Results step — three groups
              <div className="flex flex-col gap-4">
                {importError && <p className="font-mono text-sm text-destructive">{importError}</p>}

                {/* New group — Signal Green */}
                {importResults.filter((r) => r.group === 'new').length > 0 && (
                  <div>
                    <p className="mb-2 border-l-4 border-[#15803D] pl-2 font-mono text-xs uppercase tracking-wider text-[#15803D]">
                      {t('facts.importModal.groupNew')} (
                      {importResults.filter((r) => r.group === 'new').length})
                    </p>
                    <div className="flex flex-col gap-1">
                      {importResults
                        .filter((r) => r.group === 'new')
                        .map((r) => (
                          <div key={r.fact_id} className="border border-[#15803D] p-3">
                            <p className="text-sm leading-snug">{r.statement}</p>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* Near-duplicate group — Alert Orange */}
                {importResults.filter((r) => r.group === 'duplicate').length > 0 && (
                  <div>
                    <p className="mb-2 border-l-4 border-[#F97316] pl-2 font-mono text-xs uppercase tracking-wider text-[#F97316]">
                      {t('facts.importModal.groupDuplicate')} (
                      {importResults.filter((r) => r.group === 'duplicate').length})
                    </p>
                    <div className="flex flex-col gap-1">
                      {importResults
                        .filter((r) => r.group === 'duplicate')
                        .map((r) => (
                          <div key={r.fact_id} className="border border-[#F97316] p-3">
                            <p className="text-sm leading-snug">{r.statement}</p>
                            {r.existing_statement && (
                              <p className="mt-1 font-mono text-xs text-ink-soft">
                                {t('facts.importModal.existingFact')}
                                {r.existing_statement}
                              </p>
                            )}
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* Variant group — Hyper Blue (checkboxes to persist to blocks) */}
                {importResults.filter((r) => r.group === 'variant_of').length > 0 && (
                  <div>
                    <p className="mb-2 border-l-4 border-[#1D4ED8] pl-2 font-mono text-xs uppercase tracking-wider text-[#1D4ED8]">
                      {t('facts.importModal.groupVariant')} (
                      {importResults.filter((r) => r.group === 'variant_of').length})
                    </p>
                    <div className="flex flex-col gap-1">
                      {importResults
                        .filter((r) => r.group === 'variant_of')
                        .map((r) => (
                          <label
                            key={r.fact_id}
                            className="flex cursor-pointer items-start gap-3 border border-[#1D4ED8] p-3 hover:bg-secondary transition-colors"
                          >
                            <input
                              type="checkbox"
                              checked={selectedVariants.has(r.fact_id)}
                              onChange={() => toggleVariant(r.fact_id)}
                              className="mt-1 h-4 w-4 border-black accent-primary"
                            />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm leading-snug">{r.statement}</p>
                              {r.existing_statement && (
                                <p className="mt-1 font-mono text-xs text-ink-soft">
                                  {t('facts.importModal.existingFact')}
                                  {r.existing_statement}
                                </p>
                              )}
                            </div>
                          </label>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {!importLoading && (
            <DialogFooter className="border-t border-black p-4 flex-row justify-end gap-3 bg-secondary">
              <Button
                variant="outline"
                onClick={() => setImportOpen(false)}
                className="border border-black"
              >
                {t('facts.cancel')}
              </Button>
              {importResults.length === 0 ? (
                <Button
                  onClick={runImport}
                  disabled={!importSelectedId || importResumes.length === 0}
                  className="border border-black bg-primary text-white shadow-sw-sm hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all"
                >
                  {t('facts.importModal.importing')}
                </Button>
              ) : (
                <Button
                  onClick={handleConfirmImport}
                  disabled={
                    importConfirming ||
                    (importResults.filter((r) => r.group === 'new').length === 0 &&
                      selectedVariants.size === 0)
                  }
                  className="border border-black bg-primary text-white shadow-sw-sm hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all"
                >
                  {importConfirming ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    t('facts.importModal.confirmImport')
                  )}
                </Button>
              )}
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Extract Modal ──────────────────────────────────────────────────── */}
      <Dialog open={extractOpen} onOpenChange={setExtractOpen}>
        <DialogContent className="max-w-2xl p-0 gap-0">
          <DialogHeader className="border-b border-black p-6">
            <DialogTitle className="font-serif text-2xl uppercase tracking-tight">
              {t('facts.extractModal.title')}
            </DialogTitle>
            <DialogDescription className="font-mono text-xs text-ink-soft mt-1">
              {t('facts.extractModal.description')}
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-[60vh] overflow-y-auto p-6">
            {extracting ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : extractError ? (
              // Empty-state 1: no master resume, or LLM/parse failure
              <p className="font-mono text-sm text-destructive">{extractError}</p>
            ) : candidates.length === 0 ? (
              // Empty-state 2: LLM found no facts in the resume (valid empty response)
              <p className="font-mono text-sm text-ink-soft">
                {t('facts.extractModal.noFactsFound')}
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {/* Empty-state 3: every candidate is a duplicate of an existing fact */}
                {candidates.every((c) => c.duplicate_of) && (
                  <p className="mb-2 font-mono text-xs text-ink-soft border-l-4 border-warning pl-2">
                    {t('facts.extractModal.allDuplicates')}
                  </p>
                )}
                {candidates.map((c) => (
                  <label
                    key={c.fact_id}
                    className="flex cursor-pointer items-start gap-3 border border-black p-3 hover:bg-secondary transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={selectedCandidates.has(c.fact_id)}
                      onChange={() => toggleCandidate(c.fact_id)}
                      className="mt-1 h-4 w-4 border-black accent-primary"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm leading-snug">{c.statement}</p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {c.tags_json.map((tag) => (
                          <span
                            key={tag}
                            className="border border-black px-1.5 py-0.5 font-mono text-xs"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                      {c.duplicate_of && (
                        <p className="mt-1 font-mono text-xs text-warning">
                          {t('facts.extractModal.duplicate')}
                        </p>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>

          {!extracting && !extractError && candidates.length > 0 && (
            <DialogFooter className="border-t border-black p-4 flex-row justify-end gap-3 bg-secondary">
              <Button
                variant="outline"
                onClick={() => setExtractOpen(false)}
                className="border border-black"
              >
                {t('facts.cancel')}
              </Button>
              <Button
                onClick={handleConfirmSelected}
                disabled={confirming || selectedCandidates.size === 0}
                className="border border-black bg-primary text-white shadow-sw-sm hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none transition-all"
              >
                {confirming ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  t('facts.extractModal.confirmSelected')
                )}
              </Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
