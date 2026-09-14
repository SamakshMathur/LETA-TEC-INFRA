import { describe, it, expect } from 'vitest';
import { classifySessionLoadError } from '../LetaWorkspace';

/**
 * Regression coverage for the two real ways GET /api/sessions/{id} can
 * fail inside handleSelectSession, now that shared (cross-account,
 * read-only) chats exist:
 *
 *   - An explicit URL restore (share link, bookmark) hitting a genuine
 *     404 is the common real case now: opened under an account the chat
 *     wasn't shared with, or a stale/mistyped id. That's not a glitch —
 *     retrying won't help — so it gets an honest explanation instead of
 *     a generic "please try again".
 *   - Every other failure (a sidebar click on a session that really
 *     should have loaded, a network error, a 500) keeps the older
 *     generic in-chat fallback message.
 */
describe('classifySessionLoadError', () => {
  it('an explicit URL restore that 404s gets the honest access-denied message', () => {
    const result = classifySessionLoadError(404, true);
    expect(result.restoreError).toMatch(/isn't available under your current login/i);
    expect(result.fallbackMessage).toBeNull();
  });

  it('a normal sidebar-click 404 (not an explicit URL restore) keeps the generic fallback', () => {
    const result = classifySessionLoadError(404, false);
    expect(result.restoreError).toBeNull();
    expect(result.fallbackMessage).toMatch(/unable to load this consultation/i);
  });

  it('an explicit URL restore with a non-404 failure (network error, 500) keeps the generic fallback', () => {
    const result = classifySessionLoadError(500, true);
    expect(result.restoreError).toBeNull();
    expect(result.fallbackMessage).toMatch(/unable to load this consultation/i);
  });

  it('an explicit URL restore with no status at all (network failure) keeps the generic fallback', () => {
    const result = classifySessionLoadError(undefined, true);
    expect(result.restoreError).toBeNull();
    expect(result.fallbackMessage).toMatch(/unable to load this consultation/i);
  });
});
