import type { UserRole } from '../api/auth';

export const roleLabels: Record<UserRole, string> = {
  user: '普通用户', frontdesk: '前台人员', admin: '场地管理员', maintenance: '维修人员',
};
export const roleOptions = (Object.entries(roleLabels) as [UserRole, string][]).map(([value, label]) => ({ value, label }));
export function homeForRole(role?: UserRole) {
  return role === 'admin' ? '/admin/overview' : role === 'frontdesk' ? '/frontdesk' : role === 'maintenance' ? '/maintenance' : '/';
}
