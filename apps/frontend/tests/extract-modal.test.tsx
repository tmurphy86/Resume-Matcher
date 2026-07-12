/**
 * BUG-006 regression: extract modal empty states must render explicitly.
 *
 * Post-mortem: BUG-003 (commit 108907f) added 4 service-layer tests that mock
 * `complete_json` and verify `extract_candidate_facts()` handles LLM response
 * shapes correctly at the Python level. Those tests pass because the service
 * logic is correct. However, they exercise the BACKEND SERVICE LAYER only —
 * the frontend component is never rendered, no button is clicked, and the
 * three empty-state branches in the modal are never exercised.
 *
 * The browser stays broken because the component render path
 *   openExtract() → setCandidates([]) / setExtractError() → render branch
 * was untested. Any regression in the JSX conditions silently produces a blank
 * modal instead of one of the three explicit states.
 *
 * These tests live at the FRONTEND COMPONENT layer — the layer the browser
 * actually exercises. Each test:
 *   1. Renders <FactsPage />
 *   2. Clicks "Extract from master"
 *   3. Waits for async state to settle
 *   4. Asserts the correct empty-state message is visible
 *
 * A test that asserts `facts.extractModal.noFactsFound` would fail on
 * pre-BUG-003 code (which rendered `facts.empty` instead) — satisfying the
 * "regression test that fails pre-fix" requirement.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import type React from 'react';

// ── Hoisted mock factories (must precede vi.mock calls) ─────────────────────
// vi.hoisted() runs before module hoisting so these refs are usable inside
// vi.mock() factories, which are also hoisted to the top of the file.
const { mockListFacts, mockExtractFacts, mockFetchResumeList } = vi.hoisted(() => ({
  mockListFacts: vi.fn(),
  mockExtractFacts: vi.fn(),
  mockFetchResumeList: vi.fn(),
}));

// ── i18n mock — t() returns the key so assertions can match key strings ──────
vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({ t: (k: string) => k, messages: {}, locale: 'en' }),
}));

// ── Facts API mock ────────────────────────────────────────────────────────────
vi.mock('@/lib/api/facts', () => ({
  listFacts: mockListFacts,
  extractFacts: mockExtractFacts,
  confirmFacts: vi.fn().mockResolvedValue([]),
  confirmVariant: vi.fn().mockResolvedValue({ status: 'ok', matched_blocks: false }),
  importResumeFacts: vi.fn().mockResolvedValue([]),
  updateFact: vi.fn(),
  deleteFact: vi.fn(),
}));

// ── Resume API mock ───────────────────────────────────────────────────────────
vi.mock('@/lib/api/resume', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/resume')>();
  return { ...actual, fetchResumeList: mockFetchResumeList };
});

// ── next/link stub ────────────────────────────────────────────────────────────
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// ── Test helpers ──────────────────────────────────────────────────────────────

const MASTER_RESUME = {
  resume_id: 'master-r1',
  is_master: true,
  title: 'Master Resume',
  processing_status: 'ready',
};

/** Minimal Fact candidate with a duplicate_of annotation. */
function makeCandidate(
  overrides: Partial<{
    fact_id: string;
    statement: string;
    duplicate_of: string | null;
  }> = {}
) {
  return {
    fact_id: overrides.fact_id ?? 'cand-uuid-1',
    statement: overrides.statement ?? 'Led a team of 8 engineers',
    context: null,
    source: 'workExperience',
    metrics_json: {},
    tags_json: ['leadership'],
    confidence: 'candidate',
    created_at: '',
    updated_at: '',
    duplicate_of: overrides.duplicate_of ?? null,
  };
}

// ── Test suite ────────────────────────────────────────────────────────────────

