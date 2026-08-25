import { useState, useEffect } from "react";
import { useAdmin } from "../context/AdminContext";
import { FileText, Calendar, Loader2, Trash2, Pencil, LayoutTemplate } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../utils/api";
import { toast } from "react-toastify";

interface Report {
    id: number;
    display_name: string;
    report_key: string;
    created_at: string;
    sql_template: string;
    builder_definition: any; // Add this
}

export default function SavedReports() {
  const { clientId, apiKey } = useAdmin();
  const navigate = useNavigate();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  
  const API_BASE = import.meta.env.DEV ? "/api" : "/api";

  useEffect(() => {
    if (!clientId || !apiKey) return;
    const fetchReports = async () => {
        setLoading(true);
        try {
            // v2 uses ReportRegistry, which is compatible.
            // Using v2/builder/reports endpoint
            const res = await apiFetch(`/api/reports/saved?client_id=${clientId}`, {
                headers: { "X-API-Key": apiKey }
            });
            // Wait, SavedReports doesn't have apiKey in context? 
            // It uses useAdmin which might not have it.
            // Inspecting AdminContext...
            if (res.ok) {
                const data = await res.json();
                setReports(data.reports || []); 
                // Note: The response structure depends on v1 implementation.
                // Assuming standard { reports: [...] }
            }
        } catch (err) {
            console.error("Failed to fetch reports", err);
        } finally {
            setLoading(false);
        }
    };
    fetchReports();
  }, [clientId]);

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this report?")) return;
    
    try {
        const res = await apiFetch(`${API_BASE}/v2/builder/reports/${id}`, {
            method: "DELETE",
            headers: { "X-API-Key": apiKey! }
        });
        
        if (res.ok) {
            setReports(prev => prev.filter(r => r.id !== id));
        } else {
            toast.error("Failed to delete report");
        }
    } catch (err) {
        console.error("Delete failed", err);
        toast.error("Delete failed");
    }
  };

  const handleEdit = (report: Report) => {
      // Navigate to builder with state
      navigate("/admin/builder", { state: { report } });
  };

  const handleRunReport = async (reportId: number) => {
      setLoading(true);
      try {
          const res = await apiFetch(`${API_BASE}/v2/builder/reports/${reportId}/run`, {
              method: "POST",
              headers: { 
                  "X-API-Key": apiKey!,
                  "Content-Type": "application/json"
              },
              body: JSON.stringify({}) // Future expandability for dates
          });
          
          if (res.ok) {
              const data = await res.json();
              if (data.file_url) {
                  window.open(data.file_url, '_blank');
              } else {
                  toast.error("Failed to get file URL");
              }
          } else {
              const errData = await res.json();
              const errorMsg = typeof errData.detail === 'object' 
                ? JSON.stringify(errData.detail, null, 2) 
                : (errData.detail || "Failed to generate report");
              toast.error(errorMsg);
          }
      } catch (err) {
          console.error("Run report failed", err);
          toast.error("Internal server error");
      } finally {
          setLoading(false);
      }
  };

  if (!clientId) return <div className="p-8 text-center text-gray-500">Please select a client from the dashboard.</div>;

  return (
    <div>
        <div className="flex justify-between items-center mb-6">
            <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
                <FileText className="text-emerald-600"/> Saved Reports Library
            </h1>
            <button 
                onClick={() => navigate('/admin/builder')}
                className="bg-emerald-600 text-white px-5 py-2.5 rounded-xl text-sm font-bold shadow-sm shadow-emerald-200 hover:bg-emerald-700 transition flex items-center gap-2"
            >
                <LayoutTemplate size={18} /> Create New Report
            </button>
        </div>

        {loading ? (
             <div className="flex justify-center p-12"><Loader2 className="animate-spin text-emerald-600" size={32}/></div>
        ) : reports.length === 0 ? (
             <div className="bg-white p-12 rounded-xl text-center border border-gray-200">
                 <p className="text-gray-500 mb-4">No reports found.</p>
                 <p className="text-sm text-gray-400">Use the Visual Builder to create your first report.</p>
             </div>
        ) : (
            <div className="grid gap-4">
                {reports.map((report) => (
                    <div key={report.id} className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-md transition-shadow flex justify-between items-center group">
                        <div>
                            <h3 className="text-lg font-bold text-gray-800 mb-1">{report.display_name}</h3>
                            <div className="flex items-center gap-4 text-xs text-gray-500 font-mono">
                                <span className="bg-gray-100 px-2 py-1 rounded">KEY: {report.report_key}</span>
                                <span className="flex items-center gap-1"><Calendar size={12}/> {new Date(report.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                        
                        <div className="flex items-center gap-4">
                            <button 
                                className="text-gray-400 hover:text-blue-500 p-2 rounded-lg hover:bg-blue-50 transition-colors"
                                onClick={() => handleEdit(report)}
                                title="Edit Report"
                            >
                                <Pencil size={18}/>
                            </button>
                            <button 
                                className="text-gray-400 hover:text-red-500 p-2 rounded-lg hover:bg-red-50 transition-colors"
                                onClick={() => handleDelete(report.id)}
                                title="Delete Report"
                            >
                                <Trash2 size={18}/>
                            </button>
                            <button 
                                className="text-sm font-medium text-emerald-600 hover:text-emerald-700 px-4 py-2 bg-emerald-50 rounded-lg hover:bg-emerald-100 transition-colors disabled:opacity-50"
                                onClick={() => handleRunReport(report.id)}
                                disabled={loading}
                            >
                                Run Report
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        )}
    </div>
  );
}
