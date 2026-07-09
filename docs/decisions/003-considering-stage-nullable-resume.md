# ADR-003: "Considering" applications may exist without a tailored resume

**Status:** Accepted (program lead, 2026-07-09)

## Context
Career intelligence needs volume: Tim must be able to log a job he's *considering* in <30s, before (or without ever) tailoring a resume. Today `Application.resume_id` is required and part of `uq_application_job_resume`.

## Decision
Make `Application.resume_id` nullable. Add `considering` to `ApplicationStatus` (before `applied`). Quick-capture creates a `Job` (JD text) + an `Application(status=considering, resume_id=NULL)`. When a resume is later tailored for the job, the application is updated in place.

SQLite treats NULLs as distinct in unique constraints, so `uq_application_job_resume` still dedupes real (job, resume) pairs; app-level logic must prevent duplicate considering-cards per job (check `job_id` + `resume_id IS NULL` before insert).

## Consequences
One nullable-column migration (additive-safe: widens, never drops). Tracker UI needs a "considering" column and must tolerate cards without an "Edit resume" target.
