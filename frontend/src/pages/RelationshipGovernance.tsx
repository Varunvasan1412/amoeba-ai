import { useState, useEffect } from "react";
import { 
  ArrowLeft, Shield, CheckCircle, XCircle, AlertTriangle, 
  RefreshCw, Lock, Zap, BarChart, HardDrive, LayoutGrid, 
  List as ListIcon, Wand2, Unlock, ShieldCheck, Ghost
} from "lucide-react";
import { Link } from "react-router-dom";
import { useAdmin } from "../context/AdminContext";
import { apiFetch } from "../utils/api";
import RelationshipGraph from "./admin/RelationshipGraph";
import { RelationshipList } from "../components/admin/RelationshipList";

export default function RelationshipGovernance() {
  const { apiKey } = useAdmin();
  const [loading, setLoading] = useState(false);
  const [magicLoading, setMagicLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);
  const [viewMode, setViewViewMode] = useState<"graph" | "list">("graph");

  const showMessage = (type: "success" | "error", text: string) => {
      setMessage({ type, text });
      setTimeout(() => setMessage(null), 5000);
  };

  const handleMagicAction = async (action: string) => {
      if (!apiKey) return showMessage("error", "No API Key found. Select a client first.");
      setMagicLoading(action);
      try {
          const API_BASE = import.meta.env.VITE_API_URL || "";
          const url = `${API_BASE}/api/v2/relationships/bulk-update`.replace(/\/\//g, '/').replace(':/', '://');
          
          const res = await apiFetch(url, {
              method: "POST",
              headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
              body: JSON.stringify({ action })
          });
          const data = await res.json();
          if (res.ok) {
              showMessage("success", `Magic Complete! Updated ${data.updated_count} connections.`);
              setLoading(true);
              setTimeout(() => setLoading(false), 100);
          }
      } catch (err) {
          showMessage("error", "Magic failed. Try manual mode.");
      } finally {
          setMagicLoading(null);
      }
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-4">
      {/* Header */}
      <div className="flex justify-between items-center mb-8 bg-white p-6 rounded-3xl border border-gray-100 shadow-sm">
        <div className="flex items-center gap-4">
          <Link to="/admin" className="p-2 hover:bg-gray-100 rounded-xl transition-colors">
            <ArrowLeft size={20} className="text-gray-500" />
          </Link>
          <div>
            <h1 className="text-2xl font-black text-gray-800 flex items-center gap-2">
              <Shield className="text-blue-600" /> Data Connections
            </h1>
            <p className="text-sm text-gray-500 font-medium tracking-tight">Decide which tables are allowed to talk to each other.</p>
          </div>
        </div>

        <div className="flex bg-gray-100 p-1 rounded-2xl">
            <button 
                onClick={() => setViewViewMode("graph")}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${viewMode === "graph" ? "bg-white text-blue-600 shadow-sm" : "text-gray-500"}`}
            >
                <LayoutGrid size={14} /> Mindmap
            </button>
            <button 
                onClick={() => setViewViewMode("list")}
                className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${viewMode === "list" ? "bg-white text-blue-600 shadow-sm" : "text-gray-500"}`}
            >
                <ListIcon size={14} /> Detail List
            </button>
        </div>
      </div>

      {/* Magic Action Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <button 
            onClick={() => handleMagicAction("auto_unlock_safe")}
            disabled={!!magicLoading}
            className="group relative bg-white p-5 rounded-3xl border-2 border-green-50 hover:border-green-200 transition-all text-left shadow-sm hover:shadow-xl overflow-hidden"
          >
              {magicLoading === "auto_unlock_safe" && <div className="absolute inset-0 bg-green-50/80 backdrop-blur-sm z-10 flex items-center justify-center"><RefreshCw className="animate-spin text-green-600" /></div>}
              <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 bg-green-100 text-green-600 rounded-xl group-hover:scale-110 transition-transform">
                      <ShieldCheck size={20} />
                  </div>
                  <span className="font-black text-xs uppercase tracking-widest text-green-700">Level 1</span>
              </div>
              <h3 className="font-bold text-gray-800 text-sm">Auto-Unlock Safe FKs</h3>
              <p className="text-[10px] text-gray-500 mt-1">Enable all standard Foreign Keys detected in your database.</p>
          </button>

          <button 
            onClick={() => handleMagicAction("auto_unlock_heuristics")}
            disabled={!!magicLoading}
            className="group relative bg-white p-5 rounded-3xl border-2 border-purple-50 hover:border-purple-200 transition-all text-left shadow-sm hover:shadow-xl overflow-hidden"
          >
              {magicLoading === "auto_unlock_heuristics" && <div className="absolute inset-0 bg-purple-50/80 backdrop-blur-sm z-10 flex items-center justify-center"><RefreshCw className="animate-spin text-purple-600" /></div>}
              <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 bg-purple-100 text-purple-600 rounded-xl group-hover:scale-110 transition-transform">
                      <Zap size={20} />
                  </div>
                  <span className="font-black text-xs uppercase tracking-widest text-purple-700">Level 2</span>
              </div>
              <h3 className="font-bold text-gray-800 text-sm">Apply AI Heuristics</h3>
              <p className="text-[10px] text-gray-500 mt-1">Connect tables by matching IDs and names (e.g. customer_id).</p>
          </button>

          <button 
            onClick={() => handleMagicAction("enable_all")}
            disabled={!!magicLoading}
            className="group relative bg-white p-5 rounded-3xl border-2 border-blue-50 hover:border-blue-200 transition-all text-left shadow-sm hover:shadow-xl overflow-hidden"
          >
              {magicLoading === "enable_all" && <div className="absolute inset-0 bg-blue-50/80 backdrop-blur-sm z-10 flex items-center justify-center"><RefreshCw className="animate-spin text-blue-600" /></div>}
              <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 bg-blue-100 text-blue-600 rounded-xl group-hover:scale-110 transition-transform">
                      <Unlock size={20} />
                  </div>
                  <span className="font-black text-xs uppercase tracking-widest text-blue-700">Simple Mode</span>
              </div>
              <h3 className="font-bold text-gray-800 text-sm">Trust Everything</h3>
              <p className="text-[10px] text-gray-500 mt-1">Enable every possible connection for maximum flexibility.</p>
          </button>

          <button 
            onClick={() => {
                if (confirm("FACTORY RESET: This will delete ALL manual joins and reset everything to AI discovery. Are you sure?")) {
                    handleMagicAction("disable_all");
                }
            }}
            disabled={!!magicLoading}
            className="group relative bg-white p-5 rounded-3xl border-2 border-red-50 hover:border-red-200 transition-all text-left shadow-sm hover:shadow-xl overflow-hidden"
          >
              {magicLoading === "disable_all" && <div className="absolute inset-0 bg-red-50/80 backdrop-blur-sm z-10 flex items-center justify-center"><RefreshCw className="animate-spin text-red-600" /></div>}
              <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 bg-red-100 text-red-600 rounded-xl group-hover:scale-110 transition-transform">
                      <RefreshCw size={20} />
                  </div>
                  <span className="font-black text-xs uppercase tracking-widest text-red-700">Danger Zone</span>
              </div>
              <h3 className="font-bold text-gray-800 text-sm">Factory Reset</h3>
              <p className="text-[10px] text-gray-500 mt-1">Wipe all custom rules and re-run discovery from scratch.</p>
          </button>
      </div>

      {message && (
          <div className={`mb-6 p-4 rounded-2xl flex items-center gap-3 animate-in slide-in-from-top-4 ${message.type === "success" ? "bg-green-50 text-green-700 border border-green-100" : "bg-red-50 text-red-700 border border-red-100"}`}>
              {message.type === "success" ? <CheckCircle size={18}/> : <AlertTriangle size={18}/>}
              <span className="text-sm font-bold">{message.text}</span>
          </div>
      )}

      {/* Main View Area */}
      <div className="bg-white rounded-[40px] shadow-2xl border border-gray-100 overflow-hidden relative min-h-[700px]">
          {loading ? (
              <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-20">
                  <Wand2 className="animate-bounce text-blue-600" size={48} />
              </div>
          ) : viewMode === "graph" ? (
              <RelationshipGraph apiKey={apiKey} />
          ) : (
              <RelationshipList apiKey={apiKey} />
          )}
      </div>
    </div>
  );
}
