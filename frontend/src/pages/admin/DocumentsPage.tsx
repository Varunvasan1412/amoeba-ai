import { useState, useEffect } from "react";
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
  AlertTriangle
} from "lucide-react";

interface Document {
  id: number;
  filename: string;
  status: "READY" | "PROCESSING" | "FAILED";
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

  // Deletion state
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [isDeletingAll, setIsDeletingAll] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    if (clientId) {
      fetchDocuments();
      fetchMetrics();
    }
  }, [clientId, page, pageSize, statusFilter]);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams({
        client_id: String(clientId),
        page: String(page),
        page_size: String(pageSize),
        ...(statusFilter && { status: statusFilter })
      });
      const res = await apiFetch(`/api/documents?${query}`);
      if (!res.ok) throw new Error("Failed to load documents");
      const data = await res.json();
      setDocuments(data.items || []);
      setTotal(data.total || 0);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchMetrics = async () => {
    try {
      const res = await apiFetch(`/api/system/documents/metrics?client_id=${clientId}`);
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error("Failed to fetch metrics", err);
    }
  };

  const handleRetry = async (documentId: number) => {
    try {
      const res = await apiFetch(`/api/documents/${documentId}/retry`, { method: "POST" });
      if (res.ok) {
        fetchDocuments();
        // Toast logic would go here
        alert("Document reprocessing started");
      }
    } catch (err) {
      alert("Failed to trigger retry");
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
          alert("Knowledge base cleared successfully");
        } else {
          const data = await res.json();
          alert(data.detail || "Failed to clear knowledge base");
        }
      } else {
        const res = await apiFetch(`/api/documents/${deletingId}?force=true`, { method: "DELETE" });
        if (res.ok) {
          fetchDocuments();
          fetchMetrics();
          alert("Document deleted successfully");
        } else {
          const data = await res.json();
          alert(data.detail || "Failed to delete document");
        }
      }
    } catch (err) {
      alert("Error performing deletion");
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

  return (
    <div className="space-y-6">
      {/* Header & Usage */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-gray-800">Document Management</h1>
          <p className="text-sm text-gray-500">Manage and monitor your knowledge base documents.</p>
        </div>

        <div className="flex items-center gap-3">
          <button 
            onClick={() => { setIsDeletingAll(true); setShowConfirm(true); }}
            disabled={documents.length === 0 || loading}
            className="flex items-center gap-2 px-4 py-2 bg-red-50 text-red-600 border border-red-100 rounded-xl text-sm font-bold hover:bg-red-100 transition-all disabled:opacity-30"
          >
            <Trash2 size={16} /> Empty Knowledge Base
          </button>
          
          <div className="h-10 w-px bg-gray-100 mx-1 hidden md:block"></div>
        </div>

        {metrics && (
          <div className="w-full md:w-64 space-y-2">
            <div className="flex justify-between text-xs font-medium">
              <span className="text-gray-500">Storage Usage</span>
              <span className={usagePercent > 80 ? "text-red-600 font-bold" : "text-gray-700"}>
                {(metrics.storage_used_mb / 1024).toFixed(1)} GB / {(metrics.storage_limit_mb / 1024).toFixed(1)} GB
              </span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all duration-500 ${usagePercent > 80 ? "bg-red-500" : "bg-blue-500"}`}
                style={{ width: `${Math.min(usagePercent, 100)}%` }}
              ></div>
            </div>
            {usagePercent > 80 && (
              <p className="text-[10px] text-red-500 font-bold flex items-center gap-1 animate-pulse">
                <AlertTriangle size={10} /> Storage usage approaching limit
              </p>
            )}
          </div>
        )}
      </div>

      {/* Filters & Table */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="p-4 border-b border-gray-100 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
              <select 
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                className="pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none appearance-none min-w-[140px]"
              >
                <option value="">All Statuses</option>
                <option value="READY">Ready</option>
                <option value="PROCESSING">Processing</option>
                <option value="FAILED">Failed</option>
              </select>
            </div>
            
            <select 
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm outline-none"
            >
              <option value={10}>10 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
            </select>
          </div>

          <div className="text-sm text-gray-500">
            Total: <span className="font-bold text-gray-800">{total}</span> documents
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-600 font-medium border-b border-gray-100">
              <tr>
                <th className="px-6 py-4">Filename</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Size</th>
                <th className="px-6 py-4">Chunks</th>
                <th className="px-6 py-4">Uploaded</th>
                <th className="px-6 py-4">Processing Time</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-400">
                    <div className="flex flex-col items-center gap-2">
                      <RefreshCw className="animate-spin text-blue-500" size={24} />
                      <span>Loading documents...</span>
                    </div>
                  </td>
                </tr>
              ) : documents.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-400 text-lg">
                    No documents uploaded yet
                  </td>
                </tr>
              ) : documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-4 font-medium text-gray-900 flex items-center gap-2">
                    <FileText size={16} className="text-gray-400" />
                    {doc.filename}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                      doc.status === "READY" ? "bg-green-100 text-green-700" :
                      doc.status === "PROCESSING" ? "bg-yellow-100 text-yellow-700" :
                      "bg-red-100 text-red-700"
                    }`}>
                      {doc.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-gray-500">{formatSize(doc.file_size)}</td>
                  <td className="px-6 py-4 text-gray-500">{doc.chunk_count}</td>
                  <td className="px-6 py-4 text-gray-500">
                    {new Date(doc.upload_time).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-gray-500">
                    {doc.processing_time_ms ? `${(doc.processing_time_ms / 1000).toFixed(1)}s` : "-"}
                  </td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button 
                      onClick={() => handleRetry(doc.id)}
                      disabled={doc.status !== "FAILED"}
                      className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                      title="Retry Ingestion"
                    >
                      <RefreshCw size={16} />
                    </button>
                    <button 
                      onClick={() => { setDeletingId(doc.id); setShowConfirm(true); }}
                      disabled={doc.status === "PROCESSING"}
                      className="p-2 text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                      title="Delete Document"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > pageSize && (
          <div className="p-4 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
            <button 
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex items-center gap-1 text-sm font-medium text-gray-600 hover:text-blue-600 disabled:opacity-30"
            >
              <ChevronLeft size={16} /> Previous
            </button>
            <span className="text-sm text-gray-500">
              Page <span className="font-bold text-gray-800">{page}</span> of {Math.ceil(total / pageSize)}
            </span>
            <button 
              onClick={() => setPage(p => p + 1)}
              disabled={page >= Math.ceil(total / pageSize)}
              className="flex items-center gap-1 text-sm font-medium text-gray-600 hover:text-blue-600 disabled:opacity-30"
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        )}
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
    </div>
  );
}
