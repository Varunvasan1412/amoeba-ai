import React, { useState, useEffect } from 'react';
import { apiFetch } from '../../utils/api';
import { 
  ShieldCheck, 
  ShieldAlert, 
  Search, 
  Filter, 
  ChevronLeft, 
  ChevronRight,
  Clock,
  Globe,
  User as UserIcon,
  Building,
  Trash2,
  AlertCircle
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface LoginAudit {
  id: number;
  user_id: number | null;
  email: string;
  client_id: number | null;
  company_code: string | null;
  ip_address: string;
  user_agent: string;
  status: string;
  failure_reason: string | null;
  created_at: string;
}

export default function LoginAuditPage() {
  const [audits, setAudits] = useState<LoginAudit[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);
  const [pageSize] = useState(20);
  
   // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Purge State
  const { user } = useAuth();
  const [purgeDays, setPurgeDays] = useState(30);
  const [isPurging, setIsPurging] = useState(false);
  const [purgeMessage, setPurgeMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);

  useEffect(() => {
    fetchAudits();
  }, [page, statusFilter]);

  const fetchAudits = async () => {
    setLoading(true);
    try {
      let url = `/api/audit/login?page=${page}&page_size=${pageSize}`;
      if (searchQuery) url += `&query=${encodeURIComponent(searchQuery)}`;
      if (statusFilter) url += `&status=${statusFilter}`;
      
      const response = await apiFetch(url);
      if (!response.ok) {
        throw new Error(`Error ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setAudits(data?.records || []);
      setTotalRecords(data?.total_records || 0);
    } catch (err) {
      console.error("Failed to fetch login audits", err);
      setAudits([]);
      setTotalRecords(0);
    } finally {
      setLoading(false);
    }
  };

  const handlePurge = async () => {
    if (!window.confirm(`Are you sure you want to permanently delete all login logs older than ${purgeDays} days? This action cannot be undone.`)) {
      return;
    }

    setIsPurging(true);
    setPurgeMessage(null);
    try {
      const response = await apiFetch(`/api/audit/purge-login-audits?days=${purgeDays}`, {
        method: 'POST'
      });
      
      if (response.ok) {
        const result = await response.json();
        setPurgeMessage({ 
          type: 'success', 
          text: `Successfully deleted ${result.deleted_count} old records.` 
        });
        fetchAudits(); // Refresh list
      } else {
        setPurgeMessage({ type: 'error', text: 'Failed to purge logs. Please try again.' });
      }
    } catch (err) {
      setPurgeMessage({ type: 'error', text: 'A network error occurred.' });
    } finally {
      setIsPurging(false);
      // Clear message after 5 seconds
      setTimeout(() => setPurgeMessage(null), 5000);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchAudits();
  };

  const totalPages = Math.ceil(totalRecords / pageSize);

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-800">Login Activity</h1>
          <p className="text-gray-500">Monitor authentication attempts and security events across all tenants.</p>
        </div>

        {(user?.is_admin || user?.permissions?.includes('view_logs')) && (
          <div className="flex items-center gap-3 bg-rose-50 p-3 rounded-xl border border-rose-100">
            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-bold text-rose-600 mb-1">
                {user?.is_platform_user ? 'Purge Global Logs' : 'Purge Company Logs'}
              </span>
              <div className="flex items-center gap-2">
                <select 
                  className="text-sm border border-rose-200 rounded-lg px-2 py-1.5 outline-none focus:ring-2 focus:ring-rose-500 bg-white"
                  value={purgeDays}
                  onChange={(e) => setPurgeDays(parseInt(e.target.value))}
                  disabled={isPurging}
                >
                  <option value={30}>Older than 30 days</option>
                  <option value={60}>Older than 60 days</option>
                  <option value={90}>Older than 90 days</option>
                  <option value={0}>All logs (Clear everything)</option>
                </select>
                <button
                  onClick={handlePurge}
                  disabled={isPurging}
                  className="flex items-center gap-2 bg-rose-600 hover:bg-rose-700 text-white px-4 py-1.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-50"
                >
                  <Trash2 size={16} />
                  {isPurging ? 'Purging...' : 'Purge'}
                </button>
              </div>
            </div>
            {purgeMessage && (
              <div className={`flex items-center gap-2 text-xs font-medium px-3 py-2 rounded-lg animate-in fade-in slide-in-from-right-4 ${
                purgeMessage.type === 'success' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
              }`}>
                <AlertCircle size={14} />
                {purgeMessage.text}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-wrap items-center gap-4">
        <form onSubmit={handleSearch} className="flex-1 min-w-[200px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
          <input 
            type="text" 
            placeholder="Search by user or company..." 
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none transition-all"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </form>
        
        <div className="flex items-center gap-2">
          <Filter size={18} className="text-gray-400" />
          <select 
            className="border border-gray-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="SUCCESS">Success</option>
            <option value="FAILED">Failed</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 border-bottom border-gray-100">
                <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase tracking-wider">User / Company</th>
                <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase tracking-wider">Origin</th>
                <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase tracking-wider">Timestamp</th>
                <th className="px-6 py-4 text-xs font-bold text-gray-500 uppercase tracking-wider">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td colSpan={5} className="px-6 py-4 h-16 bg-gray-50/50"></td>
                  </tr>
                ))
              ) : audits.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">No login activity found.</td>
                </tr>
              ) : (
                audits.map((audit) => (
                  <tr key={audit.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-4">
                      {audit.status === 'SUCCESS' ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                          <ShieldCheck size={14} /> Success
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-100 text-rose-700">
                          <ShieldAlert size={14} /> Failed
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <div className="flex items-center gap-2 text-sm font-semibold text-gray-900">
                          <UserIcon size={14} className="text-gray-400" />
                          {audit.email}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                          <Building size={12} />
                          {audit.company_code || 'N/A'}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <Globe size={14} className="text-gray-400" />
                          {audit.ip_address}
                        </div>
                        <div className="text-[10px] text-gray-400 mt-1 max-w-[200px] truncate" title={audit.user_agent}>
                          {audit.user_agent}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 text-sm text-gray-600 font-mono">
                        <Clock size={14} className="text-gray-400" />
                        {new Date(audit.created_at).toLocaleString()}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-xs">
                       {audit.failure_reason ? (
                         <span className="text-rose-600 italic font-medium">{audit.failure_reason}</span>
                       ) : (
                         <span className="text-gray-400">—</span>
                       )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
          <div className="text-sm text-gray-500">
            Showing <span className="font-medium">{(page-1)*pageSize + 1}</span> to <span className="font-medium">{Math.min(page*pageSize, totalRecords)}</span> of <span className="font-medium">{totalRecords}</span> results
          </div>
          <div className="flex items-center gap-2">
            <button 
              disabled={page === 1 || loading}
              onClick={() => setPage(p => p - 1)}
              className="p-2 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-all font-medium"
            >
              <ChevronLeft size={18} />
            </button>
            <span className="px-4 py-2 text-sm font-bold text-gray-700">Page {page} of {totalPages || 1}</span>
            <button 
              disabled={page === totalPages || loading}
              onClick={() => setPage(p => p + 1)}
              className="p-2 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-all font-medium"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
