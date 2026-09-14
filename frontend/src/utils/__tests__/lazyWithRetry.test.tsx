import { describe, it, expect, vi, beforeEach } from 'vitest';
import { lazyWithRetry } from '../lazyWithRetry';

/**
 * Regression coverage for the "Something went wrong / Failed to fetch
 * dynamically imported module" crash reported live on launch day — hit
 * "constantly" because this app deploys several times an hour and any
 * tab left open across a deploy holds stale chunk-hash references.
 */

const RELOAD_GUARD_KEY = 'leta.chunkLoadReloadAttempted';

describe('lazyWithRetry', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('reloads once on a stale-chunk fetch failure, without ever rejecting to the caller', async () => {
    const reloadSpy = vi.fn();
    vi.stubGlobal('location', { ...window.location, reload: reloadSpy });

    const factory = vi.fn().mockRejectedValue(
      new TypeError('Failed to fetch dynamically imported module: https://letatec.com/assets/LetaWorkspace-CYmpIWUP.js')
    );

    const Lazy = lazyWithRetry(factory as unknown as () => Promise<{ default: React.ComponentType }>);
    // React.lazy defers the factory call until first render/access of the
    // component's internal promise — trigger it directly the same way
    // React does, via the lazy component's `_init`/`_payload`, is not
    // public API, so instead assert on the underlying factory contract:
    // calling the wrapped factory should reload and never settle.
    const wrapped = (Lazy as unknown as { _payload: { _result: () => Promise<unknown> } })._payload._result;

    let settled = false;
    wrapped().then(() => { settled = true; }).catch(() => { settled = true; });
    // Flush microtasks
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(factory).toHaveBeenCalledTimes(1);
    expect(reloadSpy).toHaveBeenCalledTimes(1);
    expect(settled).toBe(false); // deliberately never resolves/rejects — reload is already navigating away
    expect(sessionStorage.getItem(RELOAD_GUARD_KEY)).toBe('1');
  });

  it('does not reload a second time for a repeat failure in the same session (avoids a reload loop)', async () => {
    sessionStorage.setItem(RELOAD_GUARD_KEY, '1'); // simulate: already reloaded once this session
    const reloadSpy = vi.fn();
    vi.stubGlobal('location', { ...window.location, reload: reloadSpy });

    const factory = vi.fn().mockRejectedValue(
      new TypeError('Failed to fetch dynamically imported module: https://letatec.com/assets/Home-abc123.js')
    );
    const Lazy = lazyWithRetry(factory as unknown as () => Promise<{ default: React.ComponentType }>);
    const wrapped = (Lazy as unknown as { _payload: { _result: () => Promise<unknown> } })._payload._result;

    await expect(wrapped()).rejects.toThrow(/Failed to fetch dynamically imported module/);
    expect(reloadSpy).not.toHaveBeenCalled();
  });

  it('passes through a genuinely different error without reloading', async () => {
    const reloadSpy = vi.fn();
    vi.stubGlobal('location', { ...window.location, reload: reloadSpy });

    const factory = vi.fn().mockRejectedValue(new Error('some unrelated render error'));
    const Lazy = lazyWithRetry(factory as unknown as () => Promise<{ default: React.ComponentType }>);
    const wrapped = (Lazy as unknown as { _payload: { _result: () => Promise<unknown> } })._payload._result;

    await expect(wrapped()).rejects.toThrow('some unrelated render error');
    expect(reloadSpy).not.toHaveBeenCalled();
  });

  it('clears the reload guard after a successful load, so a later deploy gets its own one-shot reload', async () => {
    sessionStorage.setItem(RELOAD_GUARD_KEY, '1');
    const factory = vi.fn().mockResolvedValue({ default: () => null });
    const Lazy = lazyWithRetry(factory as unknown as () => Promise<{ default: React.ComponentType }>);
    const wrapped = (Lazy as unknown as { _payload: { _result: () => Promise<unknown> } })._payload._result;

    await wrapped();
    expect(sessionStorage.getItem(RELOAD_GUARD_KEY)).toBeNull();
  });
});
