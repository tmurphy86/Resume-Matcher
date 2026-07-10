import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DiffPreviewModal } from '@/components/tailor/diff-preview-modal';
import type {
  ResumeDiffSummary,
  ResumeFieldDiff,
} from '@/components/common/resume_previewer_context';

vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({
    t: (key: string) => key,
  }),
}));

const diffSummary: ResumeDiffSummary = {
  total_changes: 2,
  skills_added: 1,
  skills_removed: 0,
  descriptions_modified: 1,
  certifications_added: 0,
  high_risk_changes: 1,
};

const detailedChanges: ResumeFieldDiff[] = [
  {
    field_path: 'summary',
    field_type: 'summary',
    change_type: 'modified',
    original_value: 'old summary',
    new_value: 'new summary',
    confidence: 'medium',
  },
  {
    field_path: 'additional.technicalSkills',
    field_type: 'skill',
    change_type: 'added',
    new_value: 'Go',
    confidence: 'high',
  },
];

describe('DiffPreviewModal', () => {
  it('renders fallback dialog when diff data is missing', () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    render(<DiffPreviewModal isOpen onClose={onClose} onReject={vi.fn()} onConfirm={onConfirm} />);

    expect(screen.getByText('tailor.missingDiffDialog.title')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'tailor.missingDiffDialog.confirmLabel' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('shows warning banner and renders high-risk icon only for added high changes', () => {
    render(
      <DiffPreviewModal
        isOpen
        onClose={vi.fn()}
        onReject={vi.fn()}
        onConfirm={vi.fn()}
        diffSummary={diffSummary}
        detailedChanges={detailedChanges}
      />
    );

    expect(screen.getByText('tailor.diffModal.warningTitle', { exact: false })).toBeInTheDocument();
    // Dialog uses createPortal to document.body, so the test's `container`
    // wrapper does not contain the rendered dialog content. Query
    // document.body directly to find the icons rendered inside the portal.
    const alertIcons = document.body.querySelectorAll('.lucide-triangle-alert');
    expect(alertIcons.length).toBe(2);
  });

  it('toggles section visibility on header click', () => {
    render(
      <DiffPreviewModal
        isOpen
        onClose={vi.fn()}
        onReject={vi.fn()}
        onConfirm={vi.fn()}
        diffSummary={diffSummary}
        detailedChanges={detailedChanges}
      />
    );

    expect(screen.getByText('new summary')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /tailor\.diffModal\.summaryChanges/i }));
    expect(screen.queryByText('new summary')).not.toBeInTheDocument();
  });

  it('fires confirm and reject handlers', () => {
    const onConfirm = vi.fn();
    const onReject = vi.fn();

    render(
      <DiffPreviewModal
        isOpen
        onClose={vi.fn()}
        onReject={onReject}
        onConfirm={onConfirm}
        diffSummary={diffSummary}
        detailedChanges={detailedChanges}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'tailor.diffModal.confirmButton' }));
    fireEvent.click(screen.getByRole('button', { name: 'tailor.diffModal.rejectButton' }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onReject).toHaveBeenCalledTimes(1);
  });

  // ── "Save as variant" panel (ChangeItem) ────────────────────────

  const descChange: ResumeFieldDiff = {
    field_path: 'workExperience[0].description[0]',
    field_type: 'description',
    change_type: 'modified',
    original_value: 'Old bullet',
    new_value: 'New bullet text with keyword',
    confidence: 'medium',
  };

  it('shows BookmarkPlus button for description changes when onSaveAsVariant is provided', () => {
    render(
      <DiffPreviewModal
        isOpen
        onClose={vi.fn()}
        onReject={vi.fn()}
        onConfirm={vi.fn()}
        diffSummary={{ ...diffSummary, descriptions_modified: 1 }}
        detailedChanges={[descChange]}
        onSaveAsVariant={vi.fn()}
      />
    );

    // The BookmarkPlus button is rendered via aria-label
    expect(
      screen.getByRole('button', { name: 'tailor.variants.saveAsVariant' })
    ).toBeInTheDocument();
  });

  it('does not show BookmarkPlus button when onSaveAsVariant is not provided', () => {
    render(
      <DiffPreviewModal
        isOpen
        onClose={vi.fn()}
        onReject={vi.fn()}
        onConfirm={vi.fn()}
        diffSummary={{ ...diffSummary, descriptions_modified: 1 }}
        detailedChanges={[descChange]}
        // onSaveAsVariant deliberately omitted
      />
    );

    expect(
      screen.queryByRole('button', { name: 'tailor.variants.saveAsVariant' })
    ).not.toBeInTheDocument();
  });

  it('opens save panel and calls onSaveAsVariant with parsed tags on save', async () => {
    const onSaveAsVariant = vi.fn().mockResolvedValue(undefined);

    render(
      <DiffPreviewModal
        isOpen
        onClose={vi.fn()}
        onReject={vi.fn()}
        onConfirm={vi.fn()}
        diffSummary={{ ...diffSummary, descriptions_modified: 1 }}
        detailedChanges={[descChange]}
        onSaveAsVariant={onSaveAsVariant}
      />
    );

    // Click the BookmarkPlus button to open the inline save panel
    fireEvent.click(screen.getByRole('button', { name: 'tailor.variants.saveAsVariant' }));

    // Tag input should now be visible
    const tagInput = screen.getByRole('textbox', { name: 'tailor.variants.tagLabel' });
    expect(tagInput).toBeInTheDocument();

    // Type two comma-separated tags
    fireEvent.change(tagInput, { target: { value: 'gcp, fintech' } });

    // Click Save
    fireEvent.click(screen.getByRole('button', { name: 'tailor.variants.saveButton' }));

    await waitFor(() => expect(onSaveAsVariant).toHaveBeenCalledTimes(1));
    // The callback receives (change, tagList) — here it's wrapped so the modal
    // calls onSaveAsVariant(change, tags) internally; ChangeItem calls the
    // prop as onSaveAsVariant(tagList)
    expect(onSaveAsVariant).toHaveBeenCalledWith(descChange, ['gcp', 'fintech']);
  });

  it('shows saved confirmation after successful save and hides BookmarkPlus', async () => {
    const onSaveAsVariant = vi.fn().mockResolvedValue(undefined);

    render(
      <DiffPreviewModal
        isOpen
        onClose={vi.fn()}
        onReject={vi.fn()}
        onConfirm={vi.fn()}
        diffSummary={{ ...diffSummary, descriptions_modified: 1 }}
        detailedChanges={[descChange]}
        onSaveAsVariant={onSaveAsVariant}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: 'tailor.variants.saveAsVariant' }));
    fireEvent.click(screen.getByRole('button', { name: 'tailor.variants.saveButton' }));

    await waitFor(() => expect(screen.getByText('tailor.variants.saved')).toBeInTheDocument());
    // BookmarkPlus button should be gone after a successful save
    expect(
      screen.queryByRole('button', { name: 'tailor.variants.saveAsVariant' })
    ).not.toBeInTheDocument();
  });
});
