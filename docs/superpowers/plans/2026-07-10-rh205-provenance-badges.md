# RH-205 Provenance Badges UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface provenance badges and unverified-change warnings in the tailor view using data already returned by the improve/preview backend endpoint.

**Architecture:** Three layers of changes — (1) type extension in the shared context, (2) two new/modified UI components, (3) page wiring + i18n. No new backend calls; all data arrives in the existing `ImproveResumeData` response.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript strict, Tailwind CSS v4, vitest + Testing Library (jsdom)

## Global Constraints

- Swiss International Style: `rounded-none`, `border border-black`, hard shadows (`shadow-sw-sm`/`shadow-sw-lg`), brand tokens only — `text-success` (#15803D), `text-warning` (#F97316), `text-destructive` (#DC2626), `text-primary` (#1D4ED8)
- `font-mono` for IDs and counts; `font-serif` for section headers
- No raw `fetch` calls — no new backend calls
- All 6 locale files (`en`, `es`, `zh`, `ja`, `pt-BR`, `fr`) must have identical structure at same key paths or `npm run build` breaks
- `npm run lint && npm run test` must pass before done

---

### Task 1: Extend `Data` interface with provenance and unverified fields

**Files:**
- Modify: `apps/frontend/components/common/resume_previewer_context.tsx:118-139`

**Interfaces:**
- Produces: `ProvenanceData` and `UnverifiedChange` exported interfaces; `Data.provenance` and `Data.unverified` optional fields

- [ ] **Step 1: Add exported interfaces and extend Data**

In `resume_previewer_context.tsx`, after the `ATSScore` interface (line ~61), add:

```ts
export interface ProvenanceData {
  covered: number;
  uncovered: number;
  broken: number;
  uncovered_items?: Array<{ section: string; text: string }>;
  broken_items?: Array<{ section: string; fact_id: string; text: string }>;
}

export interface UnverifiedChange {
  path: string;
  action: string;
  value?: string;
  reason?: string;
  fact_ids: string[];
}
```

Then in the `Data` interface (line ~139), add after `ats_score`:

```ts
provenance?: ProvenanceData | null;
unverified?: UnverifiedChange[];
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd apps/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors related to the new fields.

- [ ] **Step 3: Commit**

```bash
cd apps/frontend && git add components/common/resume_previewer_context.tsx
git commit -m "feat(rh205): extend Data interface with provenance and unverified types"
```

---

### Task 2: Create ProvenancePanel component

**Files:**
- Create: `apps/frontend/components/tailor/provenance-panel.tsx`

**Interfaces:**
- Consumes: `ProvenanceData` from `@/components/common/resume_previewer_context`
- Produces: `ProvenancePanel` React component with props `{ provenance: ProvenanceData | null | undefined; unverifiedCount: number; jobId?: string | null }`

- [ ] **Step 1: Create the component file**

```tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { ProvenanceData } from '@/components/common/resume_previewer_context';
import { useTranslations } from '@/lib/i18n';

interface ProvenancePanelProps {
  provenance: ProvenanceData | null | undefined;
  unverifiedCount: number;
  jobId?: string | null;
}

export function ProvenancePanel({ provenance, unverifiedCount, jobId: _jobId }: ProvenancePanelProps) {
  const { t } = useTranslations();
  const [isExpanded, setIsExpanded] = useState(false);

  if (!provenance) {
    return null;
  }

  const hasDetails =
    (provenance.uncovered_items && provenance.uncovered_items.length > 0) ||
    (provenance.broken_items && provenance.broken_items.length > 0);

  return (
    <div className="border border-black shadow-sw-sm bg-white">
      {/* Status bar */}
      <div className="flex items-center gap-4 p-3 border-b border-black">
        <h3 className="font-serif text-sm font-bold uppercase tracking-tight mr-auto">
          {t('tailor.provenance.title') || 'Provenance'}
        </h3>
        <span className="font-mono text-xs text-success font-bold">
          {provenance.covered} {t('tailor.provenance.covered')}
        </span>
        <span className="font-mono text-xs text-warning font-bold">
          {provenance.uncovered} {t('tailor.provenance.uncovered')}
        </span>
        <span className="font-mono text-xs text-destructive font-bold">
          {provenance.broken} {t('tailor.provenance.broken')}
        </span>
        {hasDetails && (
          <button
            onClick={() => setIsExpanded((v) => !v)}
            className="font-mono text-xs text-ink-soft hover:text-ink transition-colors"
            aria-label={isExpanded ? 'Collapse provenance details' : 'Expand provenance details'}
          >
            {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        )}
      </div>

      {/* Warning rows */}
      <div className="p-3 space-y-2">
        {provenance.uncovered > 0 && (
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-xs text-warning">
              {provenance.uncovered} {t('tailor.provenance.uncovered')} blocks
            </span>
            <Link
              href="/facts?tab=interview"
              className="font-mono text-xs text-primary underline hover:opacity-80 transition-opacity"
            >
              {t('tailor.provenance.verifyGaps')}
            </Link>
          </div>
        )}
        {unverifiedCount > 0 && (
          <p className="font-mono text-xs text-warning font-bold">
            {t('tailor.provenance.unverifiedWarning', { count: String(unverifiedCount) })}
          </p>
        )}
      </div>

      {/* Collapsible detail list */}
      {isExpanded && hasDetails && (
        <div className="border-t border-black p-3 space-y-4">
          {provenance.uncovered_items && provenance.uncovered_items.length > 0 && (
            <div>
              <p className="font-mono text-xs font-bold uppercase tracking-wider mb-2">
                {t('tailor.provenance.uncoveredItems')}
              </p>
              <ul className="space-y-1">
                {provenance.uncovered_items.map((item, idx) => (
                  <li key={idx} className="border border-black p-2 bg-[#FFF7ED]">
                    <span className="font-mono text-xs text-warning font-bold">{item.section}</span>
                    <p className="font-mono text-xs text-ink-soft mt-0.5 line-clamp-2">{item.text}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {provenance.broken_items && provenance.broken_items.length > 0 && (
            <div>
              <p className="font-mono text-xs font-bold uppercase tracking-wider mb-2">
                {t('tailor.provenance.brokenItems')}
              </p>
              <ul className="space-y-1">
                {provenance.broken_items.map((item, idx) => (
                  <li key={idx} className="border border-black p-2 bg-[#FEF2F2]">
                    <span className="font-mono text-xs text-destructive font-bold">{item.section}</span>
                    <span className="font-mono text-xs text-ink-soft ml-2">[{item.fact_id}]</span>
                    <p className="font-mono text-xs text-ink-soft mt-0.5 line-clamp-2">{item.text}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd apps/frontend && git add components/tailor/provenance-panel.tsx
git commit -m "feat(rh205): add ProvenancePanel component"
```

---

### Task 3: Modify DiffPreviewModal to show unverified badges

**Files:**
- Modify: `apps/frontend/components/tailor/diff-preview-modal.tsx`

**Interfaces:**
- Consumes: `UnverifiedChange` from `@/components/common/resume_previewer_context`
- Change: `DiffPreviewModalProps` gains `unverified?: UnverifiedChange[]`; `ChangeItem` gains `isUnverified?: boolean`

- [ ] **Step 1: Add `unverified` prop and thread down to ChangeItem**

1. Import `UnverifiedChange` at the top.
2. Add `unverified?: UnverifiedChange[]` to `DiffPreviewModalProps`.
3. Before the `return` for the main dialog, build a `Set<string>` of unverified paths:
   ```ts
   const unverifiedPaths = new Set((unverified ?? []).map((u) => u.path));
   ```
4. Pass `isUnverified={unverifiedPaths.has(change.field_path)}` to each `<ChangeItem>` call.
5. In `ChangeItemProps`, add `isUnverified?: boolean`.
6. In `ChangeItem`, after the `+/-/~` glyph, add conditional badge:
   ```tsx
   {isUnverified && (
     <span className="font-mono text-xs font-bold text-warning border border-warning px-1 ml-auto shrink-0">
       unverified
     </span>
   )}
   ```

- [ ] **Step 2: Commit**

```bash
cd apps/frontend && git add components/tailor/diff-preview-modal.tsx
git commit -m "feat(rh205): mark unverified changes with amber badge in DiffPreviewModal"
```

---

### Task 4: Wire ProvenancePanel into tailor page

**Files:**
- Modify: `apps/frontend/app/(default)/tailor/page.tsx`

**Interfaces:**
- Consumes: `ProvenancePanel` from `@/components/tailor/provenance-panel`

- [ ] **Step 1: Import and render ProvenancePanel**

1. Add import: `import { ProvenancePanel } from '@/components/tailor/provenance-panel';`
2. After the existing `ATSScoreCard` block (lines 460-465), add:

```tsx
{/* Provenance Panel — shown once a preview result is available */}
{pendingResult?.data?.provenance && (
  <div className="w-full max-w-4xl mt-4">
    <ProvenancePanel
      provenance={pendingResult.data.provenance}
      unverifiedCount={pendingResult.data.unverified?.length ?? 0}
      jobId={pendingResult.data.job_id}
    />
  </div>
)}
```

3. Pass `unverified={pendingResult?.data?.unverified}` to `<DiffPreviewModal>`.

- [ ] **Step 2: Commit**

```bash
cd apps/frontend && git add app/(default)/tailor/page.tsx
git commit -m "feat(rh205): wire ProvenancePanel and unverified prop into tailor page"
```

---

### Task 5: Add i18n translations to all 6 locale files

**Files:**
- Modify: `apps/frontend/messages/en.json`
- Modify: `apps/frontend/messages/es.json`
- Modify: `apps/frontend/messages/zh.json`
- Modify: `apps/frontend/messages/ja.json`
- Modify: `apps/frontend/messages/pt-BR.json`
- Modify: `apps/frontend/messages/fr.json`

- [ ] **Step 1: Add to each locale file inside the `"tailor"` object (before the closing `}`)**

`en.json`:
```json
"provenance": {
  "title": "Provenance",
  "covered": "covered",
  "uncovered": "uncovered",
  "broken": "broken",
  "verifyGaps": "Verify gaps with Interview Mode",
  "unverifiedWarning": "{count} changes without fact support",
  "noProvenance": "No provenance data",
  "uncoveredItems": "Uncovered blocks",
  "brokenItems": "Broken citations"
}
```

`es.json`:
```json
"provenance": {
  "title": "Procedencia",
  "covered": "cubierto",
  "uncovered": "no cubierto",
  "broken": "roto",
  "verifyGaps": "Verificar lagunas con el Modo Entrevista",
  "unverifiedWarning": "{count} cambios sin respaldo de hechos",
  "noProvenance": "Sin datos de procedencia",
  "uncoveredItems": "Bloques no cubiertos",
  "brokenItems": "Citas incorrectas"
}
```

`zh.json`:
```json
"provenance": {
  "title": "来源",
  "covered": "已覆盖",
  "uncovered": "未覆盖",
  "broken": "已损坏",
  "verifyGaps": "通过面试模式验证差距",
  "unverifiedWarning": "{count} 条更改缺乏事实支持",
  "noProvenance": "无来源数据",
  "uncoveredItems": "未覆盖块",
  "brokenItems": "引用错误"
}
```

`ja.json`:
```json
"provenance": {
  "title": "出所",
  "covered": "カバー済み",
  "uncovered": "未カバー",
  "broken": "破損",
  "verifyGaps": "インタビューモードでギャップを確認",
  "unverifiedWarning": "{count} 件の変更が事実に裏付けられていません",
  "noProvenance": "出所データなし",
  "uncoveredItems": "未カバーのブロック",
  "brokenItems": "壊れた引用"
}
```

`pt-BR.json`:
```json
"provenance": {
  "title": "Procedência",
  "covered": "coberto",
  "uncovered": "não coberto",
  "broken": "quebrado",
  "verifyGaps": "Verificar lacunas com o Modo Entrevista",
  "unverifiedWarning": "{count} alterações sem suporte de fatos",
  "noProvenance": "Sem dados de procedência",
  "uncoveredItems": "Blocos não cobertos",
  "brokenItems": "Citações incorretas"
}
```

`fr.json`:
```json
"provenance": {
  "title": "Provenance",
  "covered": "couvert",
  "uncovered": "non couvert",
  "broken": "brisé",
  "verifyGaps": "Vérifier les lacunes avec le Mode Entretien",
  "unverifiedWarning": "{count} modifications sans données de faits",
  "noProvenance": "Aucune donnée de provenance",
  "uncoveredItems": "Blocs non couverts",
  "brokenItems": "Citations incorrectes"
}
```

- [ ] **Step 2: Run locale parity test**

```bash
cd apps/frontend && npx vitest run tests/i18n-locale-parity.test.ts 2>&1 | tail -20
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd apps/frontend && git add messages/
git commit -m "feat(rh205): add tailor.provenance i18n keys to all 6 locale files"
```

---

### Task 6: Write ProvenancePanel tests

**Files:**
- Create: `apps/frontend/tests/provenance-panel.test.tsx`

- [ ] **Step 1: Create the test file**

```tsx
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ProvenancePanel } from '@/components/tailor/provenance-panel';
import type { ProvenanceData } from '@/components/common/resume_previewer_context';

vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({
    t: (key: string, params?: Record<string, string>) => {
      if (params) {
        return Object.entries(params).reduce(
          (str, [k, v]) => str.replace(`{${k}}`, v),
          key
        );
      }
      return key;
    },
  }),
}));

// Next.js Link mock
vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

const baseProvenance: ProvenanceData = {
  covered: 5,
  uncovered: 2,
  broken: 1,
};

describe('ProvenancePanel', () => {
  it('renders covered, uncovered, and broken counts', () => {
    render(<ProvenancePanel provenance={baseProvenance} unverifiedCount={0} />);
    expect(screen.getByText(/5/)).toBeInTheDocument();
    expect(screen.getByText(/2/)).toBeInTheDocument();
    expect(screen.getByText(/1/)).toBeInTheDocument();
  });

  it('shows verify gaps link when uncovered > 0', () => {
    render(<ProvenancePanel provenance={baseProvenance} unverifiedCount={0} />);
    const link = screen.getByRole('link', { name: /tailor\.provenance\.verifyGaps/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/facts?tab=interview');
  });

  it('hides verify gaps link when uncovered === 0', () => {
    const prov: ProvenanceData = { covered: 5, uncovered: 0, broken: 0 };
    render(<ProvenancePanel provenance={prov} unverifiedCount={0} />);
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('shows unverified warning count when unverifiedCount > 0', () => {
    render(<ProvenancePanel provenance={baseProvenance} unverifiedCount={3} />);
    expect(screen.getByText(/3/)).toBeInTheDocument();
  });

  it('renders empty/null provenance gracefully (returns null)', () => {
    const { container } = render(
      <ProvenancePanel provenance={null} unverifiedCount={0} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('shows collapsible detail list when uncovered_items exist and toggle is clicked', () => {
    const prov: ProvenanceData = {
      covered: 2,
      uncovered: 1,
      broken: 0,
      uncovered_items: [{ section: 'experience', text: 'Led team of 10 engineers' }],
    };
    render(<ProvenancePanel provenance={prov} unverifiedCount={0} />);
    const toggle = screen.getByRole('button', { name: /expand provenance details/i });
    expect(screen.queryByText('Led team of 10 engineers')).not.toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.getByText('Led team of 10 engineers')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests**

```bash
cd apps/frontend && npx vitest run tests/provenance-panel.test.tsx 2>&1 | tail -30
```

Expected: 6 tests PASS

- [ ] **Step 3: Commit**

```bash
cd apps/frontend && git add tests/provenance-panel.test.tsx
git commit -m "test(rh205): provenance panel unit tests"
```

---

### Task 7: Final lint and full test pass

- [ ] **Step 1: Run lint**

```bash
cd apps/frontend && npm run lint 2>&1 | tail -30
```

Expected: no errors

- [ ] **Step 2: Run full test suite**

```bash
cd apps/frontend && npm run test 2>&1 | tail -30
```

Expected: all tests pass (previous count + 6 new)

- [ ] **Step 3: Commit if any format fixes needed**

```bash
cd apps/frontend && npm run format && git add -p && git commit -m "chore: format after rh205 implementation"
```
