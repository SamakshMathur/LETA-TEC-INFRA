import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { join } from 'path';
import { nextWorkspaceTheme, WORKSPACE_THEME_STORAGE_KEY } from '../LetaWorkspace';

/**
 * Regression coverage for the chat workspace's light/dark theme toggle —
 * added after beta feedback flagged the pure-black background as hard to
 * read. Scoped ONLY to the workspace (chat page); the rest of the site is
 * untouched, via a [data-workspace-theme] attribute + a --ws-* CSS
 * variable block in tokens.css that's completely separate from the
 * site-wide :root tokens.
 *
 * LetaWorkspace.tsx itself is too heavy to mount directly here
 * (three.js/pdf.js/live API client) — source-text checks follow the
 * existing pattern for this file (see accessibilityLabels.test.ts).
 */

describe('nextWorkspaceTheme', () => {
  it('toggles dark to light', () => {
    expect(nextWorkspaceTheme('dark')).toBe('light');
  });

  it('toggles light to dark', () => {
    expect(nextWorkspaceTheme('light')).toBe('dark');
  });
});

describe('WORKSPACE_THEME_STORAGE_KEY', () => {
  it('is a stable, namespaced localStorage key', () => {
    expect(WORKSPACE_THEME_STORAGE_KEY).toBe('leta.workspace.theme');
  });
});

const workspaceSource = readFileSync(join(__dirname, '../LetaWorkspace.tsx'), 'utf-8');
const tokensSource = readFileSync(join(__dirname, '../../styles/tokens.css'), 'utf-8');

describe('LetaWorkspace — theme wiring', () => {
  it('persists the chosen theme to localStorage', () => {
    expect(workspaceSource).toContain(
      'localStorage.setItem(WORKSPACE_THEME_STORAGE_KEY, workspaceTheme)'
    );
  });

  it('reads the saved theme back on mount, defaulting to dark', () => {
    expect(workspaceSource).toContain(
      "() => (localStorage.getItem(WORKSPACE_THEME_STORAGE_KEY) as WorkspaceTheme) || 'dark'"
    );
  });

  it('sets data-workspace-theme on the root element so tokens.css can scope to it', () => {
    expect(workspaceSource).toContain('data-workspace-theme={workspaceTheme}');
  });

  it('has a toggle button with a theme-aware accessible label', () => {
    expect(workspaceSource).toContain(
      "aria-label={workspaceTheme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}"
    );
  });
});

describe('tokens.css — workspace theme palette', () => {
  it('defines a dark palette scoped to [data-workspace-theme="dark"]', () => {
    expect(tokensSource).toContain('[data-workspace-theme="dark"]');
  });

  it('defines a light ("warm paper") palette scoped to [data-workspace-theme="light"]', () => {
    expect(tokensSource).toContain('[data-workspace-theme="light"]');
    expect(tokensSource).toContain('--ws-bg:              #F7F3EC;');
  });

  it('does not touch the site-wide :root tokens the rest of the app uses', () => {
    // The existing --color-* tokens (used everywhere else) must be
    // completely unaffected by adding the workspace-only --ws-* block.
    expect(tokensSource).toContain('--color-bg-main:          #000000;');
  });
});

/**
 * Regression coverage for a real, severe bug found right after shipping:
 * the empty-state greeting heading, the user's own message bubble text,
 * and a file-error message all used hardcoded light-on-dark hex colors
 * (#E8DDD0, #E4E4E7, #F87171) that were never converted to var(--ws-*) —
 * on the light theme's cream background they measured 1.03–2.5:1
 * contrast, i.e. functionally invisible. A hand-picked list of "the
 * colors I remembered to check" clearly isn't enough — this scans BOTH
 * workspace-tree files for every literal hex color still used as a solid
 * (non-translucent) text color, computes its real contrast against the
 * light theme's actual background, and fails on anything under 3:1.
 * Translucent usages (border-[#hex]/10, bg-[#hex]/[0.04]) and var(...)
 * fallbacks are intentionally excluded — see the PR description for why
 * those are fine to leave as literal hex.
 */
describe('workspace source — no invisible literal text colors on the light theme', () => {
  const LIGHT_BG = '#F7F3EC';

  function srgbToLinear(c: number): number {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }
  function relativeLuminance(hex: string): number {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
  }
  function contrastRatio(hexA: string, hexB: string): number {
    const lA = relativeLuminance(hexA);
    const lB = relativeLuminance(hexB);
    const lighter = Math.max(lA, lB);
    const darker = Math.min(lA, lB);
    return (lighter + 0.05) / (darker + 0.05);
  }

  function findLowContrastLiterals(source: string): string[] {
    const offenders: string[] = [];
    const hexPattern = /#[0-9A-Fa-f]{6}/g;
    let match: RegExpExecArray | null;
    while ((match = hexPattern.exec(source)) !== null) {
      const hex = match[0];
      const before = source.slice(Math.max(0, match.index - 45), match.index);
      // Skip var(--x,#hex) fallbacks — only meaningful outside the workspace.
      const varSplit = before.split('var(');
      if (varSplit.length > 1 && varSplit[varSplit.length - 1].includes(',')) continue;
      // Skip translucent usages: #hex]/10, #hex]/[0.04], #hex/20, etc.
      const after = source.slice(hexPattern.lastIndex, hexPattern.lastIndex + 10);
      if (/\]?\/(\d|\[)/.test(after)) continue;
      const ratio = contrastRatio(hex, LIGHT_BG);
      if (ratio < 3.0) offenders.push(`${hex} (${ratio.toFixed(2)}:1)`);
    }
    return offenders;
  }

  it('LetaWorkspace.tsx has no solid text color under 3:1 against the light background', () => {
    expect(findLowContrastLiterals(workspaceSource)).toEqual([]);
  });

  it('LetaResponse.jsx has no solid text color under 3:1 against the light background', () => {
    const letaResponseSource = readFileSync(
      join(__dirname, '../../components/leta/LetaResponse.jsx'),
      'utf-8'
    );
    expect(findLowContrastLiterals(letaResponseSource)).toEqual([]);
  });
});
