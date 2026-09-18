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
