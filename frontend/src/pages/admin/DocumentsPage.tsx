import { useState, useEffect, useRef } from "react";
import { toast } from "react-toastify";
import { useAdmin } from "../../context/AdminContext";
import { apiFetch } from "../../utils/api";
import { 
  RefreshCw, 
  Trash2, 
  Search, 
  ChevronLeft, 
  ChevronRight, 
  AlertCircle,
  FileText,
  AlertTriangle,
  Database,
  Globe,
  Upload,
  Eye,
  X,
  Download,
  FileSpreadsheet
} from "lucide-react";

interface Document {
  id: number;
  filename: string;
  status: "READY" | "PROCESSING" | "FAILED" | "UPLOADING";
  file_size: number;
  chunk_count: number;
  upload_time: string;
  processing_time_ms: number | null;
}

interface Metrics {
  storage_used_mb: number;
  storage_limit_mb: number;
  document_count: number;
  document_limit: number;
}

const ControlButton = ({ onClick, icon: Icon, label, color = "blue", disabled = false, danger = false }: any) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`p-2 rounded-xl transition-all flex items-center justify-center gap-2 group relative shadow-sm border
      ${danger ? 'text-red-500 bg-red-50 border-red-100 hover:bg-red-100' : 'text-slate-400 bg-white border-gray-100 hover:text-blue-600 hover:border-blue-200 hover:bg-blue-50'}
      disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-all`}
    title={label}
  >
    <Icon size={16} />
  </button>
);

const SourceCard = ({ label, description, isActive, onChange, icon: Icon, disabled = false, loading = false }: any) => (
    <div className={`p-4 h-full rounded-2xl border transition-all flex items-center justify-between gap-4 
        ${isActive ? 'bg-blue-50/50 border-blue-200 shadow-sm' : 'bg-white border-gray-100 opacity-70 hover:opacity-100'}
        ${disabled ? 'grayscale' : ''}`}>
        <div className="flex items-center gap-4 min-w-0 text-left">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all shrink-0
                ${isActive ? 'bg-blue-600 text-white shadow-lg shadow-blue-200' : 'bg-gray-100 text-gray-400'}`}>
                <Icon size={20} />
            </div>
            <div className="truncate">
                <h4 className={`font-bold text-sm leading-tight ${isActive ? 'text-blue-900' : 'text-gray-700'}`}>{label}</h4>
                <p className="text-[10px] text-gray-500 mt-0.5 truncate uppercase tracking-wider font-semibold opacity-60">{description}</p>
            </div>
        </div>
        <button 
           onClick={() => !disabled && onChange()}
           disabled={disabled || loading}
           className={`relative w-10 h-5 rounded-full transition-all duration-300 outline-none p-0.5 shrink-0
                ${isActive ? 'bg-blue-600 shadow-inner' : 'bg-gray-200'}
                ${disabled ? 'cursor-not-allowed' : 'cursor-pointer hover:ring-4 hover:ring-blue-500/10'}`}
        >
            <div className={`w-4 h-4 bg-white rounded-full shadow-lg transition-all duration-300 transform flex items-center justify-center
                ${isActive ? 'translate-x-5' : 'translate-x-0'}`}>
                {loading && <RefreshCw className="w-2.5 h-2.5 animate-spin text-blue-600" />}
            </div>
        </button>
    </div>
);

const formatStorage = (mb: number) => {
    if (!mb || mb === 0) return "0.0 MB";
    if (mb < 0.1) return `${(mb * 1024).toFixed(1)} KB`;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(2)} GB`;
};

