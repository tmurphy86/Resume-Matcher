import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  listFacts,
  createFact,
  updateFact,
  deleteFact,
  extractFacts,
  confirmFacts,
  type Fact,
} from '@/lib/api/facts';

/**
 * Facts API client contracts: wrappers must hit the correct method/URL and
 * propagate backend error detail strings.  No real LLM or network calls.
 */

const STUB_FACT: Fact = {
  fact_id: 'f-001',
  statement: 'Led a team of 5 engineers',
  context: 'experience',
  source: 'master_resume',
  metrics_json: {},
  tags_json: ['leadership'],
  confidence: 'high',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('facts API client', () => {
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

  it('listFacts GETs /facts with no params', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([STUB_FACT]), { status: 200 }));
    const facts = await listFacts();
    const { url, options } = lastCall();
    expect(url).toContain('/facts');
    expect(options.method).toBeUndefined(); // default GET
    expect(facts).toHaveLength(1);
    expect(facts[0].fact_id).toBe('f-001');
  });

  it('listFacts GETs /facts with tag and context query params', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    await listFacts({ tag: 'leadership', context: 'experience' });
    const { url } = lastCall();
    expect(url).toContain('tag=leadership');
    expect(url).toContain('context=experience');
  });

  it('createFact POSTs to /facts', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify(STUB_FACT), { status: 201 }));
    // Omit server-generated fields; the remaining shape is the create payload.
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { fact_id: _id, created_at: _ca, updated_at: _ua, ...payload } = STUB_FACT;
    await createFact(payload);
    const { url, options } = lastCall();
    expect(url).toContain('/facts');
    expect(options.method).toBe('POST');
    expect(JSON.parse(String(options.body))).toMatchObject({
      statement: 'Led a team of 5 engineers',
    });
  });

  it('updateFact PATCHes /facts/{id}', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ ...STUB_FACT, statement: 'Updated statement' }), {
        status: 200,
      })
    );
    await updateFact('f-001', { statement: 'Updated statement' });
    const { url, options } = lastCall();
    expect(url).toContain('/facts/f-001');
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(String(options.body))).toEqual({ statement: 'Updated statement' });
  });

  it('deleteFact DELETEs /facts/{id}', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ message: 'deleted', affected: 1 }), { status: 200 })
    );
    await deleteFact('f-001');
    const { url, options } = lastCall();
    expect(url).toContain('/facts/f-001');
    expect(options.method).toBe('DELETE');
  });

  it('extractFacts POSTs to /facts/extract with resume_id query param', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify([{ ...STUB_FACT, duplicate_of: null }]), { status: 200 })
    );
    const result = await extractFacts('r-999');
    const { url, options } = lastCall();
    expect(url).toContain('/facts/extract');
    expect(url).toContain('resume_id=r-999');
    expect(options.method).toBe('POST');
    expect(result[0].fact_id).toBe('f-001');
  });

  it('extractFacts URL-encodes the resume_id', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([]), { status: 200 }));
    await extractFacts('resume id with spaces');
    const { url } = lastCall();
    expect(url).toContain('resume_id=resume%20id%20with%20spaces');
  });

  it('confirmFacts POSTs candidate array to /facts/confirm', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify([STUB_FACT]), { status: 200 }));
    const result = await confirmFacts([STUB_FACT]);
    const { url, options } = lastCall();
    expect(url).toContain('/facts/confirm');
    expect(options.method).toBe('POST');
    const body = JSON.parse(String(options.body));
    expect(Array.isArray(body)).toBe(true);
    expect(body[0].fact_id).toBe('f-001');
    expect(result).toHaveLength(1);
  });

  it('confirmFacts handles duplicate result shape', async () => {
    const dupResult = { status: 'duplicate', existing_fact_id: 'f-000', statement: 'old fact' };
    fetchMock.mockResolvedValue(new Response(JSON.stringify([dupResult]), { status: 200 }));
    const result = await confirmFacts([STUB_FACT]);
    expect(result[0]).toMatchObject({ status: 'duplicate', existing_fact_id: 'f-000' });
  });

  it('surfaces the backend detail message on non-ok response', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'fact not found' }), { status: 404 })
    );
    await expect(deleteFact('missing')).rejects.toThrow('fact not found');
  });

  it('falls back to status code message when no detail', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({}), { status: 500 }));
    await expect(listFacts()).rejects.toThrow('status 500');
  });
});
