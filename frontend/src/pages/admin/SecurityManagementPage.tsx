import { useState } from 'react';
import { Users, Shield, Layout } from 'lucide-react';
import UserManagementPage from './UserManagementPage';
import RoleManagementPage from './RoleManagementPage';
import TenantFeaturesPage from './TenantFeaturesPage';
import { useAuth } from '../../context/AuthContext';

export default function SecurityManagementPage() {
  const [activeTab, setActiveTab] = useState<'users' | 'roles' | 'features'>('users');
  const { user } = useAuth();
  
  // Robust platform user check
  const isPlatform = user?.is_platform_user || user?.role === 'SUPER_ADMIN' || (user as any)?.role_name === 'SUPER_ADMIN';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-slate-200 pb-2">
        <div className="flex items-center gap-6">
          
          <button 
            onClick={() => setActiveTab('users')}
            className={`flex items-center gap-2 pb-2 px-1 transition-all relative ${
              activeTab === 'users' 
                ? 'text-blue-600 font-bold' 
                : 'text-slate-400 hover:text-slate-600 font-medium'
            }`}
          >
            <Users size={20} />
            <span className="text-lg">Users</span>
            {activeTab === 'users' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-full" />}
          </button>

          <button 
            onClick={() => setActiveTab('roles')}
            className={`flex items-center gap-2 pb-2 px-1 transition-all relative ${
              activeTab === 'roles' 
                ? 'text-blue-600 font-bold' 
                : 'text-slate-400 hover:text-slate-600 font-medium'
            }`}
          >
            <Shield size={20} />
            <span className="text-lg">Roles</span>
            {activeTab === 'roles' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-full" />}
          </button>

          {isPlatform && (
            <button 
              onClick={() => setActiveTab('features')}
              className={`flex items-center gap-2 pb-2 px-1 transition-all relative ${
                activeTab === 'features' 
                  ? 'text-blue-600 font-bold' 
                  : 'text-slate-400 hover:text-slate-600 font-medium'
              }`}
            >
              <Layout size={20} />
              <span className="text-lg"> Tenant Capabilities</span>
              {activeTab === 'features' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-full" />}
            </button>
          )}
        </div>
      </div>

      <div className="pt-2">
        {activeTab === 'users' ? <UserManagementPage isTab={true} /> : 
         activeTab === 'roles' ? <RoleManagementPage isTab={true} /> : 
         <TenantFeaturesPage />
        }
      </div>
    </div>
  );
}
