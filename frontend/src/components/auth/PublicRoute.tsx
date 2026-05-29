import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isLoggedIn, isInitialised } = useAuth();

  if (!isInitialised) return null;

  if (isLoggedIn && location.pathname === "/login") {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};
