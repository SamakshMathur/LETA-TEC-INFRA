import { InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { AXIOS_INSTANCE } from './api';
import { getStoredAuthSession, updateStoredTokens, clearAuthSession } from '../lib/auth-storage';
import { Tokens } from '../types/auth';

const AUTH_ENDPOINTS = [
  '/api/auth/login',
  '/api/auth/send-otp',
  '/api/auth/verify-otp',
  '/api/auth/register',
  '/api/auth/refresh',
  '/api/auth/reset-password',
  '/invites',
];

let refreshPromise: Promise<Tokens> | null = null;

// ─── Plan-expiry detection ────────────────────────────────────────────────────
// When the backend returns 401 with this specific detail, it means the user's
// plan session has expired — not the JWT.  Retrying with a fresh JWT won't help;
// we redirect to a plan-renewal page instead of the generic login page.
const PLAN_EXPIRED_DETAIL = 'Session expired. Please log in again.';

function isPlanExpiry(error: any): boolean {
  const detail = error?.response?.data?.detail;
  return typeof detail === 'string' && detail === PLAN_EXPIRED_DETAIL;
}

// Use an external axios for the refresh call to avoid interception loops
import axios from 'axios';

const doTokenRefresh = async (): Promise<Tokens> => {
  const session = getStoredAuthSession();
  if (!session || !session.tokens.refreshToken) {
    throw new Error('No refresh token available');
  }

  try {
    const response = await axios.post(`${AXIOS_INSTANCE.defaults.baseURL}/api/auth/refresh`, {
      refresh_token: session.tokens.refreshToken,
    });
    const newTokens = response.data.tokens as Tokens;
    updateStoredTokens(newTokens);
    return newTokens;
  } catch (error) {
    clearAuthSession();
    window.location.href = '/login?reason=session_expired';
    throw error;
  }
};

export const setupInterceptors = () => {
  AXIOS_INSTANCE.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
      // 1. Skip auth endpoints
      if (AUTH_ENDPOINTS.some(url => config.url?.includes(url))) {
        return config;
      }

      // 2. If Authorization already set by getAuthHeaders(), validate it hasn't
      //    expired before forwarding — expired token → proactive refresh.
      if (config.headers.Authorization) {
        const session = getStoredAuthSession();
        if (session) {
          const expiresAt = new Date(session.tokens.expiresAt).getTime();
          if (expiresAt < Date.now() + 10000) {
            // Token about to expire — refresh before sending
            if (!refreshPromise) {
              refreshPromise = doTokenRefresh().finally(() => { refreshPromise = null; });
            }
            try {
              const newTokens = await refreshPromise;
              config.headers.Authorization = `Bearer ${newTokens.accessToken}`;
            } catch {
              // Refresh failed → interceptor already redirected to login;
              // pass the stale token and let the 401 handler clean up.
            }
          }
        }
        return config;
      }

      const session = getStoredAuthSession();
      if (!session) {
        return config;
      }

      const { tokens } = session;
      const now = Date.now();
      const expiresAt = new Date(tokens.expiresAt).getTime();

      // 3. Trigger refresh if expired or within 10s of expiry
      if (expiresAt < now + 10000) {
        if (!refreshPromise) {
          refreshPromise = doTokenRefresh().finally(() => {
            refreshPromise = null;
          });
        }
        const newTokens = await refreshPromise;
        config.headers.Authorization = `Bearer ${newTokens.accessToken}`;
      } else {
        config.headers.Authorization = `Bearer ${tokens.accessToken}`;
      }

      return config;
    },
    (error) => Promise.reject(error)
  );

  AXIOS_INSTANCE.interceptors.response.use(
    (response: AxiosResponse) => response,
    async (error) => {
      const originalRequest = error.config;

      // 4. Handle 401
      if (error.response?.status === 401 && !originalRequest._retry) {
        if (AUTH_ENDPOINTS.some(url => originalRequest.url?.includes(url))) {
          return Promise.reject(error);
        }

        // Plan-expiry 401: the user's purchased plan has expired.
        // A fresh JWT won't fix this — don't bother refreshing, just reject
        // with an augmented error so callers can distinguish this from a
        // generic auth failure.  We do NOT redirect or clear the session here
        // because plan-expiry only blocks session-tracked endpoints; unauthenticated
        // endpoints like /ask still work and the user should stay on the page.
        if (isPlanExpiry(error)) {
          const augmented = error as any;
          augmented.isPlanExpired = true;
          return Promise.reject(augmented);
        }

        originalRequest._retry = true;

        if (!refreshPromise) {
          refreshPromise = doTokenRefresh().finally(() => {
            refreshPromise = null;
          });
        }

        try {
          const newTokens = await refreshPromise;
          originalRequest.headers.Authorization = `Bearer ${newTokens.accessToken}`;
          return AXIOS_INSTANCE(originalRequest);
        } catch (refreshError) {
          return Promise.reject(refreshError);
        }
      }

      return Promise.reject(error);
    }
  );
};