describe('Extract modal — empty states (BUG-006 regression)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: facts list empty, resume list has a master.
    mockListFacts.mockResolvedValue([]);
    mockFetchResumeList.mockResolvedValue([MASTER_RESUME]);
  });

  // ---------------------------------------------------------------------------
  // Empty-state 1a: No master resume
  // ---------------------------------------------------------------------------
  it('shows noMasterResume message when no master resume exists', async () => {
    // No master resume in the list → early return with extractError.
    mockFetchResumeList.mockResolvedValue([
      { resume_id: 'r-1', is_master: false, title: 'Old Resume', processing_status: 'ready' },
    ]);

    render(<FactsPage />);
    fireEvent.click(await screen.findByText('facts.extractButton'));

    await waitFor(() => {
      expect(screen.getByText('facts.extractModal.noMasterResume')).toBeInTheDocument();
    });

    // The "no facts found" and "all duplicates" messages must NOT appear.
    expect(screen.queryByText('facts.extractModal.noFactsFound')).not.toBeInTheDocument();
    expect(screen.queryByText('facts.extractModal.allDuplicates')).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Empty-state 1b: LLM/parse failure
  // ---------------------------------------------------------------------------
  it('shows extractFailed message when extractFacts throws', async () => {
    // Backend returns 500 → extractFacts throws → catch sets extractError.
    mockExtractFacts.mockRejectedValue(new Error('Fact extraction failed. Please try again.'));

    render(<FactsPage />);
    fireEvent.click(await screen.findByText('facts.extractButton'));

    await waitFor(() => {
      expect(screen.getByText('facts.errors.extractFailed')).toBeInTheDocument();
    });

    expect(screen.queryByText('facts.extractModal.noFactsFound')).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Empty-state 2: LLM returned no facts
  // ---------------------------------------------------------------------------
  it('shows noFactsFound when extraction returns an empty list', async () => {
    // Valid LLM response {"facts": []} → service returns [] → component shows
    // noFactsFound inside the modal, NOT facts.empty (pre-BUG-003 behaviour).
    mockExtractFacts.mockResolvedValue([]);

    render(<FactsPage />);
    fireEvent.click(await screen.findByText('facts.extractButton'));

    await waitFor(() => {
      expect(screen.getByText('facts.extractModal.noFactsFound')).toBeInTheDocument();
    });

    // Guard: the OLD pre-BUG-003 message must NOT appear *inside the modal*.
    // The main facts list may legitimately show facts.empty when empty, but the
    // modal must never fall back to that generic message when extraction returns
    // an empty array — it must show the specific noFactsFound message instead.
    // If someone reverts page.tsx to use t('facts.empty') inside the modal,
    // this assertion detects the regression at the component layer.
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).queryByText('facts.empty')).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Empty-state 3: All candidates are duplicates
  // ---------------------------------------------------------------------------
  it('shows allDuplicates banner when every candidate has a duplicate_of', async () => {
    mockExtractFacts.mockResolvedValue([
      makeCandidate({ fact_id: 'c-1', duplicate_of: 'existing-fact-1' }),
      makeCandidate({
        fact_id: 'c-2',
        statement: 'Improved API latency by 40%',
        duplicate_of: 'existing-fact-2',
      }),
    ]);

    render(<FactsPage />);
    fireEvent.click(await screen.findByText('facts.extractButton'));

    await waitFor(() => {
      expect(screen.getByText('facts.extractModal.allDuplicates')).toBeInTheDocument();
    });

    // Candidate list is still rendered (not hidden when all-duplicates).
    expect(screen.getByText('Led a team of 8 engineers')).toBeInTheDocument();
    expect(screen.getByText('Improved API latency by 40%')).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Happy path: non-duplicate candidates render without any empty-state banner
  // ---------------------------------------------------------------------------
  it('renders candidate list with no empty-state when extraction succeeds', async () => {
    mockExtractFacts.mockResolvedValue([
      makeCandidate({
        fact_id: 'c-1',
        statement: 'Shipped payment gateway MVP',
        duplicate_of: null,
      }),
    ]);

    render(<FactsPage />);
    fireEvent.click(await screen.findByText('facts.extractButton'));

    await waitFor(() => {
      expect(screen.getByText('Shipped payment gateway MVP')).toBeInTheDocument();
    });

    // None of the empty-state messages should appear in the happy path.
    expect(screen.queryByText('facts.extractModal.noFactsFound')).not.toBeInTheDocument();
    expect(screen.queryByText('facts.extractModal.allDuplicates')).not.toBeInTheDocument();
    expect(screen.queryByText('facts.extractModal.noMasterResume')).not.toBeInTheDocument();
    expect(screen.queryByText('facts.errors.extractFailed')).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Silent-empty guard
  // ---------------------------------------------------------------------------
  it('silent-empty is impossible: spinner OR error OR noFactsFound OR candidates always shows', async () => {
    // Use the empty-list scenario (most likely to silently produce nothing).
    mockExtractFacts.mockResolvedValue([]);

    render(<FactsPage />);
    fireEvent.click(await screen.findByText('facts.extractButton'));

    // After extraction settles, one of the three terminal states must appear.
    await waitFor(() => {
      const hasError =
        !!screen.queryByText('facts.extractModal.noMasterResume') ||
        !!screen.queryByText('facts.errors.extractFailed');
      const hasEmptyState = !!screen.queryByText('facts.extractModal.noFactsFound');
      const hasCandidates = !!screen.queryByText('facts.extractModal.allDuplicates');

      expect(hasError || hasEmptyState || hasCandidates).toBe(true);
    });
  });
});

// Deferred import so vi.mock hoisting fires first.
import FactsPage from '@/app/(default)/facts/page';
