import { useState, useEffect } from "react";
import { 
  RotateCcw, 
  Download, 
  Eye, 
  Shield, 
  Database, 
  Clock,
  X,
  FileText,
  MousePointer2,
  LogIn,
  LogOut,
  Upload,
  RefreshCw,
  Plus,
  Trash2,
  Settings,
  AlertCircle,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  User as UserIcon
} from "lucide-react";
import { format } from "date-fns";
import { useAdmin } from "../../context/AdminContext";
import { apiFetch } from "../../utils/api";

interface AuditLogEntry {
  id: string;
  timestamp: string;
  client_id?: number;
  user_id?: string;
  action: string;
  entity?: string;
  table_name?: string;
  record_id?: string;
  source: string;
  status: string;
  details: any;
  ip_address?: string;
}

const ACTION_ICONS: Record<string, any> = {
  CREATE: Plus,
  UPDATE: Settings,
  DELETE: Trash2,
  READ: Eye,
  UPLOAD: Upload,
  RETRY: RotateCcw,
  REINDEX: RefreshCw,
  NAVIGATION: MousePointer2,
  LOGIN: LogIn,
  LOGOUT: LogOut,
};

const SOURCE_COLORS: Record<string, string> = {
  USER: "bg-blue-100 text-blue-700 border-blue-200",
  AI: "bg-purple-100 text-purple-700 border-purple-200",
  SYSTEM: "bg-slate-100 text-slate-700 border-slate-200",
};

