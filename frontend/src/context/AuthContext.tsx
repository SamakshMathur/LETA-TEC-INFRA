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
    accessToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZXZfODYxOTI1Njg1MSIsInR5cGUiOiJhY2Nlc3MiLCJleHAiOjE4MTI2MzUzMjd9.3Stvcl2qJHtii31xT9aAafoZ5Pu__Jq7Fjg_zKc51AM',
    refreshToken: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZXZfODYxOTI1Njg1MSIsInR5cGUiOiJyZWZyZXNoIiwiZXhwIjoxODEyNjM1MzI3fQ.-sXmErI9_BlM8LMIn9du13nkV2TxyVS4NNFReMCkzdo',
    expiresAt: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),
    refreshTokenExpiresAt: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),
    tokenType: 'bearer',
    expiresIn: 31536000,
    refreshTokenExpiresIn: 31536000,
  },
  user: { id: 'dev_8619256851', email: 'dev@letatec.com', firstName: 'Samaksh', lastName: 'Mathur', role: 'user' },
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
