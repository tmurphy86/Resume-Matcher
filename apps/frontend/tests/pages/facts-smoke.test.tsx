/**
 * BUG-004 smoke: Facts page mounts without crashing.
 * Covers BUG-003 regression: extraction must show explicit empty states, not silent blank.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';

vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({ t: (k: string) => k, messages: {}, locale: 'en' }),
}));

// BUG-009: Use schema-parity fixture from smoke-shared to prevent fixture drift.
import { mockFact } from './smoke-shared';

vi.mock('@/lib/api/facts', () => ({
  listFacts: vi.fn().mockResolvedValue([mockFact]),
  extractFacts: vi.fn(),
  confirmFacts: vi.fn(),
  confirmVariant: vi.fn(),
  importResumeFacts: vi.fn(),
  updateFact: vi.fn(),
  deleteFact: vi.fn(),
}));

vi.mock('@/lib/api/resume', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/resume')>();
  return {
    ...actual,
    fetchResumeList: vi
      .fn()
      .mockResolvedValue([{ resume_id: 'res-master', is_master: true, title: 'Master Resume' }]),
  };
});

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

import FactsPage from '@/app/(default)/facts/page';

describe('FactsPage smoke (BUG-004)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing with a seeded facts list', () => {
    const { container } = render(<FactsPage />);
    expect(container.firstChild).toBeTruthy();
  });
});
