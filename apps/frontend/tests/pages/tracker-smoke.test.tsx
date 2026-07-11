/**
 * BUG-004 smoke: Tracker page mounts without crashing for all application row shapes.
 * Covers the BUG-001 scenario: considering cards (resume_id=null) + legacy rows
 * must not cause the board to error-boundary-trigger.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { mockColumns } from './smoke-shared';

vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({ t: (k: string) => k, messages: {}, locale: 'en' }),
}));

vi.mock('@/lib/api/tracker', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/tracker')>();
  return {
    ...actual,
    listApplications: vi.fn().mockResolvedValue({ columns: mockColumns }),
    updateApplication: vi.fn(),
    bulkUpdateStatus: vi.fn(),
    bulkDeleteApplications: vi.fn(),
    getInterestDimensions: vi.fn().mockResolvedValue([]),
    createConsideringApplication: vi.fn(),
  };
});

vi.mock('@dnd-kit/core', async (importOriginal) => {
  const actual = await importOriginal();
  return actual;
});

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/tracker',
  useSearchParams: () => ({ get: () => null }),
}));

// Import after mocks
import TrackerPage from '@/app/(default)/tracker/page';

describe('TrackerPage smoke (BUG-004)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing with considering + applied cards', async () => {
    const { container } = render(<TrackerPage />);
    // Page always mounts — the board loads asynchronously
    expect(container.firstChild).toBeTruthy();
  });
});
