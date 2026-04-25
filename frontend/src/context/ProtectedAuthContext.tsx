import React, { createContext, useContext } from 'react';
import { useAuth } from './AuthContext';
import { Session } from '../types/auth';

interface ProtectedAuthContextType {
  session: Session;
  organizationId: string;
  logout: () => void;
}

const ProtectedAuthContext = createContext<ProtectedAuthContextType | undefined>(undefined);

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

export const useProtectedAuth = () => {
  const context = useContext(ProtectedAuthContext);
  if (context === undefined) {
    throw new Error('useProtectedAuth must be used within a ProtectedAuthProvider');
  }
  return context;
};
