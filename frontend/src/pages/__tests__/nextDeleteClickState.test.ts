import { describe, it, expect } from 'vitest';
import { nextDeleteClickState } from '../LetaWorkspace';

/**
 * Regression coverage for a real data-loss risk found during a UX audit:
 * deleting a chat session used to fire on a single click of a hover-only
 * trash icon — one accidental click during a hover-sweep over the row
 * permanently destroyed a client's whole consultation history, with no
 * confirmation and no way to recover it. nextDeleteClickState is the pure
 * decision behind the fix: the first click on a row only arms it; a
 * second click on the SAME row is what actually deletes.
 */
describe('nextDeleteClickState', () => {
  it('first click on a row arms it, does not delete', () => {
    const result = nextDeleteClickState(null, 'session-1');
    expect(result.shouldDelete).toBe(false);
    expect(result.newPendingId).toBe('session-1');
  });

  it('second click on the SAME already-armed row deletes', () => {
    const result = nextDeleteClickState('session-1', 'session-1');
    expect(result.shouldDelete).toBe(true);
    expect(result.newPendingId).toBeNull();
  });

  it('clicking a DIFFERENT row while one is armed re-arms the new row instead of deleting either', () => {
    const result = nextDeleteClickState('session-1', 'session-2');
    expect(result.shouldDelete).toBe(false);
    expect(result.newPendingId).toBe('session-2');
  });

  it('after a delete fires, the next click on that same id starts fresh (arms, does not delete)', () => {
    // Simulates: click, click (deletes, pendingId resets to null) — the
    // session is gone now, but if a *new* session somehow reused that
    // exact id, a stray click right after must not immediately delete it.
    const armed = nextDeleteClickState(null, 'session-1');
    const deleted = nextDeleteClickState(armed.newPendingId, 'session-1');
    expect(deleted.shouldDelete).toBe(true);

    const afterReset = nextDeleteClickState(deleted.newPendingId, 'session-1');
    expect(afterReset.shouldDelete).toBe(false);
  });
});
