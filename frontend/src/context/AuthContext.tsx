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

const BYPASS_SESSION: Session = {
  tokens: {
    accessToken: 'dev-bypass-token',
    refreshToken: 'dev-bypass-refresh',
    expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    refreshTokenExpiresAt: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    tokenType: 'bearer',
    expiresIn: 604800,
    refreshTokenExpiresIn: 2592000,
  },
  user: { id: 'dev-user', email: 'dev@letatec.com', firstName: 'Dev', lastName: 'User', role: 'user' },
  memberships: [{ organizationId: 'org_default', role: 'user' }],
  organizationId: 'org_default',
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<Session | null>(BYPASS_SESSION);
  const [isInitialised, setIsInitialised] = useState(false);

  useEffect(() => {
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
