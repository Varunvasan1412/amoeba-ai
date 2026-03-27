import { useState, useEffect } from "react";
import { useAdmin } from "../../context/AdminContext";
import { apiFetch } from "../../utils/api";
import { 
  FileText, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Database, 
  Zap,
  Maximize
} from "lucide-react";

interface Metrics {
  total_documents: number;
  documents_ready: number;
  documents_processing: number;
  documents_failed: number;
  total_chunks: number;
  average_ingestion_time_ms: number;
  largest_document_size_mb: number;
}

export default function DocumentMetricsCard() {
  const { clientId } = useAdmin();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (clientId) {
      fetchMetrics();
    }
  }, [clientId]);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`/api/system/documents/metrics?client_id=${clientId}`);
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (err) {
      console.error("Failed to fetch document metrics", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 animate-pulse h-full min-h-[200px]">
        <div className="h-4 bg-gray-100 rounded w-1/3 mb-4"></div>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <div className="h-12 bg-gray-50 rounded"></div>
          <div className="h-12 bg-gray-50 rounded"></div>
        </div>
      </div>
    );
  }

  if (!metrics) return null;

  const stats = [
    { label: "Total Documents", value: metrics.total_documents, icon: FileText, color: "blue" },
    { label: "Chunks Created", value: metrics.total_chunks, icon: Database, color: "emerald" },
    { label: "Avg. Ingestion", value: `${(metrics.average_ingestion_time_ms / 1000).toFixed(1)}s`, icon: Zap, color: "amber" },
    { label: "Largest File", value: `${metrics.largest_document_size_mb.toFixed(1)} MB`, icon: Maximize, color: "indigo" },
  ];

  return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 h-full hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-6">
        <h3 className="font-bold text-gray-800 flex items-center gap-2">
          <FileText size={18} className="text-blue-600" />
          Knowledge System Health
        </h3>
        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Real-time</span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        {stats.map((stat) => (
          <div key={stat.label} className="p-3 bg-gray-50 rounded-xl flex flex-col items-start gap-1">
            <div className={`w-7 h-7 bg-${stat.color}-100 text-${stat.color}-600 rounded-lg flex items-center justify-center mb-1`}>
              <stat.icon size={14} />
            </div>
            <span className="text-[10px] text-gray-500 font-medium">{stat.label}</span>
            <span className="text-lg font-bold text-gray-800">{stat.value}</span>
          </div>
        ))}
      </div>

      <div className="space-y-3 pt-4 border-t border-gray-50">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-gray-600">
            <CheckCircle2 size={14} className="text-green-500" />
            <span>Ready Documents</span>
          </div>
          <span className="font-bold text-gray-800">{metrics.documents_ready}</span>
        </div>
        
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-gray-600">
            <Clock size={14} className="text-yellow-500" />
            <span>Processing</span>
          </div>
          <span className="font-bold text-gray-800">{metrics.documents_processing}</span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 text-gray-600">
            <AlertCircle size={14} className="text-red-500" />
            <span>Failed Ingestions</span>
          </div>
          <span className="font-bold text-gray-800">{metrics.documents_failed}</span>
        </div>
      </div>
    </div>
  );
}
