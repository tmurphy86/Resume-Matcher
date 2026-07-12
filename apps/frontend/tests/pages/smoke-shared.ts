/**
 * Shared mock data for page smoke tests (BUG-004 / BUG-009).
 *
 * BUG-009: All mocked API payloads are derived from the actual backend Pydantic
 * schemas to prevent fixture drift. Each shape is documented with the Pydantic
 * class it mirrors.
 *
 * Rule (BUG-009): Any ticket adding or changing a backend response schema MUST
 * update the corresponding fixture here so smoke tests stay schema-parity. See
 * apps/frontend/tests/README.md for the enforcement rule.
 */

import { vi } from 'vitest';

// ---------------------------------------------------------------------------
// Common mock setup — call in beforeEach/top-level vi.mock
// ---------------------------------------------------------------------------

export const mockT = (key: string) => key;

export const mockUseTranslations = () => ({ t: mockT, messages: {}, locale: 'en' });

// ---------------------------------------------------------------------------
// Application shapes (mirrors ApplicationResponse in schemas/applications.py)
// ---------------------------------------------------------------------------

// Considering card — resume_id=NULL (RH-106 quick-capture shape).
// status_history=[] and interest_signals=[] represent post-migration state for
// rows that predate those columns (BUG-001 / pre-P3 shape after migration).
export const mockConsideringApp = {
  application_id: 'app-considering',
  job_id: 'job-1',
  resume_id: null,
  master_resume_id: null,
  status: 'considering' as const,
  company: 'Acme Corp',
  role: 'Engineer',
  applied_at: null,
  notes: null,
  position: 0,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  interest_signals: [],
  status_history: [],
};

// Normal applied card with status_history entry.
export const mockAppliedApp = {
  ...mockConsideringApp,
  application_id: 'app-applied',
  resume_id: 'res-master',
  status: 'applied' as const,
  status_history: [{ status: 'applied', at: '2026-01-01T00:00:00Z' }],
};

// ApplicationColumns response (ApplicationListResponse.columns)
export const mockColumns = {
  considering: [mockConsideringApp],
  saved: [],
  applied: [mockAppliedApp],
  no_response: [],
  response: [],
  interview: [],
  offer: [],
  accepted: [],
  rejected: [],
};

// ---------------------------------------------------------------------------
// Resume shape (mirrors ResumeListItem — the list endpoint response)
// ---------------------------------------------------------------------------

export const mockResume = {
  resume_id: 'res-master',
  filename: 'resume.pdf',
  is_master: true,
  parent_id: null,
  processing_status: 'ready',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  title: 'Senior Engineer',
};

// ---------------------------------------------------------------------------
// Career report shape (mirrors CareerReport model)
// ---------------------------------------------------------------------------

export const mockCareerReport = {
  id: 1,
  created_at: '2026-01-01T00:00:00Z',
  archetypes_json: [
    {
      name: 'Backend Engineer',
      description: 'Python APIs',
      jd_ids: ['job-1'],
      responsibilities: ['Build APIs'],
      attraction_score: 3.5,
      fit_score: 4.0,
      gaps: [],
      response_rate: 0.5,
      interview_rate: 0.25,
    },
  ],
  scores_json: [{ name: 'Backend Engineer', attraction: 3.5, fit: 4.0, gaps: [] }],
  advice_md: 'Focus on backend roles.',
  model_used: 'claude-haiku',
};

// ---------------------------------------------------------------------------
// Job shapes (mirrors JobSummary in schemas/models.py)
//
// BUG-009: Three historical shapes are represented to match the backend seed
// matrix. The frontend JobsPage must render all three without crashing.
// ---------------------------------------------------------------------------

// Modern job — all parsed fields populated (post-RH-303 shape).
export const mockJobSummaryModern = {
  job_id: 'job-modern',
  snippet: 'Backend Engineer at MegaCorp. Python, AWS, Kubernetes required.',
  created_at: '2026-01-01T00:00:00Z',
  company: 'MegaCorp',
  role: 'Backend Engineer',
  level: 'Senior',
  archetype: 'Backend Engineer',
};

// Pre-RH-303 job — no "parsed" key in metadata_json, all optional fields null.
// This is the shape that caused BUG-007 before defensive isinstance checks.
export const mockJobSummaryPreRH303 = {
  job_id: 'job-pre-rh303',
  snippet: 'Senior Python Engineer at TechCorp. Requirements: Python, FastAPI, 5yr.',
  created_at: '2025-06-01T00:00:00Z',
  company: null,
  role: null,
  level: null,
  archetype: null,
};

// Legacy job with corrupted metadata — non-string level coerced to null.
export const mockJobSummaryBadMetadata = {
  job_id: 'job-bad-metadata',
  snippet: 'Staff DevOps Engineer at InfraCo.',
  created_at: '2025-03-01T00:00:00Z',
  company: 'InfraCo',
  role: 'Staff DevOps',
  level: null, // was {"text": "Staff"} — coerced to null by isinstance guard
  archetype: null,
};

// ---------------------------------------------------------------------------
// Fact shape (mirrors FactResponse in schemas/facts.py)
// ---------------------------------------------------------------------------

export const mockFact = {
  fact_id: 'fact-1',
  statement: 'Led a team of 20 engineers at Acme.',
  context: 'work',
  source: 'master_resume',
  metrics_json: { team_size: 20 },
  tags_json: ['leadership'],
  confidence: 'verified',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  duplicate_of: null,
};
