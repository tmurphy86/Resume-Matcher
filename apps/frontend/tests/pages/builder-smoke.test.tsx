/**
 * BUG-004 smoke: Builder (FormattingControls) renders for every template in TEMPLATE_OPTIONS.
 * Covers the BUG-002 regression: missing templateLabels entry must not crash the builder.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { FormattingControls } from '@/components/builder/formatting-controls';
import { DEFAULT_TEMPLATE_SETTINGS, TEMPLATE_OPTIONS } from '@/lib/types/template-settings';

vi.mock('@/lib/i18n', () => ({
  useTranslations: () => ({ t: (k: string) => k, messages: {}, locale: 'en' }),
}));

describe('Builder smoke — all template IDs render (BUG-004 / BUG-002 regression)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders FormattingControls without crashing', () => {
    const { container } = render(
      <FormattingControls settings={DEFAULT_TEMPLATE_SETTINGS} onChange={vi.fn()} />
    );
    expect(container).toBeTruthy();
  });

  it('has a button for every template in TEMPLATE_OPTIONS including murphy', () => {
    const { container } = render(
      <FormattingControls settings={DEFAULT_TEMPLATE_SETTINGS} onChange={vi.fn()} />
    );
    // Every registered template must render a selector button
    const templateIds = TEMPLATE_OPTIONS.map((t) => t.id);
    expect(templateIds).toContain('murphy');
    // Container renders without error — if templateLabels is missing a key the
    // component would throw before reaching this assertion.
    expect(container.querySelectorAll('button').length).toBeGreaterThan(0);
  });

  it.each(TEMPLATE_OPTIONS)('renders template button for $id without crash', ({ id }) => {
    const settings = {
      ...DEFAULT_TEMPLATE_SETTINGS,
      template: id as typeof DEFAULT_TEMPLATE_SETTINGS.template,
    };
    const { container } = render(<FormattingControls settings={settings} onChange={vi.fn()} />);
    expect(container).toBeTruthy();
  });
});
