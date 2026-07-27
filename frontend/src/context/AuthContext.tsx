import React, { createContext, useState, useEffect, useCallback } from 'react';
import { Session, User } from '../types/auth';
import { getStoredAuthSession, storeAuthSession, clearAuthSession } from '../lib/auth-storage';
import { DEMO_MODE } from '../config/demo';

// Minimal session used when DEMO_MODE=true. No session_end_ms → SessionClock hidden.
const DEMO_SESSION: Session = {
  tokens: {
    accessToken: 'demo-preview-token',
    refreshToken: 'demo-preview-refresh',
    expiresAt: '2099-12-31T00:00:00Z',
    refreshTokenExpiresAt: '2099-12-31T00:00:00Z',
    tokenType: 'bearer',
    expiresIn: 99999999,
    refreshTokenExpiresIn: 99999999,
  },
  user: { id: 'demo-user', full_name: 'Demo', email: 'demo@letatec.com', role: 'user', plan: 'pro' },
  memberships: [{ organizationId: 'demo-org', role: 'member' }],
  organizationId: 'demo-org',
};

interface AuthContextType {
  session: Session | null;
  isLoggedIn: boolean;
  user: User | null;
  organizationId: string | null;
  login: (session: Session, persist: boolean) => void;
  logout: () => void;
  isInitialised: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

const parseExpiry = (value?: string | number): number => {
  if (!value) return 0;
  return typeof value === 'number' ? value : new Date(value).getTime();
};

const getValidStoredSession = (): Session | null => {
  const stored = getStoredAuthSession();

  if (!stored?.tokens?.accessToken || !stored?.tokens?.refreshToken) {
    clearAuthSession();
    return null;
  }

  const refreshExpiresAt = parseExpiry(stored.tokens.refreshTokenExpiresAt);

  if (!Number.isFinite(refreshExpiresAt) || refreshExpiresAt <= Date.now()) {
    clearAuthSession();
    return null;
  }

  return stored;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [isInitialised, setIsInitialised] = useState(false);

  useEffect(() => {
    if (DEMO_MODE) {
      // Use real session if one exists (real login takes precedence over demo).
      // Only fall back to demo session when no real user is logged in.
      const existing = getValidStoredSession();
      const isRealSession = existing && existing.tokens?.accessToken !== 'demo-preview-token';
      if (!isRealSession) {
        localStorage.setItem('pro.auth.session', JSON.stringify(DEMO_SESSION));
        setSession(DEMO_SESSION);
      } else {
        setSession(existing);
      }
      setIsInitialised(true);
      return;
    }
    // Restore session from localStorage on page load (set by the login flow)
    setSession(getValidStoredSession());
    setIsInitialised(true);
  }, []);

  const login = useCallback((newSession: Session, persist: boolean) => {
    storeAuthSession(newSession, persist);
    setSession(newSession);
  }, []);

  const logout = useCallback(() => {
    clearAuthSession();
    setSession(null);
  }, []);

  const value = {
    session,
    isLoggedIn: !!session,
    user: session?.user || null,
    organizationId: session?.organizationId || null,
    login,
    logout,
    isInitialised
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

