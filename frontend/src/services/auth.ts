import { AXIOS_INSTANCE } from '../utils/api';
import { Session } from '../types/auth';

const ACCESS_TOKEN_KEY = 'leta_access_token';
const REFRESH_TOKEN_KEY = 'leta_refresh_token';

export const saveSession = (session: Session) => {
  if (session?.tokens?.access_token) {
    localStorage.setItem(
      ACCESS_TOKEN_KEY,
      session.tokens.access_token
    );
  }

  if (session?.tokens?.refresh_token) {
    localStorage.setItem(
      REFRESH_TOKEN_KEY,
      session.tokens.refresh_token
    );
  }

  localStorage.setItem(
    'leta_session',
    JSON.stringify(session)
  );
};

export const clearSession = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem('leta_session');
};

export const getAccessToken = (): string | null => {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

export const getRefreshToken = (): string | null => {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

export const getStoredSession = (): Session | null => {
  try {
    const raw = localStorage.getItem('leta_session');

    if (!raw) return null;

    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const isAuthenticated = (): boolean => {
  return !!getAccessToken();
};

export const registerApi = async (userData: {
  full_name: string;
  phone: string;
  profession: string;
  gender: string;
  email?: string;
}): Promise<void> => {
  await AXIOS_INSTANCE.post(
    '/api/auth/register',
    userData
  );
};

export const sendOtpApi = async (
  contact: string,
  method: 'email' | 'phone'
): Promise<void> => {
  await AXIOS_INSTANCE.post(
    '/api/auth/send-otp',
    {
      contact,
      method
    }
  );
};

export const verifyOtpApi = async (
  contact: string,
  otp: string
): Promise<Session> => {
  const res = await AXIOS_INSTANCE.post(
    '/api/auth/verify-otp',
    {
      contact,
      otp
    }
  );

  const {
    tokens,
    user,
    memberships
  } = res.data;

  const organizationId =
    memberships?.[0]?.organizationId || null;

  const session: Session = {
    tokens,
    user,
    memberships,
    organizationId
  };

  saveSession(session);

  return session;
};

export const loginAndResolveSession = async (
  credentials: {
    email: string;
    password: string;
  }
): Promise<Session> => {
  const res = await AXIOS_INSTANCE.post(
    '/api/auth/login',
    credentials
  );

  const {
    tokens,
    user,
    memberships
  } = res.data;

  const organizationId =
    memberships?.[0]?.organizationId || null;

  const session: Session = {
    tokens,
    user,
    memberships,
    organizationId
  };

  saveSession(session);

  return session;
};

export const logoutApi = async (): Promise<void> => {
  try {
    await AXIOS_INSTANCE.post('/api/auth/logout');
  } catch { }

  clearSession();
};