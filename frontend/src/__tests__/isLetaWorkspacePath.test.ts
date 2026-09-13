import { describe, it, expect } from 'vitest';
import { isLetaWorkspacePath } from '../App';

/**
 * Regression coverage for the double-header bug reported live right
 * after per-chat URLs shipped: App.tsx's Layout decides whether to
 * render the global Navbar/SystemFooter around a page, or give it the
 * workspace's own full-screen layout, based on whether the current path
 * IS the LetaWorkspace chat page. It used `.endsWith('/leta')`, which
 * only matches the bare "/gst/leta" URL — the moment a chat opened and
 * the URL became "/gst/leta/<sessionId>", the check went false and the
 * global chrome rendered on top of the workspace's own header/footer.
 */
describe('isLetaWorkspacePath', () => {
  it('matches the bare workspace URL, with or without a trailing slash', () => {
    expect(isLetaWorkspacePath('/gst/leta')).toBe(true);
    expect(isLetaWorkspacePath('/gst/leta/')).toBe(true);
  });

  it('matches a per-chat URL — the exact case that broke in production', () => {
    expect(isLetaWorkspacePath('/gst/leta/70c28367-4745-4f19-8490-ee842680a82f')).toBe(true);
    expect(isLetaWorkspacePath('/fema/leta/some-session-id')).toBe(true);
  });

  it('matches every live domain', () => {
    for (const domain of ['gst', 'fema', 'company-law', 'income-tax']) {
      expect(isLetaWorkspacePath(`/${domain}/leta`)).toBe(true);
      expect(isLetaWorkspacePath(`/${domain}/leta/abc123`)).toBe(true);
    }
  });

  it('does not match other routes (these should keep the global Navbar/Footer)', () => {
    expect(isLetaWorkspacePath('/dashboard')).toBe(false);
    expect(isLetaWorkspacePath('/gst')).toBe(false);
    expect(isLetaWorkspacePath('/')).toBe(false);
    expect(isLetaWorkspacePath('/about')).toBe(false);
    // Not a real route, but guards against overly loose matching (e.g. a
    // naive `.includes('leta')` would wrongly match this).
    expect(isLetaWorkspacePath('/gst/letaXYZ')).toBe(false);
  });
});
