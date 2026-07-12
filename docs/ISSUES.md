# Resume Hulk — Human Test Issues

> **Tim: this is your bug inbox.** Add an entry any time something breaks or behaves wrong — a title and one or two sentences is enough; paste stack traces raw inside the code fence. No formatting rules, no triage duty. Commit or just save; the eng lead does the rest.
>
> **Eng lead: this file is step 1 of every session** (before BACKLOG.md). Triage every `status: new` entry into a BUG ticket, set `status: triaged (BUG-###)`, and fix ALL open bugs before dispatching any feature ticket — the bug gate in ORCHESTRATION.md. When fixed+verified, set `status: fixed (commit)`. Never delete entries; the history is the regression map. Every bug fix MUST include a regression test that fails on the pre-fix code.

## Template (copy below the line)

```
### [short title]
- **status:** new
- **date:** YYYY-MM-DD
- **where:** page/feature
- **what happened:**
- **expected:**
- **error output (if any):**
```

---

### Application tracker couldn't load applications
- **status:** fixed (d2c0d21)
- **date:** 2026-07-10
- **where:** Tracker page (and Career page, which loads the same data)
- **what happened:** Tracker fails to load applications. Career page reports the same underlying failure while loading reports.
- **expected:** Board loads all application cards.
- **error output:**
```
Failed to load career reports: Error: Failed to load applications. Please try again.
    at asJson (lib/api/tracker.ts:125:11)
    at async CareerPage.useCallback[loadReports] (app/(default)/career/page.tsx:383:31)
```
- **program-lead triage hint:** the message is the backend's generic 500 detail from `GET /api/applications` — the API itself is failing, not the frontend. Prime suspects are P3's RH-307 changes: lazy `status_history` backfill or list serialization hitting legacy rows (pre-P3 apps without `status_history`, or `considering` rows with `resume_id=NULL`). Check backend logs for the detailed error (repo pattern logs it server-side). Career page should also not surface a tracker-worded error for a reports load — secondary UX defect.

### Can't edit the resume
- **status:** fixed (f7b3f08)
- **date:** 2026-07-10
- **where:** Builder (resume edit)
- **what happened:** Builder crashes; error boundary triggers.
- **expected:** Resume opens and is editable.
- **error output:**
```
Error Boundary caught an error: TypeError: Cannot read properties of undefined (reading 'description')
    at <unknown> (components/builder/formatting-controls.tsx:201:54)
    at Array.map (<anonymous>)
    at FormattingControls (components/builder/formatting-controls.tsx:192:33)
```
- **program-lead triage hint:** confirmed by inspection — `formatting-controls.tsx:201` does `templateLabels[template.id].description` while mapping `TEMPLATE_OPTIONS`. RH-207 registered `murphy` in `TEMPLATE_OPTIONS` but `templateLabels` has no `murphy` entry → undefined. Fix the missing label entry AND make the map defensive; regression test must render FormattingControls with every id in `TEMPLATE_OPTIONS` (that test would have caught this at RH-207 time).

### Extracting facts renders with no facts yet
- **status:** fixed (108907f)
- **date:** 2026-07-10
- **where:** Facts page → Extract from master
- **what happened:** Extraction runs but the review list renders empty ("no facts yet").
- **expected:** Candidate facts listed for review/confirm.
- **error output:** none reported
- **program-lead triage hint:** three candidate layers — backend returns candidates but response shape mismatches what `lib/api/facts.ts` expects; the page filters candidates out (e.g., `duplicate_of` annotation from RH-203 marking everything duplicate after a prior confirm run); or extraction silently failed (check backend logs / network tab for the `/facts/extract` response body). Repro with a fresh browser network capture before fixing.

### Application quick-capture 500s
- **status:** fixed (BUG-005, 2026-07-11)
- **date:** 2026-07-11
- **where:** Tracker → quick-capture ("considering") add
- **what happened:** Adding an application fails.
- **expected:** Considering card created.
- **error output:**
```
INFO: 127.0.0.1:64043 - "POST /api/v1/applications/quick HTTP/1.1" 500 Internal Server Error
```
- **program-lead triage hint:** endpoint worked at RH-106 ship; broken since. Suspects in order: BUG-001's idempotent ALTER TABLE migrations (quick-capture inserts may not populate the new columns on some code path), RH-403's import path (`POST /jobs/import` reuses quick-capture — did it modify shared code?), RH-303 background JD-parse task firing on a job created via quick path. Backend log has the detailed error — start there, not with guesses.

### Fact extraction renders empty — REOPENED (was BUG-003, "fixed" 108907f)
- **status:** fixed (BUG-006, 2026-07-11)
- **date:** 2026-07-11
- **where:** Facts page → Extract from master
- **what happened:** Still renders empty after the BUG-003 fix. Tim's assessment: likely a function bug, not the LLM.
- **expected:** Candidates listed, or one of the three explicit empty-state messages BUG-003 claimed to add.
- **error output:** none reported (which itself violates the BUG-003 fix — silent empty was supposed to be impossible)
- **program-lead triage hint:** REOPEN PROTOCOL applies — the BUG-003 regression tests passed while the behavior stayed broken, so those tests verify the wrong layer. Required: (1) post-mortem the prior fix's tests — what do they actually exercise vs. what the browser exercises; (2) trace the REAL request path end-to-end (network capture: does `/facts/extract` return candidates? does the modal receive them? does render filter them?); (3) the fix must include a test at the layer that was actually broken. If none of the three empty-state messages appears, the frontend branch handling is broken regardless of backend behavior.

### JD Library fails to load jobs
- **status:** fixed (BUG-007, 2026-07-11)
- **date:** 2026-07-11
- **where:** /jobs page (new in RH-402)
- **what happened:** Page shows "Failed to load jobs."
- **expected:** All captured jobs listed.
- **error output:** none captured beyond the UI message
- **program-lead triage hint:** `GET /jobs` list is new (RH-402). Suspects: `JobSummary` Pydantic validation failing on legacy jobs (pre-RH-303 rows without `metadata_json["parsed"]`, or rows missing company/role dynamic keys); the archetype-badge lookup against the latest career report (empty/missing report?). Same class as BUG-001: new list endpoint never tested against real legacy-shaped rows. Backend log has the truth.

### Outcome rates always 0 — status_history absent from ApplicationResponse
- **status:** fixed (BUG-008, 2026-07-11)
- **date:** 2026-07-11 (self-reported by eng lead at P4 close)
- **where:** Career page outcome overlay
- **what happened:** `status_history` exists in DB but is not in the `ApplicationResponse` schema, so outcome rates compute over missing data and show 0.
- **expected:** Response/interview rates reflect actual status history.
- **program-lead triage hint:** add field to schema + serializer; regression test asserts a moved application's history appears in the API response AND non-zero rates flow to `/career` overlay computation.
