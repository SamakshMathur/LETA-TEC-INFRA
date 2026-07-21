import { Session } from '../types/auth';

export type Role =
  | 'super_admin'
  | 'admin'
  | 'knowledge_manager'
  | 'reviewer'
  | 'uploader'
  | 'support'
  | 'viewer'
  | 'user';

const ROLE_RANK: Record<Role, number> = {
  super_admin: 8,
  admin: 7,
  knowledge_manager: 6,
  reviewer: 5,
  uploader: 4,
  support: 3,
  viewer: 2,
  user: 1,
};

export const getActiveRole = (session: Session | null): Role => {
  if (!session) return 'user';
  const orgId = session.organizationId;
  if (orgId && session.memberships) {
    const membership = session.memberships.find(m => m.organizationId === orgId);
    if (membership?.role) return membership.role as Role;
  }
  return (session.user?.role || 'user') as Role;
};

export const hasRole = (session: Session | null, requiredRole: Role): boolean => {
  const activeRole = getActiveRole(session);
  return (ROLE_RANK[activeRole] || 0) >= (ROLE_RANK[requiredRole] || 0);
};

export const hasAnyRole = (session: Session | null, requiredRoles: Role[]): boolean => {
  const activeRole = getActiveRole(session);
  return requiredRoles.some(r => activeRole === r || (ROLE_RANK[activeRole] || 0) >= (ROLE_RANK[r] || 0));
};

export const isAdmin = (session: Session | null): boolean => hasRole(session, 'admin');
export const isSuperAdmin = (session: Session | null): boolean => hasRole(session, 'super_admin');
export const canUpload = (session: Session | null): boolean => hasRole(session, 'uploader');
export const canInviteUsers = (session: Session | null): boolean => hasRole(session, 'admin');
export const canManageKnowledgeBase = (session: Session | null): boolean => hasRole(session, 'knowledge_manager');
export const canManageSettings = (session: Session | null): boolean => hasRole(session, 'admin');
export const canAccessBilling = (session: Session | null): boolean => hasRole(session, 'admin');
