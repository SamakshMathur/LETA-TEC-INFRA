import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { ProtectedAuthProvider } from '../../context/ProtectedAuthContext';
import { clearAuthSession } from '../../lib/auth-storage';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isLoggedIn, session, organizationId, isInitialised } = useAuth();
  const location = useLocation();

  if (!isInitialised) return null;

  if (!isLoggedIn) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!organizationId) {
    // Corrupted state: logged in but no org
    clearAuthSession();
    return <Navigate to="/login?reason=session_expired" replace />;
  }

  return <ProtectedAuthProvider>{children}</ProtectedAuthProvider>;
};
