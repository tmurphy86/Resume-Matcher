import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  listCareerReports,
  getCareerReport,
  clusterArchetypes,
  generateCareerReport,
  type CareerReport,
  type Archetype,
  type ArchetypeScore,
} from '@/lib/api/career';

/**
 * Career API client contracts: wrappers must hit the correct method/URL and
 * surface backend error messages.  No real network or LLM calls.
 */

const STUB_ARCHETYPE: Archetype = {
  name: 'Engineering Manager',
  description: 'Leads cross-functional engineering teams.',
  jd_ids: ['jd-1', 'jd-2'],
  responsibilities: ['Hiring', 'Roadmap planning'],
};

const STUB_SCORE: ArchetypeScore = {
  archetype_name: 'Engineering Manager',
  attraction: 3.8,
  fit: 0.72,
  gaps: ['Kubernetes', 'Budget ownership'],
};

const STUB_REPORT: CareerReport = {
  id: 1,
  created_at: '2026-07-10T10:00:00Z',
  archetypes_json: [STUB_ARCHETYPE],
  jd_ids_json: ['jd-1', 'jd-2'],
  scores_json: [STUB_SCORE],
  advice_md: '**Focus** on engineering-heavy roles first.',
  model_used: 'gpt-4o',
};

const STUB_REPORT_NO_SCORES: CareerReport = {
  id: 2,
  created_at: '2026-07-10T09:00:00Z',
  archetypes_json: [STUB_ARCHETYPE],
  jd_ids_json: ['jd-1'],
  scores_json: null,
  advice_md: null,
  model_used: null,
};

describe('career API client', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const lastCall = () => {
    const [url, options] = fetchMock.mock.calls.at(-1)!;
    return { url: String(url), options: options as RequestInit };
  };

  it('listCareerReports GETs /career/reports', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify([STUB_REPORT, STUB_REPORT_NO_SCORES]), { status: 200 })
    );
    const reports = await listCareerReports();
    const { url, options } = lastCall();
    expect(url).toContain('/career/reports');
    expect(options.method).toBeUndefined(); // default GET
    expect(reports).toHaveLength(2);
    expect(reports[0].id).toBe(1);
    expect(reports[0].scores_json).not.toBeNull();
    expect(reports[1].scores_json).toBeNull();
  });

  it('getCareerReport GETs /career/reports/{id}', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(STUB_REPORT), { status: 200 }));
    const report = await getCareerReport(1);
    const { url } = lastCall();
    expect(url).toContain('/career/reports/1');
    expect(report.id).toBe(1);
    expect(report.archetypes_json[0].name).toBe('Engineering Manager');
  });

  it('clusterArchetypes POSTs to /career/cluster', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(STUB_REPORT_NO_SCORES), { status: 200 })
    );
    const report = await clusterArchetypes();
    const { url, options } = lastCall();
    expect(url).toContain('/career/cluster');
    expect(options.method).toBe('POST');
    expect(report.scores_json).toBeNull();
  });

  it('generateCareerReport POSTs to /career/report', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(STUB_REPORT), { status: 200 }));
    const report = await generateCareerReport();
    const { url, options } = lastCall();
    expect(url).toContain('/career/report');
    expect(options.method).toBe('POST');
    expect(report.scores_json).toHaveLength(1);
    expect(report.scores_json![0].attraction).toBe(3.8);
    expect(report.scores_json![0].fit).toBe(0.72);
    expect(report.scores_json![0].gaps).toContain('Kubernetes');
  });

  it('propagates backend error detail on non-ok responses', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'No job descriptions found.' }), { status: 400 })
    );
    await expect(clusterArchetypes()).rejects.toThrow('No job descriptions found.');
  });

  it('falls back to status code message when detail is absent', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({}), { status: 500 }));
    await expect(listCareerReports()).rejects.toThrow('status 500');
  });
});

// ---------------------------------------------------------------------------
// Quadrant placement logic (pure — no DOM needed)
// ---------------------------------------------------------------------------

describe('attraction×fit quadrant thresholds', () => {
  const ATTRACTION_THRESHOLD = 2.5;
  const FIT_THRESHOLD = 0.5;

  const classify = (s: ArchetypeScore) => ({
    highAttraction: s.attraction >= ATTRACTION_THRESHOLD,
    highFit: s.fit >= FIT_THRESHOLD,
  });

  it('places a high-attraction high-fit score in the target quadrant', () => {
    const s: ArchetypeScore = { archetype_name: 'A', attraction: 4.0, fit: 0.8, gaps: [] };
    expect(classify(s)).toEqual({ highAttraction: true, highFit: true });
  });

  it('places a high-attraction low-fit score in the stretch quadrant', () => {
    const s: ArchetypeScore = { archetype_name: 'B', attraction: 3.5, fit: 0.3, gaps: [] };
    expect(classify(s)).toEqual({ highAttraction: true, highFit: false });
  });

  it('places a low-attraction high-fit score in the market-signal quadrant', () => {
    const s: ArchetypeScore = { archetype_name: 'C', attraction: 1.0, fit: 0.9, gaps: [] };
    expect(classify(s)).toEqual({ highAttraction: false, highFit: true });
  });

  it('places a low-attraction low-fit score in the deprioritize quadrant', () => {
    const s: ArchetypeScore = { archetype_name: 'D', attraction: 0.5, fit: 0.1, gaps: [] };
    expect(classify(s)).toEqual({ highAttraction: false, highFit: false });
  });

  it('treats a score exactly at threshold as high', () => {
    const s: ArchetypeScore = {
      archetype_name: 'E',
      attraction: 2.5,
      fit: 0.5,
      gaps: [],
    };
    expect(classify(s)).toEqual({ highAttraction: true, highFit: true });
  });
});
