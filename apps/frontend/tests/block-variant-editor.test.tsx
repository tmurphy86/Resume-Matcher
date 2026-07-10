/**
 * Tests for BlockVariantEditor (RH-301).
 *
 * Design:
 *  - No real network calls (onSwitchVariant is always a vi.fn())
 *  - Canned BulletBlock fixtures — deterministic, fails when the component breaks
 *  - Locale is stubbed to return the key string so assertions are locale-independent
 */

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BlockVariantEditor } from '@/components/tailor/block-variant-editor';
import type { BlockSection } from '@/components/tailor/block-variant-editor';
import type { BulletBlock } from '@/components/dashboard/resume-component';

vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({
    t: (key: string, params?: Record<string, string>) => {
      if (params) {
        return Object.entries(params).reduce((s, [k, v]) => s.replace(`{${k}}`, v), key);
      }
      return key;
    },
  }),
}));

// ─── Fixtures ─────────────────────────────────────────────────────

const blockOneVariant: BulletBlock = {
  id: 'block-1',
  active_variant_id: 'v1',
  variants: [{ id: 'v1', text: 'Led a team of five engineers', tags: ['concise'], fact_ids: [] }],
};

const blockTwoVariants: BulletBlock = {
  id: 'block-2',
  active_variant_id: 'v2a',
  variants: [
    { id: 'v2a', text: 'Managed engineering team of 5', tags: ['verbose'], fact_ids: ['f-1'] },
    { id: 'v2b', text: 'Led 5-person engineering team', tags: ['targeted'], fact_ids: ['f-2'] },
  ],
};

const makeSections = (onSwitch = vi.fn()): BlockSection[] => [
  {
    id: 'exp-0',
    label: 'Software Engineer at Acme',
    blocks: [blockOneVariant, blockTwoVariants],
    onSwitchVariant: onSwitch,
  },
];

// ─── Tests ────────────────────────────────────────────────────────

describe('BlockVariantEditor', () => {
  it('returns null when sections is empty (legacy degradation)', () => {
    const { container } = render(<BlockVariantEditor sections={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders section label and variant chips', () => {
    render(<BlockVariantEditor sections={makeSections()} />);
    expect(screen.getByText('Software Engineer at Acme')).toBeInTheDocument();
    // Active chip for block-1
    expect(screen.getByText('concise')).toBeInTheDocument();
    // Chips for block-2
    expect(screen.getByText('verbose')).toBeInTheDocument();
    expect(screen.getByText('targeted')).toBeInTheDocument();
  });

  it('active variant chip has aria-pressed=true', () => {
    render(<BlockVariantEditor sections={makeSections()} />);
    // block-2 active is v2a — label contains "verbose"
    // aria-label = "tailor.variants.active: verbose" so we match by text content
    const verboseChip = screen.getByText('verbose');
    expect(verboseChip.closest('button')).toHaveAttribute('aria-pressed', 'true');
  });

  it('non-active variant chip has aria-pressed=false', () => {
    render(<BlockVariantEditor sections={makeSections()} />);
    // The "targeted" chip is non-active; find it by visible text
    const targetedChip = screen.getByText('targeted');
    expect(targetedChip.closest('button')).toHaveAttribute('aria-pressed', 'false');
  });

  it('calls onSwitchVariant when a non-active chip is clicked', async () => {
    const onSwitch = vi.fn().mockResolvedValue(undefined);
    render(<BlockVariantEditor sections={makeSections(onSwitch)} />);

    // Find the "targeted" chip by visible text and click it
    const targetedChip = screen.getByText('targeted');
    fireEvent.click(targetedChip.closest('button')!);
    await waitFor(() => expect(onSwitch).toHaveBeenCalledTimes(1));
    expect(onSwitch).toHaveBeenCalledWith('block-2', 'v2b');
  });

  it('does not call onSwitchVariant when active chip is clicked', () => {
    const onSwitch = vi.fn().mockResolvedValue(undefined);
    render(<BlockVariantEditor sections={makeSections(onSwitch)} />);

    const verboseChip = screen.getByText('verbose');
    fireEvent.click(verboseChip.closest('button')!);
    expect(onSwitch).not.toHaveBeenCalled();
  });

  it('collapses and expands when header is clicked', () => {
    render(<BlockVariantEditor sections={makeSections()} />);
    // Initially expanded — section label visible
    expect(screen.getByText('Software Engineer at Acme')).toBeVisible();

    const headerBtn = screen.getByRole('button', { name: /tailor\.variants\.title/i });
    fireEvent.click(headerBtn);
    expect(screen.queryByText('Software Engineer at Acme')).not.toBeInTheDocument();

    fireEvent.click(headerBtn);
    expect(screen.getByText('Software Engineer at Acme')).toBeVisible();
  });

  it('shows section count in header', () => {
    const sections = [
      ...makeSections(),
      {
        id: 'summary',
        label: 'tailor.variants.summarySection',
        blocks: [blockOneVariant],
        onSwitchVariant: vi.fn(),
      },
    ];
    render(<BlockVariantEditor sections={sections} />);
    // count = 2 sections
    expect(screen.getByText(/tailor\.variants\.sections/)).toBeInTheDocument();
  });

  it('renders block active text preview', () => {
    render(<BlockVariantEditor sections={makeSections()} />);
    // blockOneVariant active text
    expect(screen.getByText('Led a team of five engineers')).toBeInTheDocument();
    // blockTwoVariants active (v2a = verbose)
    expect(screen.getByText('Managed engineering team of 5')).toBeInTheDocument();
  });

  it('shows v1, v2 labels when block has no tags', () => {
    const noTagBlock: BulletBlock = {
      id: 'block-notags',
      active_variant_id: 'vA',
      variants: [
        { id: 'vA', text: 'First variant', tags: [], fact_ids: [] },
        { id: 'vB', text: 'Second variant', tags: [], fact_ids: [] },
      ],
    };
    const sections: BlockSection[] = [
      {
        id: 'exp-0',
        label: 'Acme',
        blocks: [noTagBlock],
        onSwitchVariant: vi.fn(),
      },
    ];
    render(<BlockVariantEditor sections={sections} />);
    expect(screen.getByText('v1')).toBeInTheDocument();
    expect(screen.getByText('v2')).toBeInTheDocument();
  });
});
