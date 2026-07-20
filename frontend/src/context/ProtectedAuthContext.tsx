import React, { createContext } from 'react';
import { useAuth } from '../hooks/useAuth';
import { Session } from '../types/auth';

interface ProtectedAuthContextType {
  session: Session;
  organizationId: string;
  logout: () => void;
}

export const ProtectedAuthContext = createContext<ProtectedAuthContextType | undefined>(undefined);

export const ProtectedAuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { session, organizationId, logout } = useAuth();

  if (!session || !organizationId) {
    // This provider should only be used where the session is guaranteed
    return null;
  }

  const value = {
    session,
    organizationId,
    logout
  };

  return (
    <ProtectedAuthContext.Provider value={value}>
      {children}
    </ProtectedAuthContext.Provider>
  );
};

