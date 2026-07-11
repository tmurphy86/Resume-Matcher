/**
 * BUG-004 smoke: Dashboard page mounts without crashing.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { mockResume } from './smoke-shared';

vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({ t: (k: string) => k, messages: {}, locale: 'en' }),
}));

vi.mock('@/lib/api/resume', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/resume')>();
  return {
    ...actual,
    fetchResumeList: vi.fn().mockResolvedValue([mockResume]),
    fetchResume: vi
      .fn()
      .mockResolvedValue({ resume: mockResume, rawContent: '', processedData: null }),
    fetchJobDescription: vi.fn().mockResolvedValue(null),
    deleteResume: vi.fn(),
    retryProcessing: vi.fn(),
  };
});

vi.mock('@/lib/context/status-cache', () => ({
  useStatusCache: () => ({
    resumeCount: 1,
    hasMasterResume: true,
    incrementResumes: vi.fn(),
    decrementResumes: vi.fn(),
    setHasMasterResume: vi.fn(),
    dbStatus: null,
    llmStatus: null,
    isLlmHealthy: true,
  }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => '/dashboard',
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

import DashboardPage from '@/app/(default)/dashboard/page';

describe('DashboardPage smoke (BUG-004)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing with a seeded resume list', () => {
    const { container } = render(<DashboardPage />);
    expect(container.firstChild).toBeTruthy();
  });
});
