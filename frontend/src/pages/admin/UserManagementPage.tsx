import { useState, useEffect } from 'react';
import { apiFetch } from '../../utils/api';
import { Shield, Check, AlertCircle, Edit2, User as UserIcon, Plus, X, Lock, Trash2, Power } from 'lucide-react';

interface User {
  id: number;
  username: string;
  role_id: number | null;
  role_name: string;
  is_active: boolean;
  is_admin: boolean;
  client_id: number | null;
}

interface Role {
  id: number;
  name: string;
  description: string;
}

interface Client {
  id: number;
  client_name: string;
  company_code: string;
}

export default function UserManagementPage({ isTab = false }: { isTab?: boolean }) {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [editingUser, setEditingUser] = useState<number | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newUser, setNewUser] = useState({ username: '', email: '', password: '', role_id: '', client_id: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);
  const [userToDelete, setUserToDelete] = useState<{id: number, username: string} | null>(null);
  const [editData, setEditData] = useState<{
    username?: string;
    role_id?: number | null;
    client_id?: number | null;
    is_active?: boolean;
  }>({});

  useEffect(() => {
    fetchData();
  }, []);

  const handleEditUser = (user: User) => {
    setEditingUser(user.id);
    setEditData({
      username: user.username,
      role_id: user.role_id,
      client_id: user.client_id,
      is_active: user.is_active
    });
  };

  const handleUpdateUser = async (userId: number) => {
    setIsSubmitting(true);
    try {
      const res = await apiFetch(`/api/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...editData,
          client_id: editData.client_id === null ? -1 : editData.client_id // Handle 'Platform Core' reassignment
        })
      });
      if (res.ok) {
        setMessage({ type: 'success', text: 'User updated successfully' });
        setEditingUser(null);
        fetchData();
        setTimeout(() => setMessage(null), 3000);
      } else {
        const data = await res.json();
        setMessage({ type: 'error', text: data.detail || 'Update failed' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Network error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [userRes, roleRes] = await Promise.all([
        apiFetch('/api/users/'),
        apiFetch('/api/users/roles')
      ]);
      setUsers(await userRes.json());
      setRoles(await roleRes.json());
      
      // Try fetching clients. If 403, user is not a platform admin, which is fine.
      try {
        const clientRes = await apiFetch('/api/clients');
        if (clientRes.ok) {
          const clientData = await clientRes.json();
          setClients(clientData.clients || []);
        }
      } catch (e) {
        // Silently ignore if lacking client fetching perms
      }
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStatus = async (user: User) => {
    setIsSubmitting(true);
    try {
      const res = await apiFetch(`/api/users/${user.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !user.is_active })
      });
      if (res.ok) {
        fetchData();
        setMessage({ type: 'success', text: `User ${user.username} ${!user.is_active ? 'enabled' : 'disabled'}` });
        setTimeout(() => setMessage(null), 3000);
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to update status' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteUser = async () => {
    if (!userToDelete) return;
    setIsSubmitting(true);
    try {
      const res = await apiFetch(`/api/users/${userToDelete.id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setMessage({ type: 'success', text: 'User deleted successfully' });
        setUserToDelete(null);
        fetchData();
        setTimeout(() => setMessage(null), 3000);
      } else {
        const data = await res.json();
        setMessage({ type: 'error', text: data.detail || 'Deletion failed' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Network error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const res = await apiFetch('/api/users/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: newUser.username,
          email: newUser.email,
          password: newUser.password,
          role_id: newUser.role_id ? parseInt(newUser.role_id) : null,
          client_id: newUser.client_id ? parseInt(newUser.client_id) : null
        })
      });
      if (res.ok) {
        setMessage({ type: 'success', text: 'User created successfully' });
        setIsCreateModalOpen(false);
        setNewUser({ username: '', email: '', password: '', role_id: '', client_id: '' });
        fetchData();
        setTimeout(() => setMessage(null), 3000);
      } else {
        const data = await res.json();
        setMessage({ type: 'error', text: data.detail || 'Creation failed' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Network error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) return <div className="flex justify-center p-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div></div>;

  return (
    <div className="space-y-6">
      {!isTab && (
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">User Management</h1>
            <p className="text-slate-500">Manage account access and assign security roles.</p>
          </div>
          <button 
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all shadow-sm font-medium"
          >
            <Plus size={18} />
            Create User
          </button>
        </div>
      )}

      {isTab && (
        <div className="flex justify-end mb-4">
           <button 
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all shadow-sm font-medium"
          >
            <Plus size={18} />
            Create User
          </button>
        </div>
      )}

      {message && (
        <div className={`p-4 rounded-xl flex items-center gap-3 animate-in fade-in slide-in-from-top-2 duration-300 ${message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {message.type === 'success' ? <Check size={20} /> : <AlertCircle size={20} />}
          {message.text}
        </div>
      )}

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase">User</th>
              <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase">Company</th>
              <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase">Current Role</th>
              <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase">Status</th>
              <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {users.map(user => (
              <tr key={user.id} className="hover:bg-slate-50/50 transition-colors group">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-slate-100 text-slate-500 rounded-full flex items-center justify-center">
                      <UserIcon size={14} />
                    </div>
                    {editingUser === user.id ? (
                      <input
                        className="border rounded-lg px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-blue-500 outline-none w-32"
                        value={editData.username || ''}
                        onChange={(e) => setEditData({ ...editData, username: e.target.value })}
                      />
                    ) : (
                      <span className="font-medium text-slate-900">{user.username}</span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4">
                  {editingUser === user.id ? (
                    <select
                      className="border rounded-lg px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-blue-500 outline-none w-full max-w-[200px]"
                      value={editData.client_id === null ? '' : editData.client_id}
                      onChange={(e) => setEditData({ ...editData, client_id: e.target.value ? parseInt(e.target.value) : null })}
                    >
                      <option value="">Platform Core</option>
                      {clients.map(c => <option key={c.id} value={c.id}>{c.client_name} [{c.company_code}]</option>)}
                    </select>
                  ) : (
                    user.client_id ? (
                      <div className="flex flex-col gap-0.5">
                        <span className="text-xs font-bold text-slate-700">
                          {clients.find(c => c.id === user.client_id)?.client_name || `Tenant [${user.client_id}]`}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400 font-bold bg-slate-50 px-1.5 py-0.5 rounded border border-slate-100 w-fit uppercase">
                          {clients.find(c => c.id === user.client_id)?.company_code || 'NO-CODE'}
                        </span>
                      </div>
                    ) : (
                      <span className="text-xs font-bold bg-purple-50 text-purple-600 px-2 py-1 rounded-md shadow-sm border border-purple-100 uppercase tracking-widest">Platform Core</span>
                    )
                  )}
                </td>
                <td className="px-6 py-4">
                  {editingUser === user.id ? (
                    <select
                      className="border rounded-lg px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-blue-500 outline-none"
                      value={editData.role_id || ''}
                      onChange={(e) => setEditData({ ...editData, role_id: e.target.value ? parseInt(e.target.value) : null })}
                    >
                      <option value="" disabled>-- Select Role --</option>
                      {roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                    </select>
                  ) : (
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${
                      user.role_name === 'SUPER_ADMIN' ? 'bg-purple-100 text-purple-700' :
                      user.role_name === 'ADMIN' ? 'bg-blue-100 text-blue-700' : 
                      user.role_name === 'OPERATOR' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'
                    }`}>
                      <Shield size={12} />
                      {user.role_name}
                    </span>
                  )}
                </td>
                <td className="px-6 py-4">
                  {editingUser === user.id ? (
                    <select
                      className="border rounded-lg px-2 py-1 text-sm bg-white focus:ring-2 focus:ring-blue-500 outline-none"
                      value={editData.is_active ? 'true' : 'false'}
                      onChange={(e) => setEditData({ ...editData, is_active: e.target.value === 'true' })}
                    >
                      <option value="true">Active</option>
                      <option value="false">Inactive</option>
                    </select>
                  ) : (
                  <div className="flex items-center gap-3">
                    <button 
                      onClick={() => handleToggleStatus(user)}
                      disabled={isSubmitting}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold transition-all hover:scale-105 ${
                        user.is_active 
                          ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200' 
                          : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                      }`}
                      title={user.is_active ? 'Click to deactivate' : 'Click to activate'}
                    >
                      <Power size={10} />
                      {user.is_active ? 'ACTIVE' : 'DISABLED'}
                    </button>
                  </div>
                  )}
                </td>
                <td className="px-6 py-4 text-right">
                  {editingUser === user.id ? (
                    <div className="flex justify-end gap-2">
                       <button 
                        onClick={() => handleUpdateUser(user.id)}
                        disabled={isSubmitting}
                        className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-all"
                        title="Save Changes"
                      >
                        <Check size={18} />
                      </button>
                      <button 
                        onClick={() => setEditingUser(null)}
                        className="p-2 text-slate-400 hover:bg-slate-50 rounded-lg transition-all"
                        title="Cancel"
                      >
                        <X size={18} />
                      </button>
                    </div>
                  ) : (
                    <div className="flex justify-end items-center gap-1">
                      <button 
                        onClick={() => handleEditUser(user)}
                        className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all"
                        title="Edit User"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button 
                        onClick={() => setUserToDelete({ id: user.id, username: user.username })}
                        className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
                        title="Delete User"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create User Modal */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
              <h2 className="text-xl font-bold text-slate-800">Create New User</h2>
              <button 
                onClick={() => setIsCreateModalOpen(false)}
                className="p-2 hover:bg-slate-200/50 rounded-full transition-colors text-slate-400"
              >
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="p-6 space-y-5">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-600 flex items-center gap-2">
                  <UserIcon size={14} /> Username
                </label>
                <input 
                  type="text" 
                  required
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                  placeholder="e.g. john_doe"
                  value={newUser.username}
                  onChange={(e) => setNewUser({...newUser, username: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-600 flex items-center gap-2">
                  <UserIcon size={14} /> Email Address
                </label>
                <input 
                  type="email" 
                  required
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                  placeholder="e.g. user@company.com"
                  value={newUser.email}
                  onChange={(e) => setNewUser({...newUser, email: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-600 flex items-center gap-2">
                  <Lock size={14} /> Password
                </label>
                <input 
                  type="password" 
                  required
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                  placeholder="••••••••"
                  value={newUser.password}
                  onChange={(e) => setNewUser({...newUser, password: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold text-slate-600 flex items-center gap-2">
                  <Shield size={14} /> Assign Role
                </label>
                <select 
                  className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                  value={newUser.role_id}
                  onChange={(e) => setNewUser({...newUser, role_id: e.target.value})}
                >
                  <option value="">No Role (Restricted Access)</option>
                  {roles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              {clients.length > 0 && (
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-600 flex items-center gap-2">
                    <Shield size={14} /> Assign Company Context
                  </label>
                  <select 
                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all font-medium"
                    value={newUser.client_id}
                    onChange={(e) => setNewUser({...newUser, client_id: e.target.value})}
                  >
                    <option value="">Platform User (Global Access)</option>
                    {clients.map(c => <option key={c.id} value={c.id}>{c.client_name} [{c.company_code}]</option>)}
                  </select>
                </div>
              )}
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
                  disabled={isSubmitting}
                  className="flex-1 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 transition-all shadow-lg shadow-blue-200 flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {userToDelete && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-sm overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-8 text-center">
              <div className="w-16 h-16 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4 font-bold border-4 border-white shadow-sm">
                <Trash2 size={32} />
              </div>
              <h2 className="text-xl font-bold text-slate-800 mb-2">Delete User</h2>
              <p className="text-sm text-slate-500 mb-6 leading-relaxed">
                Are you sure you want to delete <strong>{userToDelete.username}</strong>? This will permanently remove their access and audit history associations.
              </p>
              <div className="flex gap-3">
                <button 
                  type="button" 
                  onClick={() => setUserToDelete(null)}
                  className="flex-1 py-3 border border-slate-200 text-slate-600 font-bold rounded-xl hover:bg-slate-50 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="button"
                  onClick={handleDeleteUser}
                  disabled={isSubmitting}
                  className="flex-1 bg-red-600 text-white font-bold py-3 rounded-xl hover:bg-red-700 transition-all shadow-lg shadow-red-200 active:scale-95 disabled:opacity-50"
                >
                  {isSubmitting ? 'Deleting...' : 'Confirm'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
