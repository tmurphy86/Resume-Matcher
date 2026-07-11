/**
 * BUG-004 smoke: Tailor page mounts without crashing.
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
    improveResumePreview: vi.fn(),
    improveResumeConfirm: vi.fn(),
    fetchJobDescription: vi.fn().mockResolvedValue(null),
  };
});

vi.mock('@/lib/context/status-cache', () => ({
  useStatusCache: () => ({
    resumeCount: 1,
    hasMasterResume: true,
    isLlmHealthy: true,
    incrementResumes: vi.fn(),
    decrementResumes: vi.fn(),
    setHasMasterResume: vi.fn(),
    dbStatus: null,
    llmStatus: null,
  }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
  usePathname: () => '/tailor',
}));

vi.mock('@/components/common/resume_previewer_context', () => ({
  useResumePreview: () => ({ setImprovedData: vi.fn(), improvedData: null }),
  ResumePreviewProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

import TailorPage from '@/app/(default)/tailor/page';

describe('TailorPage smoke (BUG-004)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing on initial load', () => {
    const { container } = render(<TailorPage />);
    expect(container.firstChild).toBeTruthy();
  });
});
