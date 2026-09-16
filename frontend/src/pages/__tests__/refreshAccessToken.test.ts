import { describe, it, expect, vi, beforeEach } from 'vitest';
import { refreshAccessToken } from '../Payment';

/**
 * Regression coverage for a real bug found during a flow audit: a
 * successful payment could silently revert the customer's login token to
 * a near-expired one, right as they finished paying.
 *
 * Root cause: refreshAccessToken used to write the refreshed tokens
 * straight to localStorage only, never touching AuthContext's React
 * state via login(). Payment.tsx's success/duplicate handlers then called
 * login({...session, ...}) using `session` — a value captured once from
 * useAuth() at render time, which never picked up the refresh. That
 * login() call writes the ENTIRE session object back to localStorage
 * (see lib/auth-storage.ts's storeAuthSession), so it clobbered the
 * fresh tokens refreshAccessToken had just written moments earlier — a
 * customer could see a 401 on the very next request right after paying.
 *
 * Fix: refreshAccessToken now takes `login` and writes the refreshed
 * tokens through it, so localStorage and React state update together,
 * at the point of refresh, instead of drifting apart until some later
 * code path re-syncs them (or, as here, overwrites the sync by mistake).
 */
describe('refreshAccessToken', () => {
  const STORAGE_KEY = 'pro.auth.session';

  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('calls login() with the refreshed tokens merged onto the stored session, not just localStorage', async () => {
    const storedSession = {
      tokens: {
        accessToken: 'old-access', refreshToken: 'refresh-1',
        expiresAt: '2026-01-01T00:00:00Z', refreshTokenExpiresAt: '2099-01-01T00:00:00Z',
      },
      user: { id: 'u1', full_name: 'Alice', email: 'alice@example.com', role: 'user', plan: 'basic' },
      memberships: [{ organizationId: 'org1', role: 'member' }],
      organizationId: 'org1',
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(storedSession));

    const newTokens = { accessToken: 'new-access', refreshToken: 'refresh-2', expiresAt: '2026-01-01T00:20:00Z' };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ tokens: newTokens }),
    }));

    const loginSpy = vi.fn();
    await refreshAccessToken(loginSpy);

    expect(loginSpy).toHaveBeenCalledTimes(1);
    const [calledSession, persist] = loginSpy.mock.calls[0];
    expect(persist).toBe(true);
    expect(calledSession.tokens.accessToken).toBe('new-access');
    expect(calledSession.tokens.refreshToken).toBe('refresh-2');
    expect(calledSession.organizationId).toBe('org1'); // rest of the session preserved
    expect(calledSession.user.email).toBe('alice@example.com');
  });

  it('does not call login() when there is no stored session at all', async () => {
    vi.stubGlobal('fetch', vi.fn());
    const loginSpy = vi.fn();

    await refreshAccessToken(loginSpy);

    expect(loginSpy).not.toHaveBeenCalled();
  });

  it('does not call login() when the refresh request fails', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      tokens: { accessToken: 'old', refreshToken: 'refresh-1' },
      user: {}, memberships: [], organizationId: 'org1',
    }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    const loginSpy = vi.fn();

    await refreshAccessToken(loginSpy);

    expect(loginSpy).not.toHaveBeenCalled();
  });

  it('never throws even if fetch itself rejects (network error) — non-fatal by design', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      tokens: { accessToken: 'old', refreshToken: 'refresh-1' },
      user: {}, memberships: [], organizationId: 'org1',
    }));
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    const loginSpy = vi.fn();

    await expect(refreshAccessToken(loginSpy)).resolves.toBeUndefined();
    expect(loginSpy).not.toHaveBeenCalled();
  });
});