export default function DocumentsPage() {
  const { clientId } = useAdmin();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState("");
  const [total, setTotal] = useState(0);

  // Source Settings state (Integrated from SourceSettingsPage)
  const { clients, refreshClients } = useAdmin();
  const [sources, setSources] = useState({
    erp: true,
    documents: true,
    web: false
  });
  const [savingSources, setSavingSources] = useState(false);

  // Deletion state
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isDeletingAll, setIsDeletingAll] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Preview state
  const [viewingDoc, setViewingDoc] = useState<Document | null>(null);
  const [viewingText, setViewingText] = useState<string | null>(null);
  const [structuredPreview, setStructuredPreview] = useState<{headers: string[], rows: any[]} | null>(null);
  const [loadingText, setLoadingText] = useState(false);

  useEffect(() => {
    if (clientId) {
      fetchDocuments();
      fetchMetrics();
      fetchSources();
    }
  }, [clientId, page, pageSize, statusFilter, clients]);

  // Polling for processing documents
  useEffect(() => {
    const hasActiveDocs = documents.some(doc => doc.status === "PROCESSING" || doc.status === "UPLOADING");
    if (!hasActiveDocs) return;

    const interval = setInterval(() => {
      fetchDocuments();
      fetchMetrics();
    }, 5000);

    return () => clearInterval(interval);
  }, [documents]);

  // Load preview content
  useEffect(() => {
    if (viewingDoc) {
      loadPreviewContent(viewingDoc);
    } else {
      setViewingText(null);
      setStructuredPreview(null);
    }
  }, [viewingDoc]);

  const loadPreviewContent = async (doc: Document) => {
    const isPDF = doc.filename.toLowerCase().endsWith('.pdf');
    if (isPDF) return;

    setLoadingText(true);
    setViewingText(null);
    setStructuredPreview(null);

    try {
      // Check for structured preview first (CSV, XLSX)
      if (doc.filename.match(/\.(csv|xlsx)$/i)) {
          const res = await apiFetch(`/api/documents/${doc.id}/preview`);
          if (res.ok) {
              const data = await res.json();
              setStructuredPreview(data);
              setLoadingText(false);
              return;
          } else {
              // Silently fallback to raw view if structured fails
          }
      }

      // Fallback/Default for TXT and others
      const res = await apiFetch(`/api/documents/download/${doc.id}_${doc.filename}`);
      if (res.ok) {
        const text = await res.text();
        setViewingText(text.slice(0, 50000)); // Limit large files for browser performance
      }
    } catch (err) {
      console.error("Failed to load preview", err);
    } finally {
      setLoadingText(false);
    }
  };

  const fetchSources = () => {
    if (clientId && clients.length > 0) {
      const client = clients.find(c => c.id === clientId);
      if (client) {
        setSources({
          erp: client.source_erp ?? true,
          documents: client.source_documents ?? true,
          web: client.source_web ?? false
        });
      }
    }
  };

  const handleToggleSource = (key: keyof typeof sources) => {
    const updated = { ...sources, [key]: !sources[key] };
    setSources(updated);
    saveSources(updated);
  };

  const saveSources = async (data: typeof sources) => {
    if (!clientId) return;
    setSavingSources(true);
    setSourceSuccess(false);
    try {
      const res = await apiFetch(`/api/clients/${clientId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_erp: data.erp,
          source_documents: data.documents,
          source_web: data.web
        })
      });
      
      if (!res.ok) throw new Error("Failed to save sources");
      
      await refreshClients();
      toast.success("Knowledge sources updated successfully");
      setSourceSuccess(true);
      setTimeout(() => setSourceSuccess(false), 3000);
    } catch (err: any) {
      toast.error(`Update Failed: ${err.message}`);
    } finally {
      setSavingSources(false);
    }
  };

  const fetchDocuments = async () => {
    if (!clientId) return;
    try {
      const query = new URLSearchParams({
        client_id: clientId.toString(),
        page: page.toString(),
        page_size: pageSize.toString(),
        status: statusFilter
      });
      
      const res = await apiFetch(`/api/documents?${query}`);
      const data = await res.json();
      setDocuments(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error("DocumentsPage: Fetch failed", err);
      setError("Failed to fetch documents");
    } finally {
      setLoading(false);
    }
  };

  const fetchMetrics = async () => {
    if (!clientId) return;
    try {
      const res = await apiFetch(`/api/documents/metrics?client_id=${clientId}`);
      const data = await res.json();
      setMetrics(data);
    } catch (err) {
      console.error("Failed to fetch metrics", err);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !clientId) return;

    // Check size limit (local check)
    const MAX_SIZE = 50 * 1024 * 1024; // 50MB default
    if (file.size > MAX_SIZE) {
      toast.error("File exceeds 50MB limit");
      return;
    }

    setIsUploading(true);
    toast.info(`Uploading ${file.name}...`);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("client_id", clientId.toString());

      const res = await apiFetch("/api/documents/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Upload failed");
      }

      toast.success("Document uploaded and processing started");
      fetchDocuments();
      fetchMetrics();
    } catch (err: any) {
      toast.error(`Upload Error: ${err.message}`);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleRetry = async (documentId: number) => {
    try {
      const res = await apiFetch(`/api/documents/${documentId}/retry`, { method: "POST" });
      if (res.ok) {
        fetchDocuments();
        toast.info("Document reprocessing started");
      }
    } catch (err) {
      toast.error("Failed to trigger retry");
    }
  };

  const handleDelete = async () => {
    if (!deletingId && !isDeletingAll) return;
    
    try {
      if (isDeletingAll) {
        const res = await apiFetch(`/api/documents/all?client_id=${clientId}&force=true`, { method: "DELETE" });
        if (res.ok) {
          fetchDocuments();
          fetchMetrics();
          toast.success("Knowledge base cleared successfully");
        } else {
          const data = await res.json();
          toast.error(data.detail || "Failed to clear knowledge base");
        }
      } else {
        const res = await apiFetch(`/api/documents/${deletingId}?force=true`, { method: "DELETE" });
        if (res.ok) {
          fetchDocuments();
          fetchMetrics();
          toast.success("Document deleted successfully");
        } else {
          const data = await res.json();
          toast.error(data.detail || "Failed to delete document");
        }
      }
    } catch (err) {
      toast.error("Error performing deletion");
    } finally {
      setShowConfirm(false);
      setDeletingId(null);
      setIsDeletingAll(false);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const usagePercent = metrics ? (metrics.storage_used_mb / metrics.storage_limit_mb) * 100 : 0;

  if (!clientId) {
      return (
          <div className="flex flex-col items-center justify-center h-[50vh] text-center">
              <div className="bg-white p-8 rounded-2xl shadow-xl max-w-md border border-gray-100">
                  <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                      <Database size={32} />
                  </div>
                  <h2 className="text-2xl font-bold text-gray-800 mb-2">Knowledge Management</h2>
                  <p className="text-gray-500 mb-6">
                      Please select an active client from the header to manage their knowledge assets and sources.
                  </p>
              </div>
          </div>
      );
  }

  return (
    <div className="space-y-6">
      {/* Header & Combined Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-black text-slate-800 tracking-tight flex items-center gap-3">
              <Database size={28} className="text-blue-600" />
              Knowledge System
          </h1>
          <p className="text-sm text-gray-500 mt-1">Configure company data sources and manage internal document processing.</p>
        </div>
        </div>

      {/* DATA SOURCES CONTROL CENTER */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <SourceCard 
            label="ERP Knowledge" 
            description="Database & Systems" 
            isActive={sources.erp} 
            onChange={() => handleToggleSource('erp')} 
            icon={Database} 
            loading={savingSources}
          />
          <SourceCard 
            label="Document Library" 
            description="PDFs, CSVs, Docs" 
            isActive={sources.documents} 
            onChange={() => handleToggleSource('documents')} 
            icon={FileText} 
            loading={savingSources}
          />
          <SourceCard 
            label="Web Intelligence" 
            description="Enterprise Search" 
            isActive={sources.web} 
            onChange={() => handleToggleSource('web')} 
            icon={Globe} 
            disabled
          />
      </div>

      {/* Main Grid: Metrics & Document List */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar: Metrics */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-6">Environment Statistics</h3>
            
            <div className="space-y-8">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500 font-medium">Knowledge Assets</span>
                  <span className="text-sm font-bold text-gray-800">{metrics?.document_count || 0} / {metrics?.document_limit || 500}</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-blue-600 rounded-full transition-all duration-700"
                    style={{ width: `${(metrics?.document_count || 0) / (metrics?.document_limit || 500) * 100}%` }}
                  ></div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500 font-medium">Storage Capacity</span>
                  <span className="text-sm font-bold text-gray-800">{formatStorage(metrics?.storage_used_mb || 0)}</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div 
                    className={`h-full rounded-full transition-all duration-700 ${usagePercent > 80 ? 'bg-red-500' : 'bg-green-500'}`}
                    style={{ width: `${Math.min(usagePercent, 100)}%` }}
                  ></div>
                </div>
                <p className="text-[10px] text-gray-400 font-medium uppercase tracking-wider text-right">Limit: {formatStorage(metrics?.storage_limit_mb || 2048)}</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
             <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center mb-4">
                <Search size={20} />
             </div>
             <h4 className="font-bold text-lg mb-2 text-gray-800">Advanced Filters</h4>
             <div className="space-y-4 pt-2">
                <div className="space-y-1.5">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Processing Status</label>
                    <select 
                        value={statusFilter}
                        onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                        className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 transition-all font-medium text-gray-700"
                    >
                        <option value="">All Modules</option>
                        <option value="READY">Ready</option>
                        <option value="PROCESSING">Processing</option>
                        <option value="FAILED">Failed</option>
                    </select>
                </div>

                <div className="space-y-1.5">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Page Capacity</label>
                    <select 
                        value={pageSize}
                        onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                        className="w-full bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 transition-all font-medium text-gray-700"
                    >
                        <option value={10}>10 Entries</option>
                        <option value={25}>25 Entries</option>
                        <option value={50}>50 Entries</option>
                    </select>
                </div>
             </div>
          </div>
        </div>

        {/* Knowledge Library Table */}
        <div className="lg:col-span-3 space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-white">
              <h3 className="font-bold text-gray-800 flex items-center gap-2">
                <FileText size={18} className="text-blue-600" />
                Knowledge Library
                <span className="ml-2 px-2 py-0.5 bg-blue-50 text-blue-600 text-[10px] font-black rounded-full uppercase tracking-widest">{total} Total</span>
              </h3>
              
              <div className="flex items-center gap-3">
                <button 
                    onClick={() => { setIsDeletingAll(true); setShowConfirm(true); }}
                    disabled={documents.length === 0 || loading}
                    className="flex items-center gap-2 px-4 py-2 text-red-600 hover:bg-red-50 rounded-xl text-xs font-bold transition-all disabled:opacity-30"
                >
                    <Trash2 size={16} /> Wipe Cache
                </button>
                <input 
                    type="file" 
                    ref={fileInputRef} 
                    onChange={handleFileUpload} 
                    className="hidden" 
                    accept=".pdf,.docx,.txt,.csv,.xlsx"
                />
                <button 
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-xl text-xs font-bold hover:bg-blue-700 transition-all disabled:opacity-50 shadow-lg shadow-blue-100"
                >
                    {isUploading ? <RefreshCw className="animate-spin" size={16} /> : <Upload size={16} />}
                    Upload Knowledge
                </button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead className="bg-slate-50/50 text-slate-500 font-black uppercase tracking-widest text-[10px] border-b border-gray-100">
                  <tr>
                    <th className="px-6 py-4">Knowledge Asset</th>
                    <th className="px-6 py-4">Ingestion Status</th>
                    <th className="px-6 py-4">Resource Size</th>
                    <th className="px-6 py-4">Asset Timeline</th>
                    <th className="px-6 py-4 text-right">Control</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 border-b border-gray-100">
                  {loading ? (
                    <tr><td colSpan={5} className="px-6 py-12 text-center text-slate-400">Querying knowledge assets...</td></tr>
                  ) : documents.length === 0 ? (
                    <tr><td colSpan={5} className="px-6 py-16 text-center text-gray-400 font-medium">No assets currently indexed for this client.</td></tr>
                  ) : documents.map((doc) => (
                    <tr key={doc.id} className="hover:bg-blue-50/30 transition-colors group">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-4">
                          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shadow-sm border border-gray-100 ${doc.filename.endsWith('.pdf') ? 'bg-red-50 text-red-500' : 'bg-blue-50 text-blue-500'}`}>
                             {doc.filename.match(/\.(csv|xlsx)$/i) ? <FileSpreadsheet size={20}/> : <FileText size={20}/>}
                          </div>
                          <div className="min-w-0">
                            <p className="font-bold text-gray-800 text-sm leading-tight truncate mb-1">{doc.filename}</p>
                            <div className="flex items-center gap-3 text-[10px] uppercase font-black tracking-widest text-slate-400">
                               <span className="flex items-center gap-1">
                                  <Database size={10} /> ID-HEX: {doc.id.toString(16).toUpperCase()}
                               </span>
                               <span className="flex items-center gap-1 text-blue-500 font-bold">
                                 <FileText size={10} /> {doc.filename.split('.').pop()?.toUpperCase()}
                               </span>
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-widest flex items-center gap-1.5 w-fit shadow-sm border ${
                          doc.status === "READY" ? "bg-green-50 text-green-700 border-green-100" :
                          doc.status === "PROCESSING" || doc.status === "UPLOADING" ? "bg-amber-50 text-amber-700 border-amber-100 italic" :
                          "bg-red-50 text-red-700 border-red-100"
                        }`}>
                          {(doc.status === "PROCESSING" || doc.status === "UPLOADING") && <RefreshCw size={10} className="animate-spin text-amber-500" />}
                          {doc.status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                         <div className="space-y-1">
                            <p className="text-xs text-gray-600 font-bold">{formatStorage(doc.file_size / (1024 * 1024)) || formatSize(doc.file_size)}</p>
                            <p className="text-[10px] text-gray-400 font-medium">{doc.chunk_count} Semantic Chunks</p>
                         </div>
                      </td>
                      <td className="px-6 py-4 font-mono text-[10px] text-gray-400">
                        {new Date(doc.upload_time).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex justify-end gap-1.5">
                            <ControlButton 
                                label="Interactive Preview" 
                                icon={Eye} 
                                onClick={() => setViewingDoc(doc)} 
                                disabled={doc.status !== 'READY'}
                            />
                            <ControlButton 
                                label="Reprocess" 
                                icon={RefreshCw} 
                                onClick={() => handleRetry(doc.id)} 
                                disabled={doc.status !== "FAILED"}
                            />
                            <ControlButton 
                                label="Delete Asset" 
                                icon={Trash2} 
                                onClick={() => { setDeletingId(doc.id); setShowConfirm(true); }} 
                                danger
                            />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Component */}
            {total > pageSize && (
              <div className="p-4 border-t border-gray-100 bg-white flex items-center justify-between">
                <button 
                    onClick={() => setPage(p => Math.max(1, p - 1))} 
                    disabled={page === 1}
                    className="p-2 text-gray-400 hover:text-blue-600 disabled:opacity-20 transition-all"
                >
                    <ChevronLeft size={20}/>
                </button>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-black text-slate-300 uppercase tracking-widest">Vault Page</span>
                    <span className="w-8 h-8 flex items-center justify-center bg-slate-900 text-white rounded-lg text-xs font-bold shadow-lg">{page}</span>
                    <span className="text-[10px] font-black text-slate-300 uppercase tracking-widest">of {Math.ceil(total / pageSize)}</span>
                </div>
                <button 
                    onClick={() => setPage(p => p + 1)} 
                    disabled={page >= Math.ceil(total / pageSize)}
                    className="p-2 text-gray-400 hover:text-blue-600 disabled:opacity-20 transition-all"
                >
                    <ChevronRight size={20}/>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Confirmation Dialog */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 shadow-2xl max-w-sm w-full border border-gray-100">
            <div className="w-12 h-12 bg-red-100 text-red-600 rounded-full flex items-center justify-center mb-4">
              <AlertTriangle size={24} />
            </div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">
              {isDeletingAll ? "Wipe Knowledge Base?" : "Delete Document?"}
            </h3>
            <p className="text-gray-500 text-sm mb-6">
              {isDeletingAll 
                ? "Are you absolutely sure you want to delete ALL documents for this client? This will wipe the entire knowledge base and cannot be undone."
                : "Are you sure you want to delete this document? This will remove all associated vector chunks and cannot be undone."}
            </p>
            <div className="flex gap-3">
              <button 
                onClick={() => { setShowConfirm(false); setDeletingId(null); setIsDeletingAll(false); }}
                className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button 
                onClick={handleDelete}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 shadow-md uppercase tracking-wider font-bold"
              >
                {isDeletingAll ? "Wipe All" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3 text-red-800">
          <AlertCircle size={20} />
          <span>Failed to load documents</span>
        </div>
      )}

      {/* Universal Preview Modal */}
      {viewingDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200 shadow-2xl">
          <div className="bg-white rounded-2xl w-full max-w-5xl h-[90vh] flex flex-col shadow-2xl overflow-hidden border border-gray-100">
            <div className="p-4 border-b border-gray-100 flex items-center justify-between bg-white shrink-0">
               <div className="flex items-center gap-3">
                 <div className="p-2 bg-blue-50 text-blue-600 rounded-lg shadow-sm">
                   <FileText size={20} />
                 </div>
                 <div>
                   <h3 className="font-bold text-gray-900">{viewingDoc.filename}</h3>
                   <p className="text-[10px] text-gray-500 uppercase tracking-widest font-mono">
                     {viewingDoc.status} • {formatSize(viewingDoc.file_size)}
                   </p>
                 </div>
               </div>
               <div className="flex items-center gap-2">
                 <a 
                   href={`/api/documents/download/${viewingDoc.id}_${viewingDoc.filename}`}
                   download
                   className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-all"
                   title="Download Original"
                 >
                   <Upload className="rotate-180" size={18} />
                 </a>
                 <button 
                   onClick={() => setViewingDoc(null)} 
                   className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg transition-all"
                 >
                   <X size={20} />
                 </button>
               </div>
            </div>

            <div className="flex-1 bg-gray-50 overflow-hidden relative group">
              {viewingDoc.filename.toLowerCase().endsWith('.pdf') ? (
                <iframe 
                  src={`/api/documents/download/${viewingDoc.id}_${viewingDoc.filename}#toolbar=0`}
                  className="w-full h-full border-none"
                  title={viewingDoc.filename}
                />
              ) : loadingText ? (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-gray-500 bg-gray-50/50">
                  <RefreshCw className="w-10 h-10 animate-spin text-blue-500" />
                  <p className="text-sm font-medium animate-pulse">Analyzing document structure...</p>
                </div>
              ) : structuredPreview ? (
                <div className="w-full h-full overflow-auto bg-white">
                  <table className="min-w-full divide-y divide-gray-200 border-collapse table-auto">
                    <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                      <tr>
                        {structuredPreview.headers.map((h, i) => (
                          <th key={i} className="px-4 py-3 text-left text-[10px] font-black text-slate-500 uppercase tracking-widest border-b border-gray-100 whitespace-nowrap bg-gray-50">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-100">
                      {structuredPreview.rows.map((row, i) => (
                        <tr key={i} className="hover:bg-blue-50/30 transition-colors">
                          {structuredPreview.headers.map((h, j) => (
                            <td key={j} className="px-4 py-2.5 text-xs text-gray-600 border-r border-gray-50 last:border-r-0 max-w-[300px] truncate">
                              {String(row[h] !== null ? row[h] : '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {structuredPreview.rows.length === 50 && (
                    <div className="p-4 text-center bg-gray-50 text-[10px] font-bold text-gray-400 uppercase tracking-widest border-t border-gray-100">
                      Showing first 50 rows • Download full file for complete dataset
                    </div>
                  )}
                </div>
              ) : viewingText ? (
                <div className="w-full h-full overflow-auto p-8 font-mono text-xs leading-relaxed bg-slate-900 text-slate-300 scrollbar-thin">
                  <pre className="whitespace-pre-wrap">{viewingText}</pre>
                </div>
               ) : (
                <div className="p-12 flex flex-col items-center justify-center gap-6 max-w-lg mx-auto h-full text-center">
                  <div className="p-6 bg-orange-50 text-orange-500 rounded-full shadow-inner animate-in zoom-in duration-300">
                    <AlertCircle size={48} />
                  </div>
                  <div>
                    <h4 className="font-bold text-xl text-gray-900 mb-2">Rich Preview Unavailable</h4>
                    <p className="text-sm text-gray-500 leading-relaxed">
                      Rich previews for **DOCX** and **XLSX** files are currently processed into searchable knowledge. You can ask questions about this document in the chat, or download the original file to view it locally.
                    </p>
                  </div>
                  <a 
                    href={`/api/documents/download/${viewingDoc.id}_${viewingDoc.filename}`}
                    download
                    className="flex items-center gap-2 py-3 px-8 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-bold shadow-lg shadow-blue-200 transition-all hover:-translate-y-0.5 active:translate-y-0"
                  >
                    <Download size={18} /> Download to View
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
