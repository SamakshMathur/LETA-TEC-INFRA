import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { join } from 'path';

/**
 * Regression coverage for a real gap found during a UX audit: the
 * Suspense fallback shown during lazy-loaded route transitions was a
 * bare colored div with no spinner or skeleton — every route transition
 * that hit an unfetched chunk showed a frozen, unresponsive-looking
 * blank screen until the JS resolved, with nothing to tell a user
 * anything was happening.
 *
 * App.tsx isn't cleanly importable in isolation here (it wires up the
 * full router, all lazy page chunks, and BrowserRouter's own history
 * API, which the test environment doesn't provide) — so this checks the
 * source directly for the specific regression: a Suspense fallback with
 * no visible loading indicator.
 */
describe('App — route loading fallback', () => {
  it('the Suspense fallback is not a bare empty div with no loading indicator', () => {
    const source = readFileSync(join(__dirname, '../App.tsx'), 'utf-8');
    // The old regression, verbatim: a self-closing div with nothing
    // inside it — no spinner, no status role, no feedback of any kind.
    expect(source).not.toContain(
      "<Suspense fallback={<div style={{ background: '#060816', minHeight: '100vh' }} />}>"
    );
    expect(source).toContain('<Suspense fallback={<RouteLoadingFallback />}>');
    expect(source).toContain('role="status"');
    expect(source).toContain('aria-label="Loading"');
  });
});
