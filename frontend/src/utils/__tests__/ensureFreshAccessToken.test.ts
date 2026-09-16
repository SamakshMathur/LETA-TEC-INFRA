import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { ensureFreshAccessToken } from '../interceptors';

/**
 * Regression coverage for a real gap found during a flow audit: LetaWorkspace's
 * /ask and /ask-with-file calls use raw fetch (streaming a response body
 * through axios is awkward), which never touches the axios interceptor's
 * automatic proactive token refresh. A long compose or a slow upload could
 * carry the token past its 15-minute expiry and hit a hard "please log in
 * again" with no retry — even though the 7-day refresh token was still
 * perfectly valid. ensureFreshAccessToken() is the same proactive-refresh
 * check, exported so those raw-fetch call sites can run it explicitly.
 */
describe('ensureFreshAccessToken', () => {
  const STORAGE_KEY = 'pro.auth.session';

  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('refreshes and persists new tokens when the access token is within 10s of expiring', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      tokens: {
        accessToken: 'old-access', refreshToken: 'refresh-1',
        expiresAt: new Date(Date.now() + 5000).toISOString(), // 5s left
        refreshTokenExpiresAt: '2099-01-01T00:00:00Z',
      },
      user: {}, memberships: [], organizationId: 'org1',
    }));

    // interceptors.ts's doTokenRefresh calls a plain (non-AXIOS_INSTANCE)
    // axios.post directly, specifically to avoid looping back through its
    // own interceptors — spy on that real call rather than mocking the
    // whole module (which would also break AXIOS_INSTANCE's own
    // axios.create() call in utils/api.ts).
    const postSpy = vi.spyOn(axios, 'post').mockResolvedValue({
      data: { tokens: { accessToken: 'new-access', refreshToken: 'refresh-2', expiresAt: new Date(Date.now() + 900000).toISOString() } },
    });

    await ensureFreshAccessToken();
    postSpy.mockRestore();

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(stored.tokens.accessToken).toBe('new-access');
  });

  it('does nothing when the token is not close to expiring', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      tokens: {
        accessToken: 'still-good', refreshToken: 'refresh-1',
        expiresAt: new Date(Date.now() + 10 * 60 * 1000).toISOString(), // 10 min left
      },
      user: {}, memberships: [], organizationId: 'org1',
    }));

    await ensureFreshAccessToken();

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    expect(stored.tokens.accessToken).toBe('still-good'); // unchanged
  });

  it('does nothing when there is no stored session at all', async () => {
    await expect(ensureFreshAccessToken()).resolves.toBeUndefined();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
