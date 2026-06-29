import React, { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { ProtectedAuthProvider } from '../../context/ProtectedAuthContext';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isLoggedIn, organizationId, isInitialised, logout } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (isInitialised && isLoggedIn && !organizationId) {
      logout();
    }
  }, [isInitialised, isLoggedIn, organizationId, logout]);

  if (!isInitialised) return null;

  if (!isLoggedIn) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!organizationId) {
    return <Navigate to="/login?reason=session_expired" replace />;
  }

  return <ProtectedAuthProvider>{children}</ProtectedAuthProvider>;
};
