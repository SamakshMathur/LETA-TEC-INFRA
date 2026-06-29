import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Session, User } from '../types/auth';
import { getStoredAuthSession, storeAuthSession, clearAuthSession } from '../lib/auth-storage';

interface AuthContextType {
  session: Session | null;
  isLoggedIn: boolean;
  user: User | null;
  organizationId: string | null;
  login: (session: Session, persist: boolean) => void;
  logout: () => void;
  isInitialised: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

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

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
