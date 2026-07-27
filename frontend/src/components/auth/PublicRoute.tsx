import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

export const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isLoggedIn, isInitialised } = useAuth();
  const location = useLocation();

  if (!isInitialised) return null;

  if (isLoggedIn) {
    const from = location.state?.from;
    const destination = from
      ? `${from.pathname || '/'}${from.search || ''}${from.hash || ''}`
      : '/';

    return <Navigate to={destination} replace />;
  }

  return <>{children}</>;
};
