/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, beforeEach, vi, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// Mock the tracker API
vi.mock('@/lib/api/tracker', () => ({
  getApplicationDetail: vi.fn(),
  getInterestDimensions: vi.fn(),
  updateApplication: vi.fn(),
  generateApplicationEmail: vi.fn(),
}));

// Mock the router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

// Mock translations
vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({
    t: (key: string) => key,
  }),
}));

// Import after mocks
import { CardDetailModal } from '@/components/tracker/card-detail-modal';
import * as trackerApi from '@/lib/api/tracker';

describe('CardDetailModal - Email Generation', () => {
  const mockDetail = {
    application_id: 'app-123',
    job_id: 'job-456',
    resume_id: 'resume-789',
    master_resume_id: null,
    status: 'interview',
    company: 'TechCorp',
    role: 'Senior Engineer',
    applied_at: '2024-01-15T00:00:00',
    notes: 'Good fit',
    position: 0,
    interest_signals: [],
    created_at: '2024-01-15T00:00:00',
    updated_at: '2024-01-15T00:00:00',
    job_content: 'We are looking for a senior engineer...',
    resume: { name: 'John Doe' },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (trackerApi.getApplicationDetail as any).mockResolvedValue(mockDetail);
    (trackerApi.getInterestDimensions as any).mockResolvedValue([]);
  });

  it('should show email generation buttons for interview status', async () => {
    render(
      <CardDetailModal
        applicationId="app-123"
        open={true}
        onOpenChange={() => {}}
        onUpdated={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('tracker.modal.draftThankYou')).toBeInTheDocument();
      expect(screen.getByText('tracker.modal.draftFollowUp')).toBeInTheDocument();
    });
  });

  it('should generate thank-you email on button click', async () => {
    const mockEmail = 'Subject: Thank you\n---\nThank you email body';
    (trackerApi.generateApplicationEmail as any).mockResolvedValue({
      content: mockEmail,
      message: 'Email generated',
    });

    render(
      <CardDetailModal
        applicationId="app-123"
        open={true}
        onOpenChange={() => {}}
        onUpdated={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('tracker.modal.draftThankYou')).toBeInTheDocument();
    });

    const thankYouButton = screen.getByText('tracker.modal.draftThankYou');
    fireEvent.click(thankYouButton);

    await waitFor(() => {
      expect(trackerApi.generateApplicationEmail).toHaveBeenCalledWith('app-123', 'thank_you');
    });
  });

  it('should generate follow-up email on button click', async () => {
    const mockEmail = 'Subject: Following up\n---\nFollow-up email body';
    (trackerApi.generateApplicationEmail as any).mockResolvedValue({
      content: mockEmail,
      message: 'Email generated',
    });

    render(
      <CardDetailModal
        applicationId="app-123"
        open={true}
        onOpenChange={() => {}}
        onUpdated={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('tracker.modal.draftFollowUp')).toBeInTheDocument();
    });

    const followUpButton = screen.getByText('tracker.modal.draftFollowUp');
    fireEvent.click(followUpButton);

    await waitFor(() => {
      expect(trackerApi.generateApplicationEmail).toHaveBeenCalledWith('app-123', 'follow_up');
    });
  });

  it('should not show email buttons for non-eligible statuses', async () => {
    const ineligibleDetail = { ...mockDetail, status: 'applied' };
    (trackerApi.getApplicationDetail as any).mockResolvedValue(ineligibleDetail);

    render(
      <CardDetailModal
        applicationId="app-123"
        open={true}
        onOpenChange={() => {}}
        onUpdated={() => {}}
      />
    );

    await waitFor(() => {
      // Wait for modal to load
      expect(trackerApi.getApplicationDetail).toHaveBeenCalled();
    });

    // Email buttons should not be visible
    expect(screen.queryByText('tracker.modal.draftThankYou')).not.toBeInTheDocument();
    expect(screen.queryByText('tracker.modal.draftFollowUp')).not.toBeInTheDocument();
  });

  it('should handle email generation error gracefully', async () => {
    (trackerApi.generateApplicationEmail as any).mockRejectedValue(new Error('API error'));

    render(
      <CardDetailModal
        applicationId="app-123"
        open={true}
        onOpenChange={() => {}}
        onUpdated={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('tracker.modal.draftThankYou')).toBeInTheDocument();
    });

    const thankYouButton = screen.getByText('tracker.modal.draftThankYou');
    fireEvent.click(thankYouButton);

    await waitFor(() => {
      expect(screen.getByText('common.error')).toBeInTheDocument();
    });
  });

  it('should show loading state while generating email', async () => {
    let resolveGenerate: ((value: unknown) => void) | undefined;
    (trackerApi.generateApplicationEmail as any).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGenerate = resolve;
        })
    );

    render(
      <CardDetailModal
        applicationId="app-123"
        open={true}
        onOpenChange={() => {}}
        onUpdated={() => {}}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('tracker.modal.draftThankYou')).toBeInTheDocument();
    });

    const thankYouButton = screen.getByText('tracker.modal.draftThankYou');
    fireEvent.click(thankYouButton);

    await waitFor(() => {
      expect(screen.getByText('tracker.modal.generatingEmail')).toBeInTheDocument();
    });

    resolveGenerate({ content: 'Email content', message: 'Generated' });

    await waitFor(() => {
      expect(screen.queryByText('tracker.modal.generatingEmail')).not.toBeInTheDocument();
    });
  });
});
