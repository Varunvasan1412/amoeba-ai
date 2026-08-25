import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Shield } from 'lucide-react';

interface RoleGuardProps {
  children: React.ReactNode;
  permission?: string | string[];
  role?: string;
  requireAll?: boolean;
  fallback?: React.ReactNode;
}

/**
 * RoleGuard component to wrap UI elements that require specific permissions.
 */
export const RoleGuard: React.FC<RoleGuardProps> = ({ 
  children, 
  permission, 
  role, 
  requireAll = false,
  fallback = null 
}) => {
  const { user } = useAuth();

  if (!user) return <>{fallback}</>;

  // SUPER_ADMIN bypass
  if (user.role === 'SUPER_ADMIN') {
    return <>{children}</>;
  }

  // Check specific role
  if (role && user.role !== role) {
    return <>{fallback}</>;
  }

  // Check specific permissions
  if (permission) {
    const required = Array.isArray(permission) ? permission : [permission];
    const userPerms = user.permissions || [];
    
    const hasPermission = requireAll
      ? required.every(p => userPerms.includes(p))
      : required.some(p => userPerms.includes(p));

    if (!hasPermission) {
      if (fallback) return <>{fallback}</>;
      return (
        <div className="flex flex-col items-center justify-center p-12 bg-white rounded-2xl border border-dashed border-slate-200 text-center animate-in fade-in zoom-in duration-300">
          <div className="w-12 h-12 bg-red-50 text-red-500 rounded-xl flex items-center justify-center mb-4">
            <Shield size={24} />
          </div>
          <h3 className="text-lg font-bold text-slate-800">Access Denied</h3>
          <p className="text-sm text-slate-500 max-w-xs mt-1">
            You do not have the required permissions ({Array.isArray(permission) ? permission.join(', ') : permission}) to view this module.
          </p>
        </div>
      );
    }
  }

  return <>{children}</>;
};

export default RoleGuard;
