import { AXIOS_INSTANCE } from '../utils/api';
import { Session } from '../types/auth';

export const registerApi = async (userData: {
  full_name: string;
  phone: string;
  profession: string;
  gender: string;
  email?: string;
}): Promise<void> => {
  await AXIOS_INSTANCE.post('/api/auth/register', userData);
};

export const sendOtpApi = async (contact: string, method: 'email' | 'phone'): Promise<void> => {
  await AXIOS_INSTANCE.post('/api/auth/send-otp', { contact, method });
};

export const verifyOtpApi = async (contact: string, otp: string): Promise<Session> => {
  const res = await AXIOS_INSTANCE.post('/api/auth/verify-otp', { contact, otp });
  const { tokens, user, memberships } = res.data;
  const organizationId = memberships[0]?.organizationId || null;
  return { tokens, user, memberships, organizationId };
};

export const loginAndResolveSession = async (credentials: {
  email: string;
  password: string;
}): Promise<Session> => {
  const res = await AXIOS_INSTANCE.post('/api/auth/login', credentials);
  const { tokens, user, memberships } = res.data;
  const organizationId = memberships[0]?.organizationId || null;
  return { tokens, user, memberships, organizationId };
};

export const logoutApi = async (): Promise<void> => {
  await AXIOS_INSTANCE.post('/api/auth/logout');
};
