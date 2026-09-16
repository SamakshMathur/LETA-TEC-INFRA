import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { AuthProvider } from '../AuthContext';
import { useAuth } from '../../hooks/useAuth';
import { STORAGE_KEY } from '../../lib/auth-storage';

/**
 * Regression coverage for a real gap found during a flow audit: logging
 * out in one browser tab left every OTHER open tab still believing it was
 * logged in. AuthContext's session state was only ever read from
 * localStorage once, on mount — nothing re-checked it afterward — so a
 * second tab would keep sending requests with a token that may no longer
 * be valid until something else (a 401, a manual reload) forced a
 * re-check.
 *
 * The browser's own `storage` event fires in every tab OTHER than the one
 * that made the localStorage write, which is exactly the signal needed
 * here — this is real jsdom `StorageEvent` dispatch, not a mock of
 * AuthContext's internals.
 */

function makeSession(overrides: Partial<{ accessToken: string }> = {}) {
  return {
    tokens: {
      accessToken: overrides.accessToken || 'access-1',
      refreshToken: 'refresh-1',
      expiresAt: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
      refreshTokenExpiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    },
    user: { id: 'u1', full_name: 'Alice', email: 'alice@example.com', role: 'user', plan: 'basic' },
    memberships: [{ organizationId: 'org1', role: 'member' }],
    organizationId: 'org1',
  };
}

function Probe() {
  const { isLoggedIn, session } = useAuth();
  return (
    <div>
      <span data-testid="logged-in">{String(isLoggedIn)}</span>
      <span data-testid="access-token">{session?.tokens?.accessToken || 'none'}</span>
    </div>
  );
}

describe('AuthContext — cross-tab sync via the storage event', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('logging out in another tab (localStorage cleared) logs this tab out too', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeSession()));

    render(<AuthProvider><Probe /></AuthProvider>);

    expect(await screen.findByText('true')).toBeTruthy();

    // Simulate another tab calling clearAuthSession() — localStorage.removeItem
    // fires a real "storage" event with newValue: null in every OTHER tab.
    act(() => {
      localStorage.removeItem(STORAGE_KEY);
      window.dispatchEvent(new StorageEvent('storage', { key: STORAGE_KEY, newValue: null }));
    });

    expect(await screen.findByText('false')).toBeTruthy();
  });

  it('a token refreshed in another tab is picked up here too', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeSession({ accessToken: 'access-1' })));

    render(<AuthProvider><Probe /></AuthProvider>);

    expect(await screen.findByText('access-1')).toBeTruthy();

    const refreshed = makeSession({ accessToken: 'access-2' });
    act(() => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(refreshed));
      window.dispatchEvent(new StorageEvent('storage', { key: STORAGE_KEY, newValue: JSON.stringify(refreshed) }));
    });

    expect(await screen.findByText('access-2')).toBeTruthy();
  });

  it('ignores storage events for unrelated keys', async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(makeSession()));

    render(<AuthProvider><Probe /></AuthProvider>);
    expect(await screen.findByText('true')).toBeTruthy();

    act(() => {
      window.dispatchEvent(new StorageEvent('storage', { key: 'some.other.key', newValue: 'irrelevant' }));
    });

    // Still logged in — an unrelated key changing must not touch auth state.
    expect(screen.getByTestId('logged-in').textContent).toBe('true');
  });
});
