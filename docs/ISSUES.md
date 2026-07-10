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
- **status:** new
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
- **status:** new
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
- **status:** new
- **date:** 2026-07-10
- **where:** Facts page → Extract from master
- **what happened:** Extraction runs but the review list renders empty ("no facts yet").
- **expected:** Candidate facts listed for review/confirm.
- **error output:** none reported
- **program-lead triage hint:** three candidate layers — backend returns candidates but response shape mismatches what `lib/api/facts.ts` expects; the page filters candidates out (e.g., `duplicate_of` annotation from RH-203 marking everything duplicate after a prior confirm run); or extraction silently failed (check backend logs / network tab for the `/facts/extract` response body). Repro with a fresh browser network capture before fixing.
