
import { useState } from "react";
import { Copy, Check, Database, Server, Table, FileText, AlertTriangle } from "lucide-react";
import { apiFetch } from "../utils/api";

export default function LegacyOnboarding() {
  const [activeTab, setActiveTab] = useState(1);
  const [clientId, setClientId] = useState<number | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [tables, setTables] = useState<{name: string, columns: string[]}[]>([]);
  
  // Forms
  const [clientName, setClientName] = useState("");
  const [dbConfig, setDbConfig] = useState({
      db_type: "postgresql",
      host: "localhost",
      port: 5432,
      database: "",
      username: "",
      password: ""
  });
  const [reportConfig, setReportConfig] = useState({
      report_name: "",
      base_table: "",
      date_column: "",
      output_format: "xlsx"
  });

  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);

  // API Base
  const API_BASE = import.meta.env.DEV ? "http://localhost:8000/api" : "/api";

  const showMessage = (type: "success" | "error", text: string) => {
      setMessage({ type, text });
      setTimeout(() => setMessage(null), 5000);
  };

  // 1. Create Client
  const handleCreateClient = async () => {
      setLoading(true);
      try {
          const res = await apiFetch(`${API_BASE}/clients`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ client_name: clientName })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Failed");
          
          setClientId(data.data.client_id);
          setApiKey(data.data.api_key);
          showMessage("success", "Client Created Successfully!");
          setActiveTab(2); // Next Step
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setLoading(false);
      }
  };

  // 2. Connect DB
  const handleConnectDB = async () => {
      if (!clientId) return showMessage("error", "No Client Selected");
      setLoading(true);
      try {
          const res = await apiFetch(`${API_BASE}/clients/${clientId}/database`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(dbConfig)
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Connection Failed");
          
          showMessage("success", "Database Connected & Verified!");
          setActiveTab(3); // Next Step
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setLoading(false);
      }
  };

  // 3. Discover Tables
  const handleDiscoverTables = async () => {
      if (!clientId) return showMessage("error", "No Client Selected");
      setLoading(true);
      try {
          const res = await apiFetch(`${API_BASE}/clients/${clientId}/tables`);
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Discovery Failed");
          
          setTables(data.tables);
          showMessage("success", `Discovered ${data.tables.length} tables!`);
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setLoading(false);
      }
  };

  // 4. Register Report
  const handleRegisterReport = async () => {
      if (!clientId) return showMessage("error", "No Client Selected");
      setLoading(true);
      try {
          const payload = {
              client_id: clientId,
              ...reportConfig,
              date_column: reportConfig.date_column || null // Send null if empty
          };
          
          const res = await apiFetch(`${API_BASE}/reports`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload)
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Registration Failed");
          
          showMessage("success", `Report '${data.data.report_key}' registered!`);
          // Clear form
          setReportConfig(prev => ({...prev, report_name: "", base_table: "", date_column: ""}));
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setLoading(false);
      }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-8 font-sans text-gray-800 flex justify-center">
      <div className="w-full max-w-4xl bg-white shadow-xl rounded-2xl overflow-hidden flex flex-col border border-gray-200">
        {/* Header */}
        <div className="bg-slate-900 text-white p-6 flex justify-between items-center relative overflow-hidden">
            <div className="z-10">
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <span className="bg-white text-slate-900 px-2 py-0.5 rounded text-sm font-mono">v1</span>
                    Amoeba ACP Legacy
                </h1>
                <p className="text-slate-400 text-sm">Original Client Onboarding Panel</p>
            </div>
            {clientId && (
                <div className="bg-slate-800 px-3 py-1 rounded text-xs z-10">
                    Active Client ID: <span className="font-mono text-green-400">{clientId}</span>
                </div>
            )}
            {/* Retro grid background effect */}
            <div className="absolute inset-0 opacity-10" style={{backgroundImage: 'radial-gradient(circle, #fff 1px, transparent 1px)', backgroundSize: '20px 20px'}}></div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-100">
            {[
                { id: 1, label: "1. Create Client", icon: Server },
                { id: 2, label: "2. Database", icon: Database },
                { id: 3, label: "3. Discovery", icon: Table },
                { id: 4, label: "4. Reports", icon: FileText },
            ].map(tab => (
                <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex-1 p-4 flex items-center justify-center gap-2 text-sm font-medium transition-colors
                        ${activeTab === tab.id ? "text-blue-600 border-b-2 border-blue-600 bg-blue-50/50" : "text-gray-500 hover:bg-gray-50"}
                        ${(!clientId && tab.id > 1) ? "opacity-50 cursor-not-allowed" : ""}
                    `}
                    disabled={!clientId && tab.id > 1}
                >
                    <tab.icon size={16} />
                    {tab.label}
                </button>
            ))}
        </div>

        {/* Content */}
        <div className="p-8 flex-1 overflow-y-auto">
            
            {message && (
                <div className={`mb-6 p-4 rounded-lg flex items-center gap-3 ${message.type === "success" ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                    {message.type === "success" ? <Check size={20} /> : <AlertTriangle size={20} />}
                    {message.text}
                </div>
            )}

            {/* SCREEN 1: Create Client */}
            {activeTab === 1 && (
                <div className="max-w-md mx-auto flex flex-col gap-4">
                    <h2 className="text-xl font-semibold mb-2">Create New Client</h2>
                    
                    <div className="flex flex-col gap-1">
                        <label className="text-sm font-medium text-gray-600">Client Name</label>
                        <input 
                            className="border p-3 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                            placeholder="e.g. Acme Corp"
                            value={clientName}
                            onChange={e => setClientName(e.target.value)}
                        />
                    </div>

                    <button 
                        onClick={handleCreateClient}
                        disabled={loading || !clientName}
                        className="bg-blue-600 text-white p-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        {loading ? "Creating..." : "Create Client"}
                    </button>

                    {apiKey && (
                        <div className="mt-6 bg-yellow-50 border border-yellow-200 p-4 rounded-xl">
                            <h3 className="font-bold text-yellow-800 mb-2 flex items-center gap-2">
                                <AlertTriangle size={16}/> Save this Key!
                            </h3>
                            <div className="flex items-center gap-2 bg-white border border-yellow-200 p-2 rounded">
                                <code className="flex-1 font-mono text-sm overflow-hidden text-ellipsis">{apiKey}</code>
                                <button 
                                    onClick={() => navigator.clipboard.writeText(apiKey)}
                                    className="p-2 hover:bg-gray-100 rounded text-gray-500"
                                    title="Copy API Key"
                                >
                                    <Copy size={16} />
                                </button>
                            </div>
                            <p className="text-xs text-yellow-700 mt-2">
                                This key will <strong>not</strong> be shown again. Use it to configure the chat widget.
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* SCREEN 2: Database */}
            {activeTab === 2 && (
                <div className="max-w-lg mx-auto flex flex-col gap-4">
                     <h2 className="text-xl font-semibold mb-2">Connect ERP Database</h2>
                     
                     <div className="grid grid-cols-2 gap-4">
                         <div className="flex flex-col gap-1">
                            <label className="text-sm font-bold text-gray-600">DB Type</label>
                            <select 
                                className="border p-2.5 rounded-lg bg-white"
                                value={dbConfig.db_type}
                                onChange={e => setDbConfig({...dbConfig, db_type: e.target.value})}
                            >
                                <option value="postgresql">PostgreSQL</option>
                                <option value="mysql">MySQL</option>
                            </select>
                         </div>
                         <div className="flex flex-col gap-1">
                            <label className="text-sm font-bold text-gray-600">Port</label>
                            <input 
                                type="number"
                                className="border p-2.5 rounded-lg"
                                value={dbConfig.port}
                                onChange={e => setDbConfig({...dbConfig, port: parseInt(e.target.value)})}
                            />
                         </div>
                     </div>

                     <div className="flex flex-col gap-1">
                        <label className="text-sm font-bold text-gray-600">Host</label>
                        <input 
                            className="border p-2.5 rounded-lg"
                            placeholder="e.g. 10.0.0.5 or db.example.com"
                            value={dbConfig.host}
                            onChange={e => setDbConfig({...dbConfig, host: e.target.value})}
                        />
                     </div>

                     <div className="flex flex-col gap-1">
                        <label className="text-sm font-bold text-gray-600">Database Name</label>
                        <input 
                            className="border p-2.5 rounded-lg"
                            value={dbConfig.database}
                            onChange={e => setDbConfig({...dbConfig, database: e.target.value})}
                        />
                     </div>

                     <div className="grid grid-cols-2 gap-4">
                        <div className="flex flex-col gap-1">
                            <label className="text-sm font-bold text-gray-600">Username</label>
                            <input 
                                className="border p-2.5 rounded-lg"
                                value={dbConfig.username}
                                onChange={e => setDbConfig({...dbConfig, username: e.target.value})}
                            />
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-sm font-bold text-gray-600">Password</label>
                            <input 
                                type="password"
                                className="border p-2.5 rounded-lg"
                                value={dbConfig.password}
                                onChange={e => setDbConfig({...dbConfig, password: e.target.value})}
                            />
                        </div>
                     </div>

                     <button 
                        onClick={handleConnectDB}
                        disabled={loading}
                        className="bg-emerald-600 text-white p-3 rounded-lg font-medium hover:bg-emerald-700 disabled:opacity-50 mt-2 transition-colors"
                    >
                        {loading ? "Verifying..." : "Connect & Verify"}
                    </button>
                    
                    <p className="text-xs text-center text-gray-400 mt-2">
                        Credentials are encrypted at rest. Connection URL is never displayed.
                    </p>
                </div>
            )}

            {/* SCREEN 3: Discovery */}
            {activeTab === 3 && (
                <div className="flex flex-col h-full">
                     <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-semibold">Schema Discovery</h2>
                        <button 
                            onClick={handleDiscoverTables}
                            disabled={loading}
                            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
                        >
                            {loading ? "Scanning..." : "Scan Database"}
                        </button>
                     </div>

                     {tables.length === 0 ? (
                         <div className="flex-1 flex flex-col items-center justify-center text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
                             <Table size={48} className="mb-4 opacity-50"/>
                             <p>No tables discovered yet.</p>
                             <p className="text-sm">Click "Scan Database" to fetch schema.</p>
                         </div>
                     ) : (
                         <div className="grid grid-cols-1 md:grid-cols-2 gap-4 overflow-y-auto max-h-96">
                             {tables.map(t => (
                                 <div key={t.name} className="border p-4 rounded-xl bg-white hover:shadow-md transition-shadow">
                                     <div className="font-bold text-lg text-slate-700 mb-2 flex items-center gap-2">
                                         <Table size={16} className="text-blue-500"/>
                                         {t.name}
                                     </div>
                                     <div className="flex flex-wrap gap-1">
                                         {t.columns.map(c => (
                                             <span key={c} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                                                 {c}
                                             </span>
                                         ))}
                                     </div>
                                 </div>
                             ))}
                         </div>
                     )}
                </div>
            )}

            {/* SCREEN 4: Reports */}
            {activeTab === 4 && (
                <div className="max-w-lg mx-auto flex flex-col gap-4">
                     <h2 className="text-xl font-semibold mb-2">Register New Report</h2>
                     
                     <div className="bg-blue-50 p-4 rounded-lg flex items-start gap-3 mb-2">
                         <div className="mt-1"><FileText size={18} className="text-blue-600"/></div>
                         <div className="text-sm text-blue-800">
                             <strong>No-Code Registry:</strong> Just select a base table and optional date column. 
                             The system generates the optimized SQL automatically.
                         </div>
                     </div>

                     <div className="flex flex-col gap-1">
                        <label className="text-sm font-bold text-gray-600">Report Name</label>
                        <input 
                            className="border p-2.5 rounded-lg"
                            placeholder="e.g. Daily Sales"
                            value={reportConfig.report_name}
                            onChange={e => setReportConfig({...reportConfig, report_name: e.target.value})}
                        />
                     </div>

                     <div className="flex flex-col gap-1">
                        <label className="text-sm font-bold text-gray-600">Base Table</label>
                        <select 
                            className="border p-2.5 rounded-lg bg-white"
                            value={reportConfig.base_table}
                            onChange={e => setReportConfig({...reportConfig, base_table: e.target.value})}
                        >
                            <option value="">-- Select Table --</option>
                            {tables.map(t => (
                                <option key={t.name} value={t.name}>{t.name}</option>
                            ))}
                        </select>
                        {tables.length === 0 && <span className="text-xs text-red-500">Go to Discovery tab to fetch tables first.</span>}
                     </div>

                     <div className="flex flex-col gap-1">
                        <label className="text-sm font-bold text-gray-600">Date Column (Optional)</label>
                        <select 
                            className="border p-2.5 rounded-lg bg-white disabled:bg-gray-100"
                            value={reportConfig.date_column}
                            onChange={e => setReportConfig({...reportConfig, date_column: e.target.value})}
                            disabled={!reportConfig.base_table}
                        >
                            <option value="">-- None --</option>
                            {reportConfig.base_table && tables.find(t => t.name === reportConfig.base_table)?.columns.map(c => (
                                <option key={c} value={c}>{c}</option>
                            ))}
                        </select>
                        <span className="text-xs text-gray-400">Allows AI to filter report by date range (e.g. "last week").</span>
                     </div>

                     <div className="flex flex-col gap-1">
                        <label className="text-sm font-bold text-gray-600">Format</label>
                        <select 
                            className="border p-2.5 rounded-lg bg-white"
                            value={reportConfig.output_format}
                            onChange={e => setReportConfig({...reportConfig, output_format: e.target.value})}
                        >
                            <option value="xlsx">Excel (.xlsx)</option>
                            <option value="pdf">PDF</option>
                        </select>
                     </div>

                     <button 
                        onClick={handleRegisterReport}
                        disabled={loading || !reportConfig.report_name || !reportConfig.base_table}
                        className="bg-blue-600 text-white p-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 mt-2 transition-colors"
                    >
                        {loading ? "Registering..." : "Register Report"}
                    </button>
                </div>
            )}

        </div>
      </div>
    </div>
  );
}
