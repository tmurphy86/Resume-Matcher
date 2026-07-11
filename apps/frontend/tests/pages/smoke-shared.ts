/**
 * Shared mock data for page smoke tests (BUG-004).
 * All mocked API payloads use realistic shapes that match what the backend actually returns.
 */

import { vi } from 'vitest';

// ---------------------------------------------------------------------------
// Common mock setup — call in beforeEach/top-level vi.mock
// ---------------------------------------------------------------------------

export const mockT = (key: string) => key;

export const mockUseTranslations = () => ({ t: mockT, messages: {}, locale: 'en' });

// Minimal Application shape (considering card with null resume_id)
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

// Normal applied card
export const mockAppliedApp = {
  ...mockConsideringApp,
  application_id: 'app-applied',
  resume_id: 'res-master',
  status: 'applied' as const,
  status_history: [{ status: 'applied', at: '2026-01-01T00:00:00Z' }],
};

// ApplicationColumns response
export const mockColumns = {
  considering: [mockConsideringApp],
  saved: [],
  applied: [mockAppliedApp],
  response: [],
  interview: [],
  offer: [],
  accepted: [],
  rejected: [],
};

// Minimal resume shape
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

// Minimal career report
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
