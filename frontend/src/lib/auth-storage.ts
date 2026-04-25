import { Session, Tokens } from '../types/auth';

const STORAGE_KEY = 'pro.auth.session';

export const storeAuthSession = (session: Session, persist: boolean = false): void => {
  // Always use localStorage to fix the multi-tab logout bug
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  
  // We can track the 'persist' flag if needed for specific logic later, 
  // but for now, we ensure cross-tab stability.
  sessionStorage.removeItem(STORAGE_KEY); 
};

export const getStoredAuthSession = (): Session | null => {
  const stored = localStorage.getItem(STORAGE_KEY) || sessionStorage.getItem(STORAGE_KEY);
  if (!stored) return null;
  
  try {
    return JSON.parse(stored) as Session;
  } catch (e) {
    return null;
  }
};

export const clearAuthSession = (): void => {
  localStorage.removeItem(STORAGE_KEY);
  sessionStorage.removeItem(STORAGE_KEY);
};

export const updateStoredTokens = (tokens: Tokens): void => {
  const session = getStoredAuthSession();
  if (session) {
    const isPersistent = !!localStorage.getItem(STORAGE_KEY);
    storeAuthSession({ ...session, tokens }, isPersistent);
  }
};

export const hasAuthSession = (): boolean => {
  return !!getStoredAuthSession();
};
