/**
 * Unit tests for computeOutcomeRates (exported from career/page.tsx).
 *
 * Verifies deterministic outcome rate calculation from status_history:
 * - response_rate: apps with status in {response, interview, offer, accepted}
 * - interview_rate: apps with status in {interview, offer, accepted}
 *
 * No network calls, no DOM required.
 */

import { describe, it, expect } from 'vitest';
import { computeOutcomeRates } from '@/app/(default)/career/page';

// ---------------------------------------------------------------------------
// Helpers: minimal ApplicationWithHistory shapes
// ---------------------------------------------------------------------------

function makeApp(jobId: string, statuses: string[], createdAt = '2025-01-01T00:00:00Z') {
  return {
    application_id: `app-${Math.random()}`,
    job_id: jobId,
    resume_id: null,
    master_resume_id: null,
    status: 'applied' as const,
    company: null,
    role: null,
    applied_at: null,
    notes: null,
    position: 0,
    interest_signals: [],
    created_at: createdAt,
    updated_at: createdAt,
    status_history: statuses.map((s) => ({ status: s, at: createdAt })),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('computeOutcomeRates', () => {
  it('returns zeros when no applications are given', () => {
    const rates = computeOutcomeRates([], ['job-A']);
    expect(rates.responseRate).toBe(0);
    expect(rates.interviewRate).toBe(0);
  });

  it('returns zeros when no applications match the archetype jd_ids', () => {
    const apps = [makeApp('job-B', ['response'])];
    const rates = computeOutcomeRates(apps, ['job-A']);
    expect(rates.responseRate).toBe(0);
    expect(rates.interviewRate).toBe(0);
  });

  it('computes response_rate: only apps with response/interview/offer/accepted in history', () => {
    const apps = [
      makeApp('job-A', ['applied', 'response']), // counts
      makeApp('job-A', ['applied']), // does NOT count
      makeApp('job-A', ['applied', 'interview']), // counts
    ];
    const rates = computeOutcomeRates(apps, ['job-A']);
    // 2 out of 3 reached response threshold
    expect(rates.responseRate).toBeCloseTo(2 / 3);
  });

  it('computes interview_rate: only apps with interview/offer/accepted in history', () => {
    const apps = [
      makeApp('job-A', ['applied', 'response']), // response only — NOT interview
      makeApp('job-A', ['applied', 'interview']), // counts
      makeApp('job-A', ['applied']), // does NOT count
    ];
    const rates = computeOutcomeRates(apps, ['job-A']);
    // 1 out of 3 reached interview threshold
    expect(rates.interviewRate).toBeCloseTo(1 / 3);
  });

  it('"offer" counts for both response and interview rates', () => {
    const apps = [makeApp('job-X', ['offer'])];
    const rates = computeOutcomeRates(apps, ['job-X']);
    expect(rates.responseRate).toBe(1);
    expect(rates.interviewRate).toBe(1);
  });

  it('"accepted" counts for both response and interview rates', () => {
    const apps = [makeApp('job-X', ['accepted'])];
    const rates = computeOutcomeRates(apps, ['job-X']);
    expect(rates.responseRate).toBe(1);
    expect(rates.interviewRate).toBe(1);
  });

  it('excludes apps whose job_id is outside the archetype', () => {
    const apps = [
      makeApp('job-A', ['applied', 'response']),
      makeApp('job-B', ['interview']), // different archetype, must be excluded
    ];
    const rates = computeOutcomeRates(apps, ['job-A']);
    expect(rates.responseRate).toBe(1); // 1/1 for job-A
    expect(rates.interviewRate).toBe(0); // 0/1 for job-A
  });

  it('handles app with empty status_history', () => {
    const apps = [
      makeApp('job-A', []), // no history
      makeApp('job-A', ['response']), // counts for response
    ];
    const rates = computeOutcomeRates(apps, ['job-A']);
    expect(rates.responseRate).toBeCloseTo(0.5);
    expect(rates.interviewRate).toBe(0);
  });

  it('is deterministic: identical inputs always return identical outputs', () => {
    const apps = [
      makeApp('job-A', ['applied', 'response']),
      makeApp('job-A', ['applied', 'interview']),
      makeApp('job-A', ['applied']),
    ];
    const r1 = computeOutcomeRates(apps, ['job-A']);
    const r2 = computeOutcomeRates(apps, ['job-A']);
    expect(r1.responseRate).toBe(r2.responseRate);
    expect(r1.interviewRate).toBe(r2.interviewRate);
  });

  it('combines multiple jd_ids correctly', () => {
    const apps = [
      makeApp('job-A', ['response']),
      makeApp('job-B', ['interview']),
      makeApp('job-C', ['applied']),
    ];
    const rates = computeOutcomeRates(apps, ['job-A', 'job-B']);
    // 2 apps total; both reached response (response and interview); 1 reached interview
    expect(rates.responseRate).toBe(1);
    expect(rates.interviewRate).toBeCloseTo(0.5);
  });
});
