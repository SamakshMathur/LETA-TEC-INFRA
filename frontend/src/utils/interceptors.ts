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

// Use an external axios for the refresh call to avoid interception loops
import axios from 'axios';

export const setupInterceptors = () => {
  AXIOS_INSTANCE.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
      // 1. Skip auth endpoints
      if (AUTH_ENDPOINTS.some(url => config.url?.includes(url))) {
        return config;
      }

      // 2. Check for existing header
      if (config.headers.Authorization) {
        return config;
      }

      const session = getStoredAuthSession();
      if (!session) {
        return config;
      }

      const { tokens } = session;
      const now = Date.now();
      const expiresAt = new Date(tokens.expiresAt).getTime();

      // 3. Trigger refresh if expired
      if (expiresAt < now + 10000) { // 10s buffer
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
