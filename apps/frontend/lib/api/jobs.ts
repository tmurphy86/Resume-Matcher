import { apiFetch, apiPost } from './client';

export interface JobSummary {
  job_id: string;
  snippet: string;
  created_at: string;
  company: string | null;
  role: string | null;
  level: string | null;
  archetype: string | null;
}

export interface JobDetail {
  job_id: string;
  content: string;
  created_at: string;
  company: string | null;
  role: string | null;
  level: string | null;
  archetype: string | null;
  responsibilities: string[];
  requirements: string[];
  application_ids: string[];
  [key: string]: unknown;
}

function extractDetail(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d) =>
        d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : null
      )
      .filter((m): m is string => Boolean(m));
    if (messages.length > 0) return messages.join('; ');
  }
  return null;
}

async function asJson<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractDetail(data) || `${fallback} (status ${res.status}).`);
  }
  return res.json() as Promise<T>;
}

export async function listJobs(params?: { q?: string; archetype?: string }): Promise<JobSummary[]> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.archetype) qs.set('archetype', params.archetype);
  const query = qs.toString() ? `?${qs.toString()}` : '';
  const res = await apiFetch(`/jobs${query}`, { credentials: 'include' });
  return asJson<JobSummary[]>(res, 'Failed to load jobs');
}

export async function getJob(jobId: string): Promise<JobDetail> {
  const res = await apiFetch(`/jobs/${encodeURIComponent(jobId)}`, { credentials: 'include' });
  return asJson<JobDetail>(res, 'Failed to load job');
}

export interface JobSearchResult {
  title: string;
  company: string;
  location: string;
  snippet: string;
  url: string;
  source: string;
}

export async function searchExternalJobs(params: {
  term: string;
  location?: string;
  sources?: string[];
}): Promise<{ results: JobSearchResult[]; errors: Record<string, string> }> {
  const res = await apiPost('/jobs/search', {
    term: params.term,
    location: params.location ?? null,
    sources: params.sources ?? ['linkedin', 'indeed'],
  });
  return asJson<{ results: JobSearchResult[]; errors: Record<string, string> }>(
    res,
    'Job search failed'
  );
}

export async function importExternalJob(data: {
  url: string;
  source: string;
  title?: string;
  company?: string;
  description: string;
}): Promise<{ job_id: string; application_id: string | null }> {
  const res = await apiPost('/jobs/import', {
    url: data.url,
    source: data.source,
    title: data.title ?? null,
    company: data.company ?? null,
    description: data.description,
  });
  return asJson<{ job_id: string; application_id: string | null }>(res, 'Job import failed');
}
