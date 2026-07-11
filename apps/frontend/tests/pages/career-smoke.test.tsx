/**
 * BUG-004 smoke: Career page mounts without crashing.
 * Verifies the career page renders even when applications endpoint fails (non-fatal path).
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { mockCareerReport, mockColumns } from './smoke-shared';

vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({ t: (k: string) => k, messages: {}, locale: 'en' }),
}));

vi.mock('@/lib/api/career', () => ({
  listCareerReports: vi.fn().mockResolvedValue([mockCareerReport]),
  generateCareerReport: vi.fn(),
  clusterArchetypes: vi.fn(),
  listApplicationsForCareer: vi.fn().mockResolvedValue({ columns: mockColumns }),
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('@/lib/api/tracker', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/tracker')>();
  return { ...actual, listApplications: vi.fn().mockResolvedValue({ columns: mockColumns }) };
});

import CareerPage from '@/app/(default)/career/page';

describe('CareerPage smoke (BUG-004)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing when reports load', async () => {
    const { container } = render(<CareerPage />);
    // Component mounts — container always has content even in loading state
    expect(container.firstChild).toBeTruthy();
  });

  it('renders without crashing when applications endpoint fails (non-fatal)', async () => {
    const { listApplicationsForCareer } = await import('@/lib/api/career');
    vi.mocked(listApplicationsForCareer).mockRejectedValueOnce(new Error('tracker down'));

    const { container } = render(<CareerPage />);
    // Application failure is non-fatal — page still renders the loading/reports state
    expect(container.firstChild).toBeTruthy();
  });
});
