import { useState, useEffect } from "react";
import { 
  ArrowLeft, Shield, CheckCircle, AlertTriangle, 
  RefreshCw, Zap, Wand2, Unlock, ShieldCheck, Check, X
} from "lucide-react";
import { Link } from "react-router-dom";
import { useAdmin } from "../context/AdminContext";
import { apiFetch } from "../utils/api";
import { JoinExplorer } from "../components/admin/JoinExplorer";

export default function RelationshipGovernance() {
  const { apiKey } = useAdmin();
  const [loading, setLoading] = useState(false);
  const [magicLoading, setMagicLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);
  const [allRels, setAllRels] = useState<any[]>([]);
  const [fullSchema, setFullSchema] = useState<any[]>([]);
  const [activeRelForPayload, setActiveRelForPayload] = useState<any | null>(null);

  const fetchData = async () => {
    if (!apiKey) return;
    setLoading(true);
    try {
      const API_BASE = import.meta.env.VITE_API_URL || "";
      const url = `${API_BASE}/api/v2/relationships`.replace(/\/\//g, '/').replace(':/', '://');
      const res = await apiFetch(url, { headers: { "X-API-Key": apiKey } });
      const data = await res.json();
      if (Array.isArray(data)) {
          setAllRels(data);
          const schemaRes = await apiFetch(`${API_BASE}/api/v2/semantic/schema`.replace(/\/\//g, '/').replace(':/', '://'), { headers: { "X-API-Key": apiKey } });
          const sData = await schemaRes.json();
          setFullSchema(sData);
      }
    } catch (err) {
      console.error(err);
      showMessage("error", "Failed to load data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [apiKey]);

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
              fetchData();
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
      </div>

      {/* Relationship Discovery Engine */}
      <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
              <Wand2 size={18} className="text-blue-500" />
              <h2 className="text-lg font-bold text-gray-700">Discovery Engine</h2>
              <div className="h-[1px] flex-1 bg-gray-100 ml-2"></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <button 
                onClick={() => handleMagicAction("auto_unlock_safe")}
                disabled={!!magicLoading}
                className="group relative bg-white p-6 rounded-3xl border border-gray-100 hover:border-emerald-200 transition-all text-left shadow-sm hover:shadow-xl overflow-hidden"
              >
                  {magicLoading === "auto_unlock_safe" && <div className="absolute inset-0 bg-emerald-50/80 backdrop-blur-sm z-10 flex items-center justify-center"><RefreshCw className="animate-spin text-emerald-600" /></div>}
                  <div className="flex items-center gap-3 mb-3">
                      <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-2xl group-hover:scale-110 transition-transform">
                          <ShieldCheck size={22} />
                      </div>
                      <span className="font-black text-[10px] uppercase tracking-widest text-emerald-600/70">Safe Mode</span>
                  </div>
                  <h3 className="font-bold text-gray-800">Auto-Unlock FKs</h3>
                  <p className="text-xs text-gray-500 mt-2 leading-relaxed">Enable all official Foreign Keys defined in your database schema.</p>
              </button>

              <button 
                onClick={() => handleMagicAction("auto_unlock_heuristics")}
                disabled={!!magicLoading}
                className="group relative bg-white p-6 rounded-3xl border border-gray-100 hover:border-indigo-200 transition-all text-left shadow-sm hover:shadow-xl overflow-hidden"
              >
                  {magicLoading === "auto_unlock_heuristics" && <div className="absolute inset-0 bg-indigo-50/80 backdrop-blur-sm z-10 flex items-center justify-center"><RefreshCw className="animate-spin text-indigo-600" /></div>}
                  <div className="flex items-center gap-3 mb-3">
                      <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-2xl group-hover:scale-110 transition-transform">
                          <Zap size={22} />
                      </div>
                      <span className="font-black text-[10px] uppercase tracking-widest text-indigo-600/70">AI Enhanced</span>
                  </div>
                  <h3 className="font-bold text-gray-800">Apply Heuristics</h3>
                  <p className="text-xs text-gray-500 mt-2 leading-relaxed">AI-powered discovery matching columns by name (e.g. customer_id).</p>
              </button>

              <button 
                onClick={() => handleMagicAction("enable_all")}
                disabled={!!magicLoading}
                className="group relative bg-white p-6 rounded-3xl border border-gray-100 hover:border-blue-200 transition-all text-left shadow-sm hover:shadow-xl overflow-hidden"
              >
                  {magicLoading === "enable_all" && <div className="absolute inset-0 bg-blue-50/80 backdrop-blur-sm z-10 flex items-center justify-center"><RefreshCw className="animate-spin text-blue-600" /></div>}
                  <div className="flex items-center gap-3 mb-3">
                      <div className="p-2.5 bg-blue-50 text-blue-600 rounded-2xl group-hover:scale-110 transition-transform">
                          <Unlock size={22} />
                      </div>
                      <span className="font-black text-[10px] uppercase tracking-widest text-blue-600/70">Maximum Access</span>
                  </div>
                  <h3 className="font-bold text-gray-800">Trust Everything</h3>
                  <p className="text-xs text-gray-500 mt-2 leading-relaxed">Enable every possible connection for maximum conversational flexibility.</p>
              </button>
          </div>
      </div>

      {/* Maintenance & Safety */}
      <div className="mb-8 p-6 bg-slate-50/50 rounded-[32px] border border-slate-100">
          <div className="flex items-center gap-2 mb-4">
              <Shield size={18} className="text-slate-400" />
              <h2 className="text-sm font-bold text-slate-500 uppercase tracking-widest">Maintenance & Safety</h2>
          </div>
          <div className="flex flex-wrap gap-4">
              <button 
                onClick={() => {
                    if (confirm("FACTORY RESET: This will disable ALL joins and reset everything to AI discovery. Are you sure?")) {
                        handleMagicAction("disable_all");
                    }
                }}
                disabled={!!magicLoading}
                className="flex items-center gap-3 bg-white px-5 py-3 rounded-2xl border border-gray-200 hover:border-orange-300 hover:bg-orange-50/30 transition-all text-gray-700 group shadow-sm"
              >
                  <RefreshCw size={18} className={`text-orange-500 ${magicLoading === 'disable_all' ? 'animate-spin' : 'group-hover:rotate-180 transition-transform duration-500'}`} />
                  <div className="text-left">
                      <p className="text-sm font-bold">Factory Reset</p>
                      <p className="text-[10px] text-gray-400">Disable all current rules</p>
                  </div>
              </button>

              <button 
                onClick={() => {
                    if (confirm("PURGE ALL: This will permanently DELETE every connection for this client. This cannot be undone. Are you sure?")) {
                        handleMagicAction("purge_all");
                    }
                }}
                disabled={!!magicLoading}
                className="flex items-center gap-3 bg-white px-5 py-3 rounded-2xl border border-gray-200 hover:border-rose-300 hover:bg-rose-50/30 transition-all text-gray-700 group shadow-sm"
              >
                  <X size={18} className={`text-rose-500 ${magicLoading === 'purge_all' ? 'animate-spin' : 'group-hover:scale-125 transition-transform'}`} />
                  <div className="text-left">
                      <p className="text-sm font-bold">Purge All Connections</p>
                      <p className="text-[10px] text-gray-400">Permanently erase from DB</p>
                  </div>
              </button>

              <button 
                onClick={() => fetchData()}
                className="ml-auto flex items-center gap-2 px-5 py-3 rounded-2xl bg-slate-800 text-white hover:bg-slate-700 transition-all text-sm font-bold shadow-lg shadow-slate-200"
              >
                  <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                  Refresh View
              </button>
          </div>
      </div>

      {message && (
          <div className={`mb-6 p-4 rounded-2xl flex items-center gap-3 animate-in slide-in-from-top-4 ${message.type === "success" ? "bg-green-50 text-green-700 border border-green-100" : "bg-red-50 text-test-700 border border-red-100"}`}>
              {message.type === "success" ? <CheckCircle size={18}/> : <AlertTriangle size={18}/>}
              <span className="text-sm font-bold">{message.text}</span>
          </div>
      )}

      {/* Main View Area */}
      <div className="bg-white rounded-[40px] shadow-2xl border border-gray-100 relative min-h-[700px]">
          {loading ? (
              <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-20">
                  <Wand2 className="animate-bounce text-blue-600" size={48} />
              </div>
          ) : (
              <JoinExplorer 
                rels={allRels} 
                schemaData={fullSchema}
                apiKey={apiKey}
                onOpenPayload={(rel) => setActiveRelForPayload(rel)}
                onRefresh={fetchData}
              />
          )}
      </div>

      {/* Reusable Payload Modal for Explorer */}
      {activeRelForPayload && (
          <div className="fixed inset-0 z-[110] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6">
              <div className="bg-white w-full max-w-md rounded-3xl shadow-2xl overflow-hidden border border-slate-100 flex flex-col max-h-[80vh]">
                  <div className="p-6 border-b border-slate-50 flex justify-between items-center">
                      <div>
                          <h3 className="text-lg font-bold text-slate-800">Select Data Payload</h3>
                          <p className="text-xs text-slate-400">Choose which columns to pull from <span className="font-mono text-blue-600 bg-blue-50 px-1 rounded">{activeRelForPayload.child_table}</span></p>
                      </div>
                      <button onClick={() => setActiveRelForPayload(null)} className="p-2 hover:bg-slate-50 rounded-xl text-slate-400"><X size={20} /></button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto p-6 space-y-2 bg-slate-50/30">
                      {fullSchema.filter(s => s.table_name === activeRelForPayload.child_table).map(s => s.column_name).map(col => {
                          const isSelected = activeRelForPayload.selected_columns?.includes(col);
                          return (
                            <button 
                                key={col} 
                                onClick={() => {
                                    const next = isSelected 
                                        ? activeRelForPayload.selected_columns.filter((c: any) => c !== col)
                                        : [...(activeRelForPayload.selected_columns || []), col];
                                    setActiveRelForPayload({...activeRelForPayload, selected_columns: next});
                                }}
                                className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all ${isSelected ? 'bg-blue-50 border-blue-200 text-blue-700 shadow-sm' : 'bg-white border-slate-100 text-slate-600 hover:border-slate-200'}`}
                            >
                                <span className="text-sm font-semibold">{col}</span>
                                {isSelected && <Check size={16} className="text-blue-600" />}
                            </button>
                          );
                      })}
                  </div>

                  <div className="p-6 border-t border-slate-50 flex gap-3">
                      <button 
                        onClick={async () => {
                            const API_BASE = import.meta.env.VITE_API_URL || "";
                            await apiFetch(`${API_BASE}/api/v2/relationships/${activeRelForPayload.id}/columns`.replace(/\/\//g, '/').replace(':/', '://'), {
                                method: "POST",
                                headers: { "Content-Type": "application/json", "X-API-Key": apiKey || "" },
                                body: JSON.stringify({ columns: activeRelForPayload.selected_columns })
                            });
                            setAllRels(prev => prev.map(r => r.id === activeRelForPayload.id ? activeRelForPayload : r));
                            setActiveRelForPayload(null);
                            showMessage("success", "Payload updated!");
                        }}
                        className="flex-1 bg-blue-600 text-white py-3 rounded-2xl font-bold text-sm hover:bg-blue-700 transition-all shadow-lg shadow-blue-100"
                      >
                          Apply Column Selection
                      </button>
                  </div>
              </div>
          </div>
      )}
    </div>
  );
}
