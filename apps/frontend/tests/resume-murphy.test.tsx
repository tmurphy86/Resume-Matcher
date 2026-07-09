import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ResumeMurphy } from '@/components/resume/resume-murphy';
import type { ResumeData } from '@/components/dashboard/resume-component';

vi.mock('@/lib/i18n', () => ({ useTranslations: () => ({ t: (k: string) => k }) }));

const data: ResumeData = {
  personalInfo: {
    name: 'Tim Murphy',
    email: 'tim@murphy.dev',
    phone: '+1-555-000-0001',
    location: 'New York, NY',
    linkedin: 'linkedin.com/in/timmurphy',
  },
  workExperience: [
    {
      id: 1,
      title: 'Engineering Lead',
      company: 'Acme Corp',
      location: 'Remote',
      years: '2022-Present',
      description: ['Led a team of 8 engineers.', 'Shipped major platform rewrite.'],
    },
  ],
  education: [
    {
      id: 1,
      institution: 'State University',
      degree: 'B.S. Computer Science',
      years: '2010-2014',
    },
  ],
  additional: {
    technicalSkills: ['TypeScript', 'Python', 'AWS'],
    languages: ['English', 'Spanish'],
    certificationsTraining: [],
    awards: [],
  },
} as ResumeData;

describe('ResumeMurphy', () => {
  it('renders name in the header', () => {
    render(<ResumeMurphy data={data} />);
    expect(screen.getByText('Tim Murphy')).toBeInTheDocument();
  });

  it('renders contact details', () => {
    render(<ResumeMurphy data={data} />);
    expect(screen.getByText('tim@murphy.dev')).toBeInTheDocument();
    expect(screen.getByText('+1-555-000-0001')).toBeInTheDocument();
    expect(screen.getByText('New York, NY')).toBeInTheDocument();
  });

  it('renders competency band from technicalSkills', () => {
    render(<ResumeMurphy data={data} />);
    // All skills appear in the band
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('AWS')).toBeInTheDocument();
  });

  it('renders experience with company, role, and bullets', () => {
    render(<ResumeMurphy data={data} />);
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('Engineering Lead')).toBeInTheDocument();
    expect(screen.getByText('Led a team of 8 engineers.')).toBeInTheDocument();
    expect(screen.getByText('Shipped major platform rewrite.')).toBeInTheDocument();
  });

  it('renders education with institution and degree', () => {
    render(<ResumeMurphy data={data} />);
    expect(screen.getByText('State University')).toBeInTheDocument();
    expect(screen.getByText('B.S. Computer Science')).toBeInTheDocument();
  });

  it('renders languages in the additional section (not duplicated in competency band)', () => {
    render(<ResumeMurphy data={data} />);
    expect(screen.getByText(/English/)).toBeInTheDocument();
    expect(screen.getByText(/Spanish/)).toBeInTheDocument();
  });

  it('skips technicalSkills in the additional section when shown in competency band', () => {
    render(<ResumeMurphy data={data} />);
    // technicalSkills appear in competency band; in the additional section they are skipped.
    // Because the competency band is non-empty, the additional section should not repeat them
    // as a "Technical Skills:" labeled row.
    const skillLabels = screen.queryAllByText('Technical Skills:');
    expect(skillLabels).toHaveLength(0);
  });
});
