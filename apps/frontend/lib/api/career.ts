import { apiFetch, apiPost } from './client';
import { listApplications, type ApplicationListResponse } from './tracker';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Archetype {
  name: string;
  description: string;
  jd_ids: string[];
  responsibilities: string[];
}

export interface ArchetypeScore {
  archetype_name: string;
  attraction: number; // 0.0–5.0
  fit: number; // 0.0–1.0
  gaps: string[]; // requirements with no fact coverage
}

export interface CareerReport {
  id: number;
  created_at: string; // ISO 8601
  archetypes_json: Archetype[];
  jd_ids_json: string[];
  scores_json: ArchetypeScore[] | null; // null before /report is run
  advice_md: string | null;
  model_used: string | null;
}

// ---------------------------------------------------------------------------
// Error helpers (mirrors tracker.ts pattern)
// ---------------------------------------------------------------------------

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
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    try {
      return JSON.stringify(detail);
    } catch {
      return null;
    }
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

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Run archetype clustering on all saved JDs — creates a new CareerReport. */
export async function clusterArchetypes(): Promise<CareerReport> {
  const res = await apiPost('/career/cluster', {});
  return asJson<CareerReport>(res, 'Failed to cluster archetypes');
}

/** Compute scores + narrative for the latest report. */
export async function generateCareerReport(): Promise<CareerReport> {
  const res = await apiPost('/career/report', {});
  return asJson<CareerReport>(res, 'Failed to generate career report');
}

/** List all career reports, newest first. */
export async function listCareerReports(): Promise<CareerReport[]> {
  const res = await apiFetch('/career/reports', { credentials: 'include' });
  return asJson<CareerReport[]>(res, 'Failed to load career reports');
}

/** Fetch a single career report by ID. */
export async function getCareerReport(id: number): Promise<CareerReport> {
  const res = await apiFetch(`/career/reports/${id}`, { credentials: 'include' });
  return asJson<CareerReport>(res, 'Failed to load career report');
}

/**
 * List applications for the career intelligence view.
 *
 * Re-uses the tracker endpoint but surfaces a career-domain error message so
 * the career page never shows a tracker-worded failure to the user.
 */
export async function listApplicationsForCareer(): Promise<ApplicationListResponse> {
  try {
    return await listApplications();
  } catch {
    throw new Error('Failed to load career data. Please try again.');
  }
}
