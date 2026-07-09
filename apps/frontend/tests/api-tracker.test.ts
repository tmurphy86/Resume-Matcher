import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  bulkUpdateStatus,
  bulkDeleteApplications,
  createApplication,
  deleteApplication,
  updateApplication,
  quickCaptureApplication,
  getInterestDimensions,
  APPLICATION_STATUS_ORDER,
} from '@/lib/api/tracker';
import { llmProviderToKeyProvider } from '@/lib/api/config';

/**
 * Tracker API client contracts: the wrappers must hit the right method/URL and
 * send the right payloads, and the provider-axis mapping (used by the Settings
 * key store) must mirror the backend `_PROVIDER_KEY_MAP`.
 */

describe('llmProviderToKeyProvider', () => {
  it('maps gemini to the google key-store slot and passes others through', () => {
    expect(llmProviderToKeyProvider('gemini')).toBe('google');
    expect(llmProviderToKeyProvider('openai')).toBe('openai');
    expect(llmProviderToKeyProvider('anthropic')).toBe('anthropic');
    expect(llmProviderToKeyProvider('openai_compatible')).toBe('openai_compatible');
    expect(llmProviderToKeyProvider('ollama')).toBe('ollama');
  });
});

describe('tracker API client', () => {
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

  it('bulkUpdateStatus PATCHes /applications/bulk with ids + status', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ message: 'ok', affected: 2 }), { status: 200 })
    );
    await bulkUpdateStatus(['a', 'b'], 'interview');
    const { url, options } = lastCall();
    expect(url).toContain('/applications/bulk');
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(String(options.body))).toEqual({
      application_ids: ['a', 'b'],
      status: 'interview',
    });
  });

  it('updateApplication PATCHes /applications/{id} with the partial', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ application_id: 'x' }), { status: 200 })
    );
    await updateApplication('x', { status: 'rejected', position: 0 });
    const { url, options } = lastCall();
    expect(url).toContain('/applications/x');
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(String(options.body))).toEqual({ status: 'rejected', position: 0 });
  });

  it('createApplication POSTs the manual-add payload', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ application_id: 'x' }), { status: 200 })
    );
    await createApplication({ resume_id: 'r1', job_description: 'JD', status: 'saved' });
    const { url, options } = lastCall();
    expect(url).toContain('/applications');
    expect(options.method).toBe('POST');
    expect(JSON.parse(String(options.body))).toMatchObject({ resume_id: 'r1', status: 'saved' });
  });

  it('deleteApplication DELETEs /applications/{id}', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ message: 'ok', affected: 1 }), { status: 200 })
    );
    await deleteApplication('x');
    const { url, options } = lastCall();
    expect(url).toContain('/applications/x');
    expect(options.method).toBe('DELETE');
  });

  it('bulkDeleteApplications POSTs to /applications/bulk-delete', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ message: 'ok', affected: 2 }), { status: 200 })
    );
    await bulkDeleteApplications(['a', 'b']);
    const { url, options } = lastCall();
    expect(url).toContain('/applications/bulk-delete');
    expect(options.method).toBe('POST');
    expect(JSON.parse(String(options.body))).toEqual({ application_ids: ['a', 'b'] });
  });

  it('surfaces the backend detail message on failure', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: 'boom' }), { status: 500 }));
    await expect(deleteApplication('x')).rejects.toThrow('boom');
  });

  it('quickCaptureApplication POSTs to /applications/quick with jd_text payload', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ application_id: 'q1', status: 'considering' }), {
        status: 200,
      })
    );
    await quickCaptureApplication({ jd_text: 'Software engineer role', company: 'Acme' });
    const { url, options } = lastCall();
    expect(url).toContain('/applications/quick');
    expect(options.method).toBe('POST');
    expect(JSON.parse(String(options.body))).toMatchObject({
      jd_text: 'Software engineer role',
      company: 'Acme',
    });
  });

  it('getInterestDimensions GETs /applications/interest-dimensions', async () => {
    const dims = [
      { id: 'mission', label: 'Mission' },
      { id: 'growth', label: 'Growth' },
    ];
    fetchMock.mockResolvedValue(new Response(JSON.stringify(dims), { status: 200 }));
    const result = await getInterestDimensions();
    const { url } = lastCall();
    expect(url).toContain('/applications/interest-dimensions');
    expect(result).toEqual(dims);
  });

  it('updateApplication accepts interest_signals in the payload', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ application_id: 'x' }), { status: 200 })
    );
    const signals = [{ dimension: 'mission', weight: 4 }];
    await updateApplication('x', { interest_signals: signals });
    const { url, options } = lastCall();
    expect(url).toContain('/applications/x');
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(String(options.body))).toEqual({ interest_signals: signals });
  });

  it('APPLICATION_STATUS_ORDER starts with considering', () => {
    expect(APPLICATION_STATUS_ORDER[0]).toBe('considering');
    expect(APPLICATION_STATUS_ORDER).toContain('considering');
    expect(APPLICATION_STATUS_ORDER).toContain('saved');
  });
});
