import React, { useState, useEffect } from "react";
import { useAdmin } from "../../context/AdminContext";
import { apiFetch } from "../../utils/api";
import { 
  Plus, 
  Building2, 
  Search, 
  ExternalLink, 
  Settings2, 
  ShieldCheck, 
  Globe,
  AlertCircle,
  Copy,
  Check,
  Trash2,
} from "lucide-react";
import { toast } from "react-toastify";

interface Tenant {
  id: number;
  client_name: string;
  company_code: string | null;
  api_key: string;
  is_active: boolean;
  created_at: string | null;
}

export default function TenantManagementPage() {
  const { clients, refreshClients, setClientId, setClientName, setApiKey } = useAdmin();
  const [searchTerm, setSearchTerm] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [newTenant, setNewTenant] = useState({ client_name: "", company_code: "" });
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [tenantToDelete, setTenantToDelete] = useState<{id: number, name: string} | null>(null);

  useEffect(() => {
    refreshClients();
  }, []);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "N/A";
    try {
      const date = new Date(dateStr);
      if (isNaN(date.getTime())) return "N/A";
      return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
      return "N/A";
    }
  };

  const copyToClipboard = async (text: string, id: number) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "absolute";
        textArea.style.left = "-999999px";
        document.body.prepend(textArea);
        textArea.select();
        try {
          document.execCommand('copy');
        } catch (error) {
          console.error("Fallback copy failed", error);
        } finally {
          textArea.remove();
        }
      }
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
      toast.success("Copied to clipboard");
    } catch (err) {
      toast.error("Failed to copy API key");
    }
  };

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTenant.client_name.trim()) return;

    setLoading(true);
    try {
      const response = await apiFetch("/api/clients", {
        method: "POST",
        body: JSON.stringify(newTenant),
      });

      if (!response.ok) throw new Error("Failed to create tenant");

      toast.success(`Tenant "${newTenant.client_name}" created successfully!`);
      setIsModalOpen(false);
      setNewTenant({ client_name: "", company_code: "" });
      await refreshClients();
    } catch (err) {
      toast.error("Error creating tenant. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingTenant) return;

    setLoading(true);
    try {
      const response = await apiFetch(`/api/clients/${editingTenant.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          client_name: editingTenant.client_name,
          company_code: editingTenant.company_code
        }),
      });

      if (!response.ok) throw new Error("Failed to update tenant");

      toast.success(`Tenant "${editingTenant.client_name}" updated!`);
      setIsEditModalOpen(false);
      setEditingTenant(null);
      await refreshClients();
    } catch (err) {
      toast.error("Failed to update tenant");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStatus = async (tenantId: number, currentStatus: boolean) => {
    try {
      const response = await apiFetch(`/api/clients/${tenantId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !currentStatus }),
      });
      if (response.ok) {
        toast.info("Tenant status updated");
        await refreshClients();
      }
    } catch (err) {
      toast.error("Failed to update status");
    }
  };

  const handleGenerateCode = async (tenantId: number) => {
    setLoading(true);
    try {
      const response = await apiFetch(`/api/clients/${tenantId}/generate-code`, {
        method: "POST"
      });
      if (response.ok) {
        toast.success("Company code generated!");
        await refreshClients();
      }
    } catch (err) {
      toast.error("Failed to generate code");
    } finally {
      setLoading(false);
    }
  };

  const handleRotateKey = async (tenantId: number) => {
    // if (!window.confirm("Are you sure? This will invalidate the existing API key immediately.")) return;
    setLoading(true);
    try {
      const response = await apiFetch(`/api/clients/${tenantId}/rotate-key`, {
        method: "POST"
      });
      if (response.ok) {
        toast.success("API Key rotated successfully!");
        await refreshClients();
      }
    } catch (err) {
      toast.error("Failed to change API Key");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTenant = (tenantId: number, name: string) => {
    setTenantToDelete({ id: tenantId, name });
  };

  const confirmDeleteTenant = async () => {
    if (!tenantToDelete) return;
    setLoading(true);
    try {
      const response = await apiFetch(`/api/clients/${tenantToDelete.id}`, {
        method: "DELETE"
      });
      if (response.ok) {
        toast.success(`Company '${tenantToDelete.name}' deleted successfully`);
        await refreshClients();
      } else {
        toast.error("Failed to delete company");
      }
    } catch (err) {
      toast.error("Failed to delete company");
    } finally {
      setLoading(false);
      setTenantToDelete(null);
    }
  };

  const filteredTenants = clients.filter(c => 
    c.client_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.company_code && c.company_code.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="space-y-8 animate-in fade-in duration-700">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Tenant Management</h1>
          <p className="text-gray-500 mt-1">Onboard and manage multi-tenant enterprise clients.</p>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-bold shadow-lg shadow-blue-200 transition-all active:scale-95"
        >
          <Plus size={20} />
          <span>Add New Company</span>
        </button>
      </div>

      {/* Stats & Tools Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
            <Building2 size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium text-uppercase tracking-wider">Total Tenants</p>
            <p className="text-2xl font-bold text-gray-900">{clients.length}</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm flex items-center gap-4">
          <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center">
            <ShieldCheck size={24} />
          </div>
          <div>
            <p className="text-sm text-gray-500 font-medium text-uppercase tracking-wider">Active Instances</p>
            <p className="text-2xl font-bold text-gray-900">{clients.filter((c: any) => c.is_active !== false).length}</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm relative overflow-hidden group">
          <div className="relative z-10">
            <p className="text-sm text-gray-500 font-medium mb-2">Search Companies</p>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
              <input 
                type="text" 
                placeholder="Name or Company Code..."
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>
          <Globe className="absolute -bottom-4 -right-4 w-24 h-24 text-gray-50 opacity-50 group-hover:scale-110 transition-transform" />
        </div>
      </div>

      {/* Tenants Table */}
      <div className="bg-white rounded-3xl border border-gray-100 shadow-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50/50 border-b border-gray-100">
                <th className="px-8 py-5 text-xs font-bold text-gray-500 uppercase tracking-widest">Company Info</th>
                <th className="px-8 py-5 text-xs font-bold text-gray-500 uppercase tracking-widest">Access Config</th>
                <th className="px-8 py-5 text-xs font-bold text-gray-500 uppercase tracking-widest text-center">Status</th>
                <th className="px-8 py-5 text-xs font-bold text-gray-500 uppercase tracking-widest text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filteredTenants.map((tenant) => (
                <tr 
                  key={tenant.id} 
                  className={`transition-colors group ${tenant.is_active !== false ? 'hover:bg-blue-50/30' : 'bg-gray-50/80 opacity-[0.65] grayscale-[0.5]'}`}
                >
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center font-bold ${tenant.is_active !== false ? 'bg-slate-100 text-slate-600' : 'bg-gray-200 text-gray-500'}`}>
                        {tenant.client_name[0]}
                      </div>
                      <div>
                        <div className="font-bold text-gray-900 group-hover:text-blue-600 transition-colors uppercase tracking-tight">
                          {tenant.client_name}
                        </div>
                        <div className="text-xs text-gray-400 flex items-center gap-1 mt-1">
                          <AlertCircle size={12} />
                          ID: {tenant.id} | Created: {formatDate(tenant.created_at)}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase ${tenant.is_active !== false ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-600'}`}>Code</span>
                        {tenant.company_code ? (
                          <code className="text-sm font-mono text-gray-700 font-bold">{tenant.company_code}</code>
                        ) : (
                          <button 
                            disabled={loading || tenant.is_active === false}
                            onClick={() => handleGenerateCode(tenant.id)}
                            className="text-[10px] font-bold text-blue-600 hover:text-blue-800 underline underline-offset-2 flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                          >
                            <Plus size={10} /> Generate Code
                          </button>
                        )}
                      </div>
                      <div className="flex flex-col gap-1">
                        <div 
                          className={`flex items-center gap-2 group/key ${tenant.is_active !== false ? 'cursor-pointer' : ''}`} 
                          onClick={() => tenant.is_active !== false && copyToClipboard(tenant.api_key, tenant.id)} 
                          title={tenant.is_active !== false ? "Click to copy API Key" : "Disabled"}
                        >
                          <span className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase ${tenant.is_active !== false ? 'bg-slate-100 text-slate-700' : 'bg-gray-200 text-gray-500'}`}>API Key</span>
                          <code className="text-xs font-mono text-gray-400 group-hover/key:text-blue-600 transition-colors">
                            {tenant.api_key.substring(0, 12)}...
                          </code>
                          <Copy size={12} className={`transition-all ${copiedId === tenant.id ? "text-emerald-500 scale-125" : "text-gray-400 opacity-40 group-hover/key:opacity-100"}`} />
                          {copiedId === tenant.id && <Check size={12} className="text-emerald-500 animate-in zoom-in" />}
                        </div>
                        <button 
                          onClick={() => handleRotateKey(tenant.id)}
                          disabled={tenant.is_active === false}
                          className="text-[10px] font-bold text-slate-400 hover:text-red-600 bg-slate-50 hover:bg-red-50 px-2 py-0.5 rounded transition-all mt-1 w-fit border border-transparent hover:border-red-100 disabled:opacity-50 disabled:hover:text-slate-400 disabled:hover:bg-slate-50"
                        >
                          Change API Key
                        </button>
                      </div>
                    </div>
                  </td>
                  <td className="px-8 py-6 text-center">
                    <button 
                      onClick={() => handleToggleStatus(tenant.id, tenant.is_active !== false)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold transition-all hover:scale-105 active:scale-95 ${
                        tenant.is_active !== false 
                          ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200" 
                          : "bg-gray-200 text-gray-600 hover:bg-gray-300"
                      }`}
                      title={tenant.is_active !== false ? "Click to Disable" : "Click to Enable"}
                    >
                      <div className={`w-1.5 h-1.5 rounded-full ${tenant.is_active !== false ? "bg-emerald-500" : "bg-gray-500"}`} />
                      {tenant.is_active !== false ? "ACTIVE" : "DISABLED"}
                    </button>
                  </td>
                  <td className="px-8 py-6 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button 
                        onClick={() => {
                          setClientId(tenant.id);
                          setClientName(tenant.client_name);
                          setApiKey(tenant.api_key);
                          toast.success(`Switched context to ${tenant.client_name}`);
                        }}
                        disabled={tenant.is_active === false}
                        className="p-2 hover:bg-blue-100 text-blue-600 rounded-lg transition-all disabled:opacity-50 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                        title={tenant.is_active !== false ? "Enter Dashboard" : "Cannot access disabled tenant"}
                      >
                        <ExternalLink size={18} />
                      </button>
                      <button 
                        onClick={() => {
                          setEditingTenant(tenant);
                          setIsEditModalOpen(true);
                        }}
                        disabled={tenant.is_active === false}
                        className="p-2 hover:bg-slate-100 text-slate-400 hover:text-blue-600 rounded-lg transition-all disabled:opacity-50 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                        title={tenant.is_active !== false ? "Edit Settings" : "Cannot edit disabled tenant"}
                      >
                        <Settings2 size={18} />
                      </button>
                      <button 
                        onClick={() => handleDeleteTenant(tenant.id, tenant.client_name)}
                        className="p-2 hover:bg-red-100 text-red-500 hover:text-red-700 rounded-lg transition-all"
                        title="Delete Company"
                      >
                        <Trash2 size={18} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {filteredTenants.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-8 py-12 text-center text-gray-400">
                    <div className="max-w-xs mx-auto">
                        <Search size={48} className="mx-auto mb-4 text-gray-200" />
                        <p className="font-medium text-gray-500">No companies found</p>
                        <p className="text-sm">Try searching for a different name or add a new tenant.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Tenant Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="bg-white w-full max-w-md rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-8 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
              <div>
                <h2 className="text-xl font-bold text-gray-900">New Client Onboarding</h2>
                <p className="text-sm text-gray-500 mt-1">Configure basic identity for a new tenant.</p>
              </div>
              <button onClick={() => setIsModalOpen(false)} className="text-gray-400 hover:text-gray-600 transition-colors">
                <Plus className="rotate-45" size={24} />
              </button>
            </div>
            
            <form onSubmit={handleCreateTenant} className="p-8 space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-gray-700 flex items-center gap-2">
                  <Building2 size={16} className="text-blue-600" />
                  Legal Company Name
                </label>
                <input 
                  autoFocus
                  required
                  type="text" 
                  placeholder="e.g. Acme Corp Industries"
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none bg-gray-50/30"
                  value={newTenant.client_name}
                  onChange={(e) => setNewTenant({...newTenant, client_name: e.target.value})}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-bold text-gray-700 flex items-center gap-2">
                  <ShieldCheck size={16} className="text-emerald-600" />
                  Company Login Code
                </label>
                <input 
                  type="text" 
                  placeholder="e.g. ACME-001"
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none bg-gray-50/30 uppercase font-mono tracking-wider"
                  value={newTenant.company_code}
                  onChange={(e) => setNewTenant({...newTenant, company_code: e.target.value.toUpperCase()})}
                />
                <p className="text-[10px] text-gray-400 mt-1 italic">
                  * This code is required for non-platform users to login to this tenant.
                </p>
              </div>

              <div className="pt-4 flex gap-3">
                <button 
                  type="button" 
                  onClick={() => setIsModalOpen(false)}
                  className="flex-1 py-3 border border-gray-200 text-gray-600 font-bold rounded-xl hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={loading}
                  className="flex-2 bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-xl shadow-lg shadow-blue-100 transition-all active:scale-95 disabled:opacity-50"
                >
                  {loading ? "Creating..." : "Launch Instance"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Tenant Modal */}
      {isEditModalOpen && editingTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="bg-white w-full max-w-md rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-8 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
              <div>
                <h2 className="text-xl font-bold text-gray-900">Edit Company Settings</h2>
                <p className="text-sm text-gray-500 mt-1">Update identity and access configuration.</p>
              </div>
              <button onClick={() => setIsEditModalOpen(false)} className="text-gray-400 hover:text-gray-600 transition-colors">
                <Plus className="rotate-45" size={24} />
              </button>
            </div>
            
            <form onSubmit={handleUpdateTenant} className="p-8 space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-gray-700">Company Name</label>
                <input 
                  required
                  type="text" 
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none bg-gray-50/30"
                  value={editingTenant.client_name}
                  onChange={(e) => setEditingTenant({...editingTenant, client_name: e.target.value})}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-bold text-gray-700">Company Login Code</label>
                <input 
                  type="text" 
                  placeholder="e.g. ACME-001"
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 transition-all outline-none bg-gray-50/30 uppercase font-mono tracking-wider"
                  value={editingTenant.company_code || ""}
                  onChange={(e) => setEditingTenant({...editingTenant, company_code: e.target.value.toUpperCase()})}
                />
              </div>

              <div className="pt-4 flex gap-3">
                <button 
                  type="button" 
                  onClick={() => setIsEditModalOpen(false)}
                  className="flex-1 py-3 border border-gray-200 text-gray-600 font-bold rounded-xl hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={loading}
                  className="flex-2 bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-xl shadow-lg shadow-blue-100"
                >
                  {loading ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {tenantToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="bg-white w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-8 text-center">
              <div className="w-16 h-16 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <AlertCircle size={32} />
              </div>
              <h2 className="text-xl font-bold text-gray-900 mb-2">Delete Company</h2>
              <p className="text-sm text-gray-500 mb-6">
                Are you sure you want to completely delete <strong>{tenantToDelete.name}</strong>? This action cannot be undone and will detach all associated users.
              </p>
              <div className="flex gap-3">
                <button 
                  type="button" 
                  onClick={() => setTenantToDelete(null)}
                  className="flex-1 py-3 border border-gray-200 text-gray-600 font-bold rounded-xl hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="button"
                  onClick={confirmDeleteTenant}
                  disabled={loading}
                  className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 rounded-xl shadow-lg shadow-red-100 transition-all active:scale-95 disabled:opacity-50"
                >
                  {loading ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
