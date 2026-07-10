import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ProvenancePanel } from '@/components/tailor/provenance-panel';
import type { ProvenanceData } from '@/components/common/resume_previewer_context';

vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({
    t: (key: string, params?: Record<string, string>) => {
      if (params) {
        return Object.entries(params).reduce((str, [k, v]) => str.replace(`{${k}}`, v), key);
      }
      return key;
    },
  }),
}));

// Next.js Link mock
vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...rest
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const baseProvenance: ProvenanceData = {
  covered: 5,
  uncovered: 2,
  broken: 1,
};

describe('ProvenancePanel', () => {
  it('renders covered, uncovered, and broken counts', () => {
    render(<ProvenancePanel provenance={baseProvenance} unverifiedCount={0} />);
    // 5 covered, 2 uncovered, 1 broken — all appear somewhere in the document
    expect(screen.getAllByText(/5/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/2/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/1/).length).toBeGreaterThan(0);
  });

  it('shows verify gaps link when uncovered > 0', () => {
    render(<ProvenancePanel provenance={baseProvenance} unverifiedCount={0} />);
    const link = screen.getByRole('link', { name: /tailor\.provenance\.verifyGaps/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/facts?tab=interview');
  });

  it('hides verify gaps link when uncovered === 0', () => {
    const prov: ProvenanceData = { covered: 5, uncovered: 0, broken: 0 };
    render(<ProvenancePanel provenance={prov} unverifiedCount={0} />);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('shows unverified warning with count when unverifiedCount > 0', () => {
    render(<ProvenancePanel provenance={baseProvenance} unverifiedCount={3} />);
    // The translated key contains "{count}" replaced with "3"
    expect(screen.getByText(/tailor\.provenance\.unverifiedWarning/)).toBeInTheDocument();
  });

  it('renders null when provenance is null', () => {
    const { container } = render(<ProvenancePanel provenance={null} unverifiedCount={0} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders null when provenance is undefined', () => {
    const { container } = render(<ProvenancePanel provenance={undefined} unverifiedCount={0} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows collapsible detail list when uncovered_items exist and expand toggle is clicked', () => {
    const prov: ProvenanceData = {
      covered: 2,
      uncovered: 1,
      broken: 0,
      uncovered_items: [{ section: 'experience', text: 'Led team of 10 engineers' }],
    };
    render(<ProvenancePanel provenance={prov} unverifiedCount={0} />);
    // Detail text not yet visible
    expect(screen.queryByText('Led team of 10 engineers')).not.toBeInTheDocument();
    // Click the expand toggle
    const toggle = screen.getByRole('button', { name: /expand provenance details/i });
    fireEvent.click(toggle);
    expect(screen.getByText('Led team of 10 engineers')).toBeInTheDocument();
  });

  it('collapses detail list when toggle is clicked twice', () => {
    const prov: ProvenanceData = {
      covered: 2,
      uncovered: 1,
      broken: 0,
      uncovered_items: [{ section: 'skills', text: 'Python expert' }],
    };
    render(<ProvenancePanel provenance={prov} unverifiedCount={0} />);
    const toggle = screen.getByRole('button', { name: /expand provenance details/i });
    fireEvent.click(toggle);
    expect(screen.getByText('Python expert')).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.queryByText('Python expert')).not.toBeInTheDocument();
  });
});
