import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { ATSScoreCard } from '@/components/tailor/ats-score-card';
import type { ATSScore } from '@/components/common/resume_previewer_context';

const baseATSScore: ATSScore = {
  overall_score: 75,
  sub_scores: {
    keyword_match: 80,
    skills_coverage: 70,
    section_completeness: 75,
  },
  missing_keywords: ['Python', 'Kubernetes', 'AWS'],
  injectable_keywords: ['React', 'TypeScript'],
  recommendations: ['Add more technical skills', 'Expand project descriptions'],
};

describe('ATSScoreCard', () => {
  it('renders overall score and sub-scores', () => {
    render(<ATSScoreCard atsScore={baseATSScore} />);
    expect(screen.getByText('ATS Score Breakdown')).toBeInTheDocument();
    expect(screen.getByText(/Keyword Match/)).toBeInTheDocument();
    expect(screen.getByText(/Skills Coverage/)).toBeInTheDocument();
  });

  it('renders missing keywords as static spans when onKeywordClick is not provided', () => {
    render(<ATSScoreCard atsScore={baseATSScore} />);
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('Kubernetes')).toBeInTheDocument();
    expect(screen.getByText('AWS')).toBeInTheDocument();
  });

  it('calls onKeywordClick with the correct keyword when a missing-keyword button is clicked', () => {
    const mockOnKeywordClick = vi.fn();
    render(<ATSScoreCard atsScore={baseATSScore} onKeywordClick={mockOnKeywordClick} />);

    const pythonButton = screen.getByRole('button', { name: 'Python' });
    fireEvent.click(pythonButton);

    expect(mockOnKeywordClick).toHaveBeenCalledWith('Python');
    expect(mockOnKeywordClick).toHaveBeenCalledTimes(1);
  });

  it('renders injectable keywords', () => {
    render(<ATSScoreCard atsScore={baseATSScore} />);
    expect(screen.getByText('React')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
  });

  it('renders recommendations', () => {
    render(<ATSScoreCard atsScore={baseATSScore} />);
    expect(screen.getByText('Add more technical skills')).toBeInTheDocument();
    expect(screen.getByText('Expand project descriptions')).toBeInTheDocument();
  });

  it('does not render missing keywords section when array is empty', () => {
    const scoreWithoutMissing: ATSScore = {
      ...baseATSScore,
      missing_keywords: [],
    };
    render(<ATSScoreCard atsScore={scoreWithoutMissing} />);
    expect(screen.queryByText('Missing Keywords')).not.toBeInTheDocument();
  });

  it('does not render injectable keywords section when array is empty', () => {
    const scoreWithoutInjectable: ATSScore = {
      ...baseATSScore,
      injectable_keywords: [],
    };
    render(<ATSScoreCard atsScore={scoreWithoutInjectable} />);
    expect(screen.queryByText('Safe to Add')).not.toBeInTheDocument();
  });

  it('does not render recommendations section when array is empty', () => {
    const scoreWithoutRecommendations: ATSScore = {
      ...baseATSScore,
      recommendations: [],
    };
    render(<ATSScoreCard atsScore={scoreWithoutRecommendations} />);
    expect(screen.queryByText('Recommendations')).not.toBeInTheDocument();
  });
});
