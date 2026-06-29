import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isLoggedIn, isInitialised } = useAuth();
  const location = useLocation();

  if (!isInitialised) return null;

  if (isLoggedIn && location.pathname === "/login") {
    const from = location.state?.from;
    const destination = from
      ? `${from.pathname || '/dashboard'}${from.search || ''}${from.hash || ''}`
      : '/dashboard';

    return <Navigate to={destination} replace />;
  }

  return <>{children}</>;
};
