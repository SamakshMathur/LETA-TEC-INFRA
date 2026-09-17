import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * Regression coverage for a real gap found during a UX audit:
 * LetaWorkspace's left sidebar (320px) and right reference/PDF viewer
 * (340px) were both permanent, fixed-width in-flow columns. On a phone
 * screen (~375-414px wide), the two together already exceed the viewport,
 * leaving zero — or negative — width for the actual chat, the app's core
 * feature. Below md (768px) the sidebar now becomes a fixed overlay drawer
 * with a tap-to-dismiss backdrop, and the reference viewer becomes a
 * full-screen overlay, both reverting to their original in-flow desktop
 * layout at md and above.
 *
 * Not practical to mount LetaWorkspace directly here (three.js/pdf.js/live
 * API client) — following this codebase's existing source-level test
 * pattern for this file (see accessibilityLabels.test.ts).
 */

const workspaceSource = readFileSync(
  join(__dirname, '../LetaWorkspace.tsx'),
  'utf-8'
);

describe('LetaWorkspace — sidebar is a mobile overlay drawer, not a fixed column', () => {
  it('defaults open on desktop widths but closed on phone widths', () => {
    expect(workspaceSource).toContain(
      "() => typeof window === 'undefined' || window.innerWidth >= 768"
    );
  });

  it('is fixed + full-height below md, back to normal flow at md and above', () => {
    expect(workspaceSource).toContain(
      "fixed md:relative inset-y-0 left-0 md:inset-auto z-30 md:z-10"
    );
  });

  it('is capped to a sane max width on narrow phones', () => {
    expect(workspaceSource).toContain("maxWidth: '85vw'");
  });

  it('has a tap-to-dismiss backdrop that only exists below md', () => {
    expect(workspaceSource).toContain('bg-black/60 md:hidden');
    expect(workspaceSource).toContain('onClick={() => setIsSidebarOpen(false)}');
  });
});

describe('LetaWorkspace — reference viewer is a full-screen overlay on mobile', () => {
  it('is a fixed full-screen overlay below md, an in-flow 340px column at md and above', () => {
    expect(workspaceSource).toContain(
      'fixed inset-0 z-40 md:relative md:inset-auto md:z-10 w-full md:w-[340px]'
    );
  });
});
