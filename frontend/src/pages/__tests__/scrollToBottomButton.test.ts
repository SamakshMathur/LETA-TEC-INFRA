import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * Regression coverage for a real UX complaint: the floating "scroll to
 * bottom" button was centered (left-1/2) directly in the middle of the
 * reading column, which put it on top of whatever line of the answer
 * happened to be at the bottom of the viewport — the worst possible spot
 * for an overlay, and it regularly obscured text. Moved to the
 * bottom-right corner, matching where every other chat UI (Slack,
 * Discord, WhatsApp Web) puts a "jump to latest" control.
 *
 * Also fixed while in there: the button's background was a hardcoded
 * rgba(0,0,0,0.85), which read as a floating black pill against the
 * light workspace theme's cream background.
 */

const workspaceSource = readFileSync(join(__dirname, '../LetaWorkspace.tsx'), 'utf-8');

describe('LetaWorkspace — scroll-to-bottom button placement', () => {
  it('is anchored to the bottom-right corner, not centered in the reading column', () => {
    expect(workspaceSource).toContain('absolute bottom-6 right-6 z-20');
    expect(workspaceSource).not.toContain('absolute bottom-6 left-1/2');
  });

  it('uses a theme-aware background instead of a hardcoded dark overlay', () => {
    expect(workspaceSource).toContain("background: 'var(--ws-surface)'");
  });
});
