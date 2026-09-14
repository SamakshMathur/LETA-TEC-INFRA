import { describe, it, expect } from 'vitest';
import { resolveSessionRestore } from '../LetaWorkspace';

/**
 * Regression coverage for a live report: opening a shared per-chat URL
 * (/:domainId/leta/:sessionId) under a DIFFERENT account than the one that
 * created it silently fell through to the ordinary empty-chat landing
 * screen — no error, no explanation, indistinguishable from "the share
 * feature is broken". It was working as scoped (per-chat URLs are
 * owner-only, not cross-account, by design — GET /api/sessions/{id} is
 * scoped server-side to the requesting user) but failing *silently*.
 */
describe('resolveSessionRestore', () => {
  it('restores the session when the URL id is in the account\'s own list', () => {
    const result = resolveSessionRestore('abc123', null, ['abc123', 'xyz789']);
    expect(result).toEqual({ restoreId: 'abc123', restoreError: null });
  });

  it('restores from the sessionStorage fallback when there is no URL id', () => {
    const result = resolveSessionRestore(undefined, 'abc123', ['abc123', 'xyz789']);
    expect(result).toEqual({ restoreId: 'abc123', restoreError: null });
  });

  it('the URL id takes priority over the sessionStorage fallback', () => {
    const result = resolveSessionRestore('xyz789', 'abc123', ['abc123', 'xyz789']);
    expect(result.restoreId).toBe('xyz789');
  });

  it('surfaces a clear error for a URL id not owned by the current account — the exact bug reported live', () => {
    const result = resolveSessionRestore('70c28367-4745-4f19-8490-ee842680a82f', null, ['abc123']);
    expect(result.restoreId).toBeNull();
    expect(result.restoreError).toMatch(/isn't available under your current login/i);
  });

  it('does NOT surface an error for a missing sessionStorage fallback (unremarkable, not worth alarming the user)', () => {
    const result = resolveSessionRestore(undefined, 'some-stale-id', ['abc123']);
    expect(result).toEqual({ restoreId: null, restoreError: null });
  });

  it('does nothing when there is no URL id and no sessionStorage fallback (ordinary fresh visit)', () => {
    const result = resolveSessionRestore(undefined, null, ['abc123']);
    expect(result).toEqual({ restoreId: null, restoreError: null });
  });
});