export default function AuditPage() {
  const { clientId } = useAdmin();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  
  // Sorting
  const [sortBy, setSortBy] = useState("timestamp");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  
  // Filters
  const [action, setAction] = useState("");
  const [status, setStatus] = useState("");
  
  // Modal
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    fetchLogs();
  }, [page, clientId, sortBy, sortOrder, action, status]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      let url = `/api/audit/logs?page=${page}&page_size=${pageSize}&sort_by=${sortBy}&sort_order=${sortOrder}`;
      if (clientId) url += `&client_id=${clientId}`;
      if (action) url += `&action=${action}`;
      if (status) url += `&status=${status}`;
      
      const res = await apiFetch(url);
      const data = await res.json();
      setLogs(data.records);
      setTotal(data.total_records);
    } catch (err) {
      console.error("Failed to fetch logs", err);
    } finally {
      setLoading(false);
    }
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
    setPage(1);
  };


  const handleReset = () => {
    setAction("");
    setStatus("");
    setPage(1);
    fetchLogs();
  };

  const handleClearAll = async () => {
    setClearing(true);
    try {
      await apiFetch(`/api/audit/clear`, { method: "DELETE" });
      setShowClearConfirm(false);
      fetchLogs();
    } catch (err) {
      console.error("Failed to clear logs", err);
    } finally {
      setClearing(false);
    }
  };

  const handleExport = async () => {
    try {
      let url = `/api/audit/export?`;
      if (clientId) url += `&client_id=${clientId}`;
      if (action) url += `&action=${action}`;
      if (status) url += `&status=${status}`;
      
      const res = await apiFetch(url);
      const blob = await res.blob();
      const filename = `audit_export_${new Date().getTime()}.csv`;
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.download = filename;
      link.click();
    } catch (err) {
      console.error("Export failed", err);
    }
  };

  const getActionIcon = (act: string) => {
    const Icon = ACTION_ICONS[act] || FileText;
    return <Icon size={14} />;
  };

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-500">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <div className="p-2 bg-blue-600 rounded-xl text-white shadow-lg shadow-blue-200">
                <Shield size={24} />
            </div>
            Audit Trail
          </h1>
          <p className="text-gray-500 mt-1">Monitor all system activities and user actions.</p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => setShowClearConfirm(true)}
            className="bg-red-50 text-red-600 px-4 py-2.5 rounded-xl font-bold text-sm hover:bg-red-100 transition-all flex items-center gap-2 border border-red-100"
          >
            <Trash2 size={18} />
            Clear History
          </button>
          <button 
            onClick={handleExport}
            className="bg-white border border-gray-200 text-gray-700 px-4 py-2.5 rounded-xl font-bold text-sm shadow-sm hover:bg-gray-50 transition-all flex items-center gap-2"
          >
            <Download size={18} className="text-blue-600" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[200px]">
          <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1 block px-1">Action</label>
          <div className="relative">
            <select
              value={action}
              onChange={(e) => { setAction(e.target.value); setPage(1); }}
              className="w-full bg-gray-50 border-none rounded-xl py-2.5 pl-3 pr-10 text-sm focus:ring-2 focus:ring-blue-500 outline-none appearance-none"
            >
              <option value="">All Actions</option>
              <option value="CREATE">CREATE</option>
              <option value="UPDATE">UPDATE</option>
              <option value="DELETE">DELETE</option>
              <option value="READ">READ</option>
              <option value="UPLOAD">UPLOAD</option>
              <option value="RETRY">RETRY</option>
              <option value="NAVIGATION">NAVIGATION</option>
              <option value="LOGIN">LOGIN</option>
              <option value="LOGOUT">LOGOUT</option>
            </select>
            <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
               <RotateCcw size={14} />
            </div>
          </div>
        </div>

        <div className="flex-1 min-w-[200px]">
          <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider mb-1 block px-1">Status</label>
          <div className="relative">
            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1); }}
              className="w-full bg-gray-50 border-none rounded-xl py-2.5 pl-3 pr-10 text-sm focus:ring-2 focus:ring-blue-500 outline-none appearance-none"
            >
              <option value="">All Statuses</option>
              <option value="SUCCESS">SUCCESS</option>
              <option value="FAILED">FAILED</option>
            </select>
            <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
               <AlertCircle size={14} />
            </div>
          </div>
        </div>

        <div className="flex gap-2 items-end">
           <button 
             onClick={handleReset}
             className="bg-gray-100 text-gray-600 p-2.5 rounded-xl hover:bg-gray-200 transition-all"
             title="Reset Filters"
           >
             <RotateCcw size={18} />
           </button>
        </div>
      </div>

      {/* Logs Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th 
                  className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 transition-colors group"
                  onClick={() => toggleSort("timestamp")}
                >
                  <div className="flex items-center gap-1 group-hover:text-blue-600">
                    Timestamp
                    {sortBy === "timestamp" ? (
                      sortOrder === "asc" ? <ChevronUp size={14} className="text-blue-600" /> : <ChevronDown size={14} className="text-blue-600" />
                    ) : (
                      <ChevronsUpDown size={14} className="opacity-0 group-hover:opacity-100 text-gray-300" />
                    )}
                  </div>
                </th>
                <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider">User</th>
                <th 
                  className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 transition-colors group"
                  onClick={() => toggleSort("action")}
                >
                  <div className="flex items-center gap-1 group-hover:text-blue-600">
                    Action
                    {sortBy === "action" ? (
                      sortOrder === "asc" ? <ChevronUp size={14} className="text-blue-600" /> : <ChevronDown size={14} className="text-blue-600" />
                    ) : (
                      <ChevronsUpDown size={14} className="opacity-0 group-hover:opacity-100 text-gray-300" />
                    )}
                  </div>
                </th>
                <th 
                  className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 transition-colors group"
                  onClick={() => toggleSort("entity")}
                >
                  <div className="flex items-center gap-1 group-hover:text-blue-600">
                    Entity/Table
                    {sortBy === "entity" ? (
                      sortOrder === "asc" ? <ChevronUp size={14} className="text-blue-600" /> : <ChevronDown size={14} className="text-blue-600" />
                    ) : (
                      <ChevronsUpDown size={14} className="opacity-0 group-hover:opacity-100 text-gray-300" />
                    )}
                  </div>
                </th>
                <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider">Source</th>
                <th 
                  className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-gray-100 transition-colors group"
                  onClick={() => toggleSort("status")}
                >
                  <div className="flex items-center gap-1 group-hover:text-blue-600">
                    Status
                    {sortBy === "status" ? (
                      sortOrder === "asc" ? <ChevronUp size={14} className="text-blue-600" /> : <ChevronDown size={14} className="text-blue-600" />
                    ) : (
                      <ChevronsUpDown size={14} className="opacity-0 group-hover:opacity-100 text-gray-300" />
                    )}
                  </div>
                </th>
                <th className="px-6 py-4 text-xs font-bold text-gray-400 uppercase tracking-wider"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td colSpan={7} className="px-6 py-4">
                      <div className="h-4 bg-gray-100 rounded w-full"></div>
                    </td>
                  </tr>
                ))
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-400">
                    <Database size={48} className="mx-auto mb-4 opacity-20" />
                    <p>No audit records found.</p>
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr 
                    key={log.id} 
                    className="hover:bg-blue-50/50 cursor-pointer transition-colors"
                    onClick={() => setSelectedLog(log)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-gray-800">
                          {format(new Date(log.timestamp), "MMM d, yyyy")}
                        </span>
                        <span className="text-[10px] text-gray-400 font-mono">
                          {format(new Date(log.timestamp), "HH:mm:ss.SSS")}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                       <div className="flex items-center gap-2">
                          <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-gray-500 uppercase font-bold text-xs">
                             {(log.user_id || "S")[0]}
                          </div>
                          <span className="text-sm text-gray-600 font-medium">{log.user_id || "SYSTEM"}</span>
                       </div>
                    </td>
                    <td className="px-6 py-4">
                       <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-blue-50 text-blue-700 border border-blue-100 capitalize">
                          {getActionIcon(log.action)}
                          {log.action.toLowerCase()}
                       </span>
                    </td>
                    <td className="px-6 py-4">
                       <div className="flex flex-col">
                          <span className="text-sm text-gray-700 font-medium">{log.entity || "-"}</span>
                          <span className="text-xs text-gray-400 font-mono">{log.table_name || "-"}</span>
                       </div>
                    </td>
                    <td className="px-6 py-4">
                       <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${SOURCE_COLORS[log.source] || SOURCE_COLORS.SYSTEM}`}>
                          {log.source}
                       </span>
                    </td>
                    <td className="px-6 py-4">
                       {log.status === "SUCCESS" ? (
                         <span className="flex items-center gap-1.5 text-emerald-600 text-xs font-bold">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
                            SUCCESS
                         </span>
                       ) : (
                         <span className="flex items-center gap-1.5 text-red-600 text-xs font-bold">
                            <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></div>
                            FAILED
                         </span>
                       )}
                    </td>
                    <td className="px-6 py-4 text-right">
                       <button className="p-2 hover:bg-blue-100 rounded-lg text-gray-400 hover:text-blue-600 transition-all">
                          <Eye size={18} />
                       </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        {total > pageSize && (
          <div className="bg-gray-50 px-6 py-4 flex justify-between items-center border-t border-gray-100">
            <span className="text-xs text-gray-500 font-medium">
              Showing {logs.length > 0 ? (page - 1) * pageSize + 1 : 0} to {(page - 1) * pageSize + logs.length} of {total} records
            </span>
            <div className="flex gap-2">
               <button 
                 disabled={page === 1}
                 onClick={() => setPage(page - 1)}
                 className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm font-bold disabled:opacity-50 hover:bg-gray-50 transition-all shadow-sm"
               >
                 Previous
               </button>
               <button 
                 disabled={logs.length < pageSize}
                 onClick={() => setPage(page + 1)}
                 className="px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm font-bold disabled:opacity-50 hover:bg-gray-50 transition-all shadow-sm"
               >
                 Next
               </button>
            </div>
          </div>
        )}
      </div>

      {/* Details Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
           <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={() => setSelectedLog(null)}></div>
           <div className="bg-white rounded-3xl w-full max-w-2xl shadow-2xl relative z-10 overflow-hidden flex flex-col max-h-[90vh]">
              <div className="p-6 border-b border-gray-100 flex justify-between items-center bg-gray-50/50">
                 <div>
                    <h2 className="text-xl font-bold text-gray-900 group flex items-center gap-2">
                       Event Details
                       <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${SOURCE_COLORS[selectedLog.source]}`}>
                          {selectedLog.source}
                       </span>
                    </h2>
                    <p className="text-xs text-gray-400 font-mono mt-0.5 truncate max-w-[300px]">{selectedLog.id}</p>
                 </div>
                 <button onClick={() => setSelectedLog(null)} className="p-2 hover:bg-gray-200 rounded-full transition-colors">
                    <X size={20} className="text-gray-500" />
                 </button>
              </div>
              
              <div className="p-8 overflow-y-auto grid grid-cols-2 gap-8">
                 <div className="space-y-6">
                    <div>
                       <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5 mb-1.5">
                          <Clock size={12}/> Timestamp
                       </label>
                       <p className="text-sm font-medium text-gray-800">
                          {format(new Date(selectedLog.timestamp), "EEEE, MMMM do, yyyy")}
                       </p>
                       <p className="text-xs text-gray-500 font-mono mt-0.5">
                          {format(new Date(selectedLog.timestamp), "HH:mm:ss.SSS (xxx)")}
                       </p>
                    </div>

                    <div>
                       <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5 mb-1.5">
                          <UserIcon size={12}/> Initiator
                       </label>
                       <div className="bg-gray-100/50 p-3 rounded-xl border border-gray-100 flex items-center gap-3">
                          <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold">
                             {(selectedLog.user_id || "S")[0]}
                          </div>
                          <div>
                             <p className="text-sm font-bold text-gray-800">{selectedLog.user_id || "SYSTEM"}</p>
                             <p className="text-[10px] text-gray-500 font-mono">IP: {selectedLog.ip_address || "Internal"}</p>
                          </div>
                       </div>
                    </div>

                    <div>
                       <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5 mb-1.5">
                          <Settings size={12}/> Operation
                       </label>
                       <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2">
                             <span className="text-sm font-bold text-gray-800">{selectedLog.action}</span>
                             <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${selectedLog.status === "SUCCESS" ? "bg-emerald-50 text-emerald-700 border-emerald-100" : "bg-red-50 text-red-700 border-red-100"}`}>
                                {selectedLog.status}
                             </span>
                          </div>
                          <p className="text-xs text-gray-500">
                             Analyzed on <span className="font-mono">{selectedLog.table_name || "N/A"}</span>
                          </p>
                       </div>
                    </div>
                 </div>

                 <div className="space-y-6">
                    <div>
                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5 mb-1.5">
                           <FileText size={12}/> Metadata / Details
                        </label>
                        <div className="bg-slate-900 rounded-2xl p-4 overflow-hidden shadow-inner flex flex-col h-full max-h-[300px]">
                           <pre className="text-[11px] font-mono text-emerald-400/90 overflow-auto scrollbar-hide">
                              {JSON.stringify(selectedLog.details, null, 2)}
                           </pre>
                        </div>
                    </div>

                    {selectedLog.record_id && (
                       <div>
                          <label className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5 mb-1.5">
                             <Database size={12}/> Record Mapping
                          </label>
                          <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-3">
                             <p className="text-xs font-medium text-blue-900 mb-1">Target Resource ID:</p>
                             <code className="text-[10px] font-mono bg-white px-2 py-1 rounded inline-block text-blue-600 border border-blue-100">
                                {selectedLog.record_id}
                             </code>
                          </div>
                       </div>
                    )}
                 </div>
              </div>

              <div className="p-6 bg-gray-50/50 border-t border-gray-100 flex justify-end">
                 <button 
                   onClick={() => setSelectedLog(null)}
                   className="bg-slate-900 text-white px-6 py-2.5 rounded-xl font-bold text-sm hover:bg-slate-800 transition-all shadow-lg"
                 >
                   Dismiss
                 </button>
              </div>
           </div>
        </div>
      )}
      {/* Clear Confirmation Modal */}
      {showClearConfirm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={() => setShowClearConfirm(false)}></div>
          <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl relative z-[70] p-8 text-center border border-gray-100">
            <div className="w-16 h-16 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <AlertCircle size={32} />
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Clear Audit History?</h3>
            <p className="text-gray-500 mb-8 text-sm">This will permanently delete ALL activity logs from the database. This action cannot be undone.</p>
            <div className="flex gap-3">
              <button 
                onClick={() => setShowClearConfirm(false)}
                className="flex-1 px-4 py-2.5 border border-gray-200 text-gray-600 font-bold rounded-xl hover:bg-gray-50 transition-all shadow-sm"
              >
                Cancel
              </button>
              <button 
                onClick={handleClearAll}
                disabled={clearing}
                className="flex-1 px-4 py-2.5 bg-red-600 text-white font-bold rounded-xl hover:bg-red-700 transition-all shadow-lg shadow-red-200 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {clearing ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" />
                    Clearing...
                  </>
                ) : "Yes, Clear All"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
