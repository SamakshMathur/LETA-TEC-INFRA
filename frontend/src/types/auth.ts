export interface User {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
  role: string;
  phone?: string;
  gender?: string;
  profession?: string;
  [key: string]: any;
}

export interface Tokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: string; // ISO string or timestamp
  refreshTokenExpiresAt: string;
  tokenType: string;
  expiresIn: number;
  refreshTokenExpiresIn: number;
}

export interface Membership {
  organizationId: string;
  role: string;
}

export interface Session {
  tokens: Tokens;
  user: User;
  memberships: Membership[];
  organizationId?: string | null;
}
