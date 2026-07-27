import { useContext } from 'react';
import { ProtectedAuthContext } from '../context/ProtectedAuthContext';

export const useProtectedAuth = () => {
  const context = useContext(ProtectedAuthContext);
  if (context === undefined) {
    throw new Error('useProtectedAuth must be used within a ProtectedAuthProvider');
  }
  return context;
};
