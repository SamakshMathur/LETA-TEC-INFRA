import { AXIOS_INSTANCE } from '../utils/api';
import { Session, User, Membership } from '../types/auth';

export const loginAndResolveSession = async (credentials: any): Promise<Session> => {
  // 1. Perform login
  const loginResponse = await AXIOS_INSTANCE.post('/api/auth/login', credentials);
  const { tokens, user, memberships } = loginResponse.data;

  let organizationId = null;

  // 2. Resolve organizationId
  if (user.role === 'SUPER_ADMIN') {
    const orgsResponse = await AXIOS_INSTANCE.get('/api/organizations');
    const organizations = orgsResponse.data;
    organizationId = organizations[0]?.id || null;
  } else {
    organizationId = memberships[0]?.organizationId || null;
  }

  return {
    tokens,
    user,
    memberships,
    organizationId,
  };
};

export const registerApi = async (userData: any): Promise<void> => {
  await AXIOS_INSTANCE.post('/api/auth/register', userData);
};

export const logoutApi = async (): Promise<void> => {
  await AXIOS_INSTANCE.post('/api/auth/logout');
};
