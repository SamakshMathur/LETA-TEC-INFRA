import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * Regression coverage for real gaps found during a UX audit: LetaWorkspace.tsx
 * (2813 lines, the core chat workspace) had zero aria-label attributes —
 * icon-only controls like the mic-error dismiss button announced only
 * "button" to a screen reader, with no indication of what it does.
 * ModuleDashboard's pricing modal close button had the same problem, plus
 * used a body-text color (#334155) measuring ~1.4:1 contrast against its
 * near-black background — well under WCAG's minimum.
 *
 * Neither file is practical to fully mount in isolation here (LetaWorkspace
 * pulls in three.js/pdf.js/a live API client; ModuleDashboard pulls in
 * three.js for its particle background) — existing tests for both files
 * already take this same source-level approach (see
 * workspaceRouteRemount.test.tsx's own note on this). Checking the actual
 * source is still a real, meaningful regression guard: it fails exactly
 * when someone removes one of these attributes, the same as it would if
 * the component were mounted and queried directly.
 */

const workspaceSource = readFileSync(
  join(__dirname, '../LetaWorkspace.tsx'),
  'utf-8'
);
const dashboardSource = readFileSync(
  join(__dirname, '../ModuleDashboard.tsx'),
  'utf-8'
);

describe('LetaWorkspace — icon-only controls have accessible names', () => {
  it.each([
    ['sidebar toggle', 'aria-label={isSidebarOpen ? \'Hide consultations list\' : \'Show consultations list\'}'],
    ['mic/voice toggle', "aria-label={isRecording ? 'Stop voice recording' : 'Voice input (click to speak)'}"],
    ['mic error dismiss', 'aria-label="Dismiss microphone error"'],
    ['remove attached file', 'aria-label="Remove attached file"'],
    ['dismiss file validation error', 'aria-label="Dismiss file error"'],
    ['attach document', 'aria-label="Attach document"'],
  ])('%s has an aria-label', (_name, snippet) => {
    expect(workspaceSource).toContain(snippet);
  });
});

describe('ModuleDashboard — pricing modal close button', () => {
  it('has an aria-label', () => {
    expect(dashboardSource).toContain('aria-label="Close"');
  });

  it('no longer uses the ~1.4:1-contrast color for its default state', () => {
    // #334155 measured ~1.4:1 against the modal's near-black background —
    // well under WCAG's 3:1 minimum for UI components, let alone the
    // 4.5:1 real text would need. #64748B is the same muted tone at a
    // contrast that actually passes.
    expect(dashboardSource).not.toContain("style={{ color: '#334155' }}\n              onMouseEnter");
  });
});
