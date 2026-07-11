import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { listJobs, getJob, type JobSummary, type JobDetail } from '@/lib/api/jobs';

const STUB_SUMMARY: JobSummary = {
  job_id: 'j-001',
  snippet: 'Senior Python Engineer at MegaCorp, responsible for...',
  created_at: '2026-01-01T00:00:00Z',
  company: 'MegaCorp',
  role: 'Senior Python Engineer',
  level: 'senior',
  archetype: 'Backend',
};

const STUB_DETAIL: JobDetail = {
  job_id: 'j-001',
  content: 'Senior Python Engineer at MegaCorp, responsible for building APIs...',
  created_at: '2026-01-01T00:00:00Z',
  company: 'MegaCorp',
  role: 'Senior Python Engineer',
  level: 'senior',
  archetype: 'Backend',
  responsibilities: ['Build APIs', 'Review PRs'],
  requirements: ['Python', 'FastAPI'],
  application_ids: ['app-abc'],
};

describe('jobs API client', () => {
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

  it('listJobs GETs /jobs with no params', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([STUB_SUMMARY]), { status: 200 }));
    const jobs = await listJobs();
    const { url, options } = lastCall();
    expect(url).toContain('/jobs');
    expect(url).not.toContain('?');
    expect(options.method).toBeUndefined();
    expect(jobs).toHaveLength(1);
    expect(jobs[0].job_id).toBe('j-001');
  });

  it('listJobs appends ?q= when provided', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    await listJobs({ q: 'python' });
    const { url } = lastCall();
    expect(url).toContain('q=python');
  });

  it('listJobs appends ?archetype= when provided', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    await listJobs({ archetype: 'Backend' });
    const { url } = lastCall();
    expect(url).toContain('archetype=Backend');
  });

  it('listJobs sends both q and archetype params together', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    await listJobs({ q: 'engineer', archetype: 'Backend' });
    const { url } = lastCall();
    expect(url).toContain('q=engineer');
    expect(url).toContain('archetype=Backend');
  });

  it('getJob GETs /jobs/{id}', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(STUB_DETAIL), { status: 200 }));
    const detail = await getJob('j-001');
    const { url, options } = lastCall();
    expect(url).toContain('/jobs/j-001');
    expect(options.method).toBeUndefined();
    expect(detail.application_ids).toEqual(['app-abc']);
    expect(detail.responsibilities).toHaveLength(2);
  });

  it('getJob URL-encodes job_id', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(STUB_DETAIL), { status: 200 }));
    await getJob('job id/with special');
    const { url } = lastCall();
    expect(url).toContain('job%20id%2Fwith%20special');
  });

  it('surfaces backend detail message on non-ok response', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'job not found' }), { status: 404 })
    );
    await expect(getJob('missing')).rejects.toThrow('job not found');
  });

  it('falls back to status code when no detail key', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({}), { status: 500 }));
    await expect(listJobs()).rejects.toThrow('status 500');
  });
});
