import { useState, useEffect } from 'react';
import { apiFetch } from '../../utils/api';
import { useAuth } from '../../context/AuthContext';
import { Shield, Check, X, AlertCircle, Edit2, Save, Trash2 } from 'lucide-react';

interface Role {
  id: number;
  name: string;
  description: string;
  permissions: string[];
  client_id: number | null;
}

interface Permission {
  id: number;
  name: string;
  description: string;
}

export default function RoleManagementPage({ isTab = false }: { isTab?: boolean }) {
  const [roles, setRoles] = useState<Role[]>([]);
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [editingRole, setEditingRole] = useState<number | null>(null);
  const [editedPerms, setEditedPerms] = useState<string[]>([]);
  const [roleToDelete, setRoleToDelete] = useState<{id: number, name: string} | null>(null);

  const { user } = useAuth();
  const isPlatformAdmin = user?.role === 'SUPER_ADMIN' || (user as any)?.role_name === 'SUPER_ADMIN' || user?.is_platform_user;

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [roleRes, permRes] = await Promise.all([
        apiFetch('/api/users/roles'),
        apiFetch('/api/users/permissions')
      ]);
      const rolesData = await roleRes.json();
      const permsData: Permission[] = await permRes.json();
      
      setRoles(rolesData);
      
      // Filter permissions for non-platform users
      if (!isPlatformAdmin) {
        const platformPerms = ['access_ai_settings', 'access_health', 'access_backups', 'access_tenants'];
        setAllPermissions(permsData.filter(p => !platformPerms.includes(p.name)));
      } else {
        setAllPermissions(permsData);
      }
    } catch (err) {
      console.error('Failed to fetch roles:', err);
    } finally {
      setLoading(false);
    }
  };

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newRole, setNewRole] = useState({ name: '', description: '' });

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  const handleCreateRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRole.name.trim()) return;

    setLoading(true);
    try {
      const res = await apiFetch('/api/users/roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newRole)
      });
      if (res.ok) {
        showMessage('success', `Role "${newRole.name}" created!`);
        setIsCreateModalOpen(false);
        setNewRole({ name: '', description: '' });
        fetchData();
      } else {
        const data = await res.json();
        showMessage('error', data.detail || 'Failed to create role');
      }
    } catch (err) {
      showMessage('error', 'Network error');
    } finally {
      setLoading(false);
    }
  };

  const handleEditRole = (role: Role) => {
    setEditingRole(role.id);
    setEditedPerms(role.permissions);
  };

  const togglePermission = (permName: string) => {
    setEditedPerms(prev => 
      prev.includes(permName) ? prev.filter(p => p !== permName) : [...prev, permName]
    );
  };

  const handleDeleteRole = async () => {
    if (!roleToDelete) return;
    setLoading(true);
    try {
      const res = await apiFetch(`/api/users/roles/${roleToDelete.id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        showMessage('success', `Role "${roleToDelete.name}" deleted successfully.`);
        setRoleToDelete(null);
        fetchData();
      } else {
        const data = await res.json();
        showMessage('error', data.detail || 'Deletion failed');
      }
    } catch (err) {
      showMessage('error', 'Network error');
    } finally {
      setLoading(false);
    }
  };

  const handleSavePermissions = async (roleId: number) => {
    try {
      const res = await apiFetch(`/api/users/roles/${roleId}/permissions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editedPerms)
      });
      if (res.ok) {
        showMessage('success', 'Permissions updated successfully');
        setEditingRole(null);
        fetchData();
      } else {
        const data = await res.json();
        showMessage('error', data.detail || 'Update failed');
      }
    } catch (err) {
      showMessage('error', 'Network error');
    }
  };

  if (loading) return <div className="flex justify-center p-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div></div>;

  return (
    <div className="space-y-6">
      {!isTab && (
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Role Management</h1>
            <p className="text-slate-500">Define roles and assign granular permissions.</p>
          </div>
          <button 
            onClick={() => setIsCreateModalOpen(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-bold shadow-sm transition-all flex items-center gap-2"
          >
            <Shield size={18} />
            <span>Add New Role</span>
          </button>
        </div>
      )}

      {isTab && (
          <div className="flex justify-end mb-4">
              <button 
                onClick={() => setIsCreateModalOpen(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-bold shadow-sm transition-all flex items-center gap-2 text-sm"
              >
                <Shield size={16} />
                <span>Add New Role</span>
              </button>
          </div>
      )}

      {message && (
        <div className={`p-4 rounded-xl flex items-center gap-3 ${message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {message.type === 'success' ? <Check size={20} /> : <AlertCircle size={20} />}
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6">
        {roles.map(role => (
          <div key={role.id} className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden hover:shadow-md transition-all">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center">
                  <Shield size={20} />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 uppercase tracking-tight">{role.name}</h3>
                  <p className="text-xs text-slate-500">{role.description}</p>
                </div>
              </div>
              
              {editingRole === role.id ? (
                <div className="flex items-center gap-2">
                   <button 
                    onClick={() => handleSavePermissions(role.id)}
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 hover:bg-blue-700 active:scale-95 transition-all"
                  >
                    <Save size={16} /> Save Changes
                  </button>
                  <button 
                    onClick={() => setEditingRole(null)}
                    className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    <X size={18} />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1">
                  <button 
                    onClick={() => handleEditRole(role)}
                    className="text-slate-500 hover:text-blue-600 p-2 hover:bg-blue-50 rounded-lg transition-colors"
                    title="Edit Permissions"
                    disabled={!isPlatformAdmin && role.client_id === null}
                  >
                    <Edit2 size={18} />
                  </button>
                  {role.client_id !== null && (
                    <button 
                      onClick={() => setRoleToDelete({ id: role.id, name: role.name })}
                      className="text-slate-400 hover:text-red-600 p-2 hover:bg-red-50 rounded-lg transition-colors"
                      title="Delete Role"
                    >
                      <Trash2 size={18} />
                    </button>
                  )}
                </div>
              )}
            </div>
            
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                  <div className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    Permissions Matrix
                  </div>
                  {role.client_id === null && (
                      <span className="text-[10px] bg-amber-50 text-amber-600 font-black px-2 py-0.5 rounded-full uppercase border border-amber-100">Global Platform Role</span>
                  )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {allPermissions.map(perm => {
                  const isActive = editingRole === role.id 
                    ? editedPerms.includes(perm.name) 
                    : role.permissions.includes(perm.name);
                    
                  return (
                    <button
                      key={perm.id}
                      disabled={editingRole !== role.id}
                      onClick={() => togglePermission(perm.name)}
                      className={`flex items-start gap-3 p-3 rounded-xl border text-left transition-all ${
                        isActive 
                          ? 'border-blue-200 bg-blue-50/50 text-blue-700 shadow-sm shadow-blue-50/50' 
                          : 'border-slate-100 bg-white text-slate-400 opacity-60'
                      } ${editingRole === role.id ? 'hover:border-blue-300 hover:shadow-md' : 'cursor-default'}`}
                    >
                      <div className={`mt-0.5 rounded-md p-0.5 ${isActive ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-300'}`}>
                        {isActive ? <Check size={12} /> : <X size={12} />}
                      </div>
                      <div>
                        <div className="text-[11px] font-black uppercase tracking-wider">{perm.name.replace('access_', '').replace('_', ' ')}</div>
                        <div className="text-[10px] leading-tight mt-0.5 text-slate-500 truncate-2-lines line-clamp-2">{perm.description}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Create Role Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="bg-white w-full max-w-md rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 border border-slate-100">
            <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Create Custom Role</h2>
                <p className="text-sm text-slate-500 mt-1">Define a new identity for your specific company context.</p>
              </div>
              <button onClick={() => setIsCreateModalOpen(false)} className="text-slate-400 hover:text-slate-600 transition-colors">
                <X size={24} />
              </button>
            </div>
            
            <form onSubmit={handleCreateRole} className="p-8 space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-700 flex items-center gap-2">
                  <Shield size={16} className="text-blue-600" />
                  Role Name
                </label>
                <input 
                  autoFocus
                  required
                  type="text" 
                  placeholder="e.g. Finance Admin"
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none bg-slate-50/30 font-bold uppercase tracking-tight"
                  value={newRole.name}
                  onChange={(e) => setNewRole({...newRole, name: e.target.value.toUpperCase()})}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-bold text-slate-700">Description</label>
                <textarea 
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none bg-slate-50/30 text-sm"
                  placeholder="What can this role do?"
                  rows={3}
                  value={newRole.description}
                  onChange={(e) => setNewRole({...newRole, description: e.target.value})}
                />
              </div>

              <div className="pt-4 flex gap-3">
                <button 
                  type="button" 
                  onClick={() => setIsCreateModalOpen(false)}
                  className="flex-1 py-3 border border-slate-200 text-slate-600 font-bold rounded-xl hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={loading}
                  className="flex-2 bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-xl shadow-lg shadow-blue-100 transition-all active:scale-95 disabled:opacity-50"
                >
                  {loading ? "Creating..." : "Launch Role"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Delete Confirmation Modal */}
      {roleToDelete && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="bg-white w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200 border border-slate-100">
            <div className="p-8 text-center">
              <div className="w-16 h-16 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4 font-bold border-4 border-white shadow-sm">
                <Trash2 size={28} />
              </div>
              <h2 className="text-xl font-bold text-slate-900">Delete Role</h2>
              <p className="text-sm text-slate-500 mt-2 mb-6 leading-relaxed">
                Are you sure you want to delete the <strong>{roleToDelete.name}</strong> role? This action cannot be undone if users are currently assigned to it.
              </p>
              <div className="flex gap-3">
                <button 
                  type="button" 
                  onClick={() => setRoleToDelete(null)}
                  className="flex-1 py-3 border border-slate-200 text-slate-600 font-bold rounded-xl hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="button"
                  onClick={handleDeleteRole}
                  disabled={loading}
                  className="flex-1 bg-red-600 text-white font-bold py-3 rounded-xl hover:bg-red-700 transition-all shadow-lg shadow-red-200 active:scale-95 disabled:opacity-50"
                >
                  {loading ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
