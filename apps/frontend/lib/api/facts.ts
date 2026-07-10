import { apiFetch, apiPost, apiPatch, apiDelete } from './client';

export interface Fact {
  fact_id: string;
  statement: string;
  context: string | null;
  source: string | null;
  metrics_json: Record<string, unknown>;
  tags_json: string[];
  confidence: string;
  created_at: string;
  updated_at: string;
  duplicate_of?: string | null;
}

export interface DuplicateResult {
  status: 'duplicate';
  existing_fact_id: string;
  statement: string;
}

export type ConfirmResult = Fact | DuplicateResult;

// FastAPI returns `detail` as a string for HTTPException but as an array for
// validation errors — coerce both to a string so error messages are legible.
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

export async function listFacts(params?: { tag?: string; context?: string }): Promise<Fact[]> {
  const qs = new URLSearchParams();
  if (params?.tag) qs.set('tag', params.tag);
  if (params?.context) qs.set('context', params.context);
  const query = qs.toString() ? `?${qs.toString()}` : '';
  const res = await apiFetch(`/facts${query}`, { credentials: 'include' });
  return asJson<Fact[]>(res, 'Failed to load facts');
}

export async function createFact(
  data: Omit<Fact, 'fact_id' | 'created_at' | 'updated_at'>
): Promise<Fact> {
  const res = await apiPost('/facts', data);
  return asJson<Fact>(res, 'Failed to create fact');
}

export async function updateFact(
  factId: string,
  data: Partial<
    Pick<Fact, 'statement' | 'context' | 'source' | 'metrics_json' | 'tags_json' | 'confidence'>
  >
): Promise<Fact> {
  const res = await apiPatch(`/facts/${factId}`, data);
  return asJson<Fact>(res, 'Failed to update fact');
}

export async function deleteFact(factId: string): Promise<void> {
  const res = await apiDelete(`/facts/${factId}`);
  await asJson<{ message: string; affected: number }>(res, 'Failed to delete fact');
}

export async function extractFacts(resumeId: string): Promise<Fact[]> {
  const res = await apiPost(`/facts/extract?resume_id=${encodeURIComponent(resumeId)}`, {});
  return asJson<Fact[]>(res, 'Failed to extract facts');
}

export async function confirmFacts(candidates: Fact[]): Promise<ConfirmResult[]> {
  const res = await apiPost('/facts/confirm', candidates);
  return asJson<ConfirmResult[]>(res, 'Failed to confirm facts');
}

export interface ImportedFact extends Fact {
  group: 'new' | 'duplicate' | 'variant_of';
  existing_fact_id: string | null;
  existing_statement: string | null;
}

export async function importResumeFacts(resumeId: string): Promise<ImportedFact[]> {
  const res = await apiFetch(`/facts/import-resume?resume_id=${encodeURIComponent(resumeId)}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(extractDetail(data) || `Import failed (status ${res.status}).`);
  }
  return res.json() as Promise<ImportedFact[]>;
}
