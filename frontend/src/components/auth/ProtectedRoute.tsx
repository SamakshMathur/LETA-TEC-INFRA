import React, { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { ProtectedAuthProvider } from '../../context/ProtectedAuthContext';
import { hasRole } from '../../lib/permissions';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isLoggedIn, organizationId, isInitialised, logout, session } = useAuth();
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

  if (location.pathname.startsWith('/admin') && !hasRole(session, 'knowledge_manager')) {
    return <Navigate to="/dashboard" replace />;
  }

  return <ProtectedAuthProvider>{children}</ProtectedAuthProvider>;
};
