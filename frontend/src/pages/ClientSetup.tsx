
import { useState } from "react";
import { Server, Database, Table, Check, AlertTriangle, Copy, ArrowRight } from "lucide-react";
import { useAdmin } from "../context/AdminContext";
import { apiFetch } from "../utils/api";

export default function ClientSetup() {
  const { clientId, setClientId, setApiKey, setClientName } = useAdmin();
  const [activeTab, setActiveTab] = useState(1);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);

  // Form State
  const [newClientName, setNewClientName] = useState("");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  
  const [dbConfig, setDbConfig] = useState({
      db_type: "postgresql",
      host: "localhost",
      port: 5432,
      database: "",
      username: "",
      password: ""
  });

  const [discoveredTables, setDiscoveredTables] = useState<string[]>([]);

  const API_BASE = import.meta.env.DEV ? "/api" : "/api";

  const showMessage = (type: "success" | "error", text: string) => {
      setMessage({ type, text });
      setTimeout(() => setMessage(null), 5000);
  };

  // 1. Create Client
  const handleCreateClient = async () => {
      setLoading(true);
      try {
          const res = await fetch('/api/clients/setup', {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ client_name: newClientName })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Failed to create client");
          
          // Update Global Context
          setClientId(data.data.client_id);
          setApiKey(data.data.api_key);
          setClientName(newClientName);
          
          setGeneratedKey(data.data.api_key);
          showMessage("success", `Client '${newClientName}' created successfully!`);
          // setActiveTab(2); // Manual advance now
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setLoading(false);
      }
  };

  // 2. Connect Database
  const handleConnectDB = async () => {
      if (!clientId) return showMessage("error", "No Client Selected. Create one first.");
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
          setActiveTab(3); // Move to Discovery
          handleDiscoverTables(clientId); // Auto-scan
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setLoading(false);
      }
  };

  // 3. Discover (Verification)
  const handleDiscoverTables = async (id: number = clientId!) => {
      if (!id) return;
      setLoading(true);
      try {
          const res = await apiFetch(`${API_BASE}/clients/${id}/tables`);
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Discovery Failed");
          
          const names = data.tables.map((t: any) => t.name);
          setDiscoveredTables(names);
          showMessage("success", `Discovered ${names.length} tables from ERP.`);
      } catch (err: any) {
          console.error(err); 
          // Don't show error on auto-scan to avoid annoyance, unless manual?
          if (activeTab === 3) showMessage("error", "Failed to scan tables.");
      } finally {
          setLoading(false);
      }
  };

  return (
    <div className="max-w-4xl mx-auto">
        <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-800">Client Setup</h1>
            <p className="text-gray-500">Onboard new clients and configure their database connections.</p>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center mb-8">
            {[
                { id: 1, label: "Create Client", icon: Server },
                { id: 2, label: "Connect Database", icon: Database },
                { id: 3, label: "Verify Connection", icon: Table },
            ].map((step, idx) => (
                <div key={step.id} className="flex items-center">
                    <div className={`flex items-center gap-2 px-4 py-2 rounded-full border ${activeTab === step.id ? "bg-blue-50 border-blue-200 text-blue-700" : activeTab > step.id ? "bg-green-50 border-green-200 text-green-700" : "bg-white border-gray-200 text-gray-400"}`}>
                        {activeTab > step.id ? <Check size={16}/> : <step.icon size={16}/>}
                        <span className="font-medium text-sm">{step.label}</span>
                    </div>
                    {idx < 2 && <div className="w-12 h-px bg-gray-200 mx-2"></div>}
                </div>
            ))}
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            {message && (
                <div className={`p-4 flex items-center gap-3 ${message.type === "success" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"}`}>
                    {message.type === "success" ? <Check size={20}/> : <AlertTriangle size={20}/>}
                    {message.text}
                </div>
            )}

            <div className="p-8">
                {/* STEP 1: CREATE CLIENT */}
                {activeTab === 1 && (
                    <div className="max-w-md">
                        <h2 className="text-xl font-bold mb-4">Let's start with a name</h2>
                        <div className="mb-6">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Client / Company Name</label>
                            <input 
                                className="w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none"
                                placeholder="e.g. Acme Corp"
                                value={newClientName}
                                onChange={e => setNewClientName(e.target.value)}
                                disabled={!!generatedKey}
                            />
                        </div>

                        {!generatedKey ? (
                            <button 
                                onClick={handleCreateClient}
                                disabled={loading || !newClientName}
                                className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
                            >
                                {loading ? "Creating..." : "Create Client"} <ArrowRight size={16}/>
                            </button>
                        ) : (
                            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                                <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
                                    <h3 className="font-bold text-yellow-800 mb-2 flex items-center gap-2">
                                        <AlertTriangle size={16}/> API Key Generated
                                    </h3>
                                    <div className="flex items-center gap-2 bg-white border border-yellow-200 p-2 rounded">
                                        <code className="flex-1 font-mono text-sm overflow-hidden text-ellipsis">{generatedKey}</code>
                                        <button onClick={() => navigator.clipboard.writeText(generatedKey!)} className="p-2 hover:bg-gray-100 rounded text-gray-500">
                                            <Copy size={16}/>
                                        </button>
                                    </div>
                                    <p className="text-xs text-yellow-700 mt-2">
                                        <strong>Important:</strong> Copy this key now. It won't be shown again.
                                    </p>
                                </div>

                                <button 
                                    onClick={() => setActiveTab(2)}
                                    className="w-full bg-green-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-green-700 flex items-center justify-center gap-2"
                                >
                                    I have copied the key, Continue <ArrowRight size={16}/>
                                </button>
                            </div>
                        )}
                        
                        <div className="mt-8 pt-8 border-t border-gray-100 text-center">
                             <a href="/admin/legacy" className="text-xs text-gray-400 hover:text-gray-600 hover:underline">
                                 Looking for the classic v1 onboarding? Click here.
                             </a>
                        </div>
                    </div>
                )}

                {/* STEP 2: CONNECT DB */}
                {activeTab === 2 && (
                    <div className="max-w-lg">
                        <h2 className="text-xl font-bold mb-4">Connect ERP Database</h2>
                         <div className="grid grid-cols-2 gap-4 mb-4">
                             <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">DB Type</label>
                                <select 
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={dbConfig.db_type}
                                    onChange={e => setDbConfig({...dbConfig, db_type: e.target.value})}
                                >
                                    <option value="postgresql">PostgreSQL</option>
                                    <option value="mysql">MySQL</option>
                                </select>
                             </div>
                             <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
                                <input 
                                    type="number"
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={dbConfig.port}
                                    onChange={e => setDbConfig({...dbConfig, port: parseInt(e.target.value)})}
                                />
                             </div>
                         </div>
                         <div className="mb-4">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Host</label>
                            <input 
                                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                placeholder="e.g. localhost or 192.168.1.50"
                                value={dbConfig.host}
                                onChange={e => setDbConfig({...dbConfig, host: e.target.value})}
                            />
                            <p className="text-xs text-gray-400 mt-1">
                                💡 Docker users: use <code className="bg-gray-100 px-1 rounded">host.docker.internal</code> to connect to localhost.
                            </p>
                         </div>
                         <div className="mb-4">
                            <label className="block text-sm font-medium text-gray-700 mb-1">Database Name</label>
                            <input 
                                className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                value={dbConfig.database}
                                onChange={e => setDbConfig({...dbConfig, database: e.target.value})}
                            />
                         </div>
                         <div className="grid grid-cols-2 gap-4 mb-6">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                                <input 
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={dbConfig.username}
                                    onChange={e => setDbConfig({...dbConfig, username: e.target.value})}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                                <input 
                                    type="password"
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={dbConfig.password}
                                    onChange={e => setDbConfig({...dbConfig, password: e.target.value})}
                                />
                            </div>
                         </div>
                         <button 
                            onClick={handleConnectDB}
                            disabled={loading}
                            className="bg-emerald-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
                        >
                            {loading ? "Verifying..." : "Connect & Verify"} <ArrowRight size={16}/>
                        </button>
                    </div>
                )}

                {/* STEP 3: DISCOVERY */}
                {activeTab === 3 && (
                    <div>
                        <div className="flex items-center gap-3 mb-6">
                            <div className="w-12 h-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center">
                                <Check size={24}/>
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-gray-800">Connection Successful!</h2>
                                <p className="text-gray-500">We discovered {discoveredTables.length} tables in your database.</p>
                            </div>
                        </div>

                        {discoveredTables.length > 0 ? (
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
                                {discoveredTables.map(t => (
                                    <div key={t} className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm text-gray-700">
                                        <Table size={14} className="text-blue-500"/> {t}
                                    </div>
                                ))}
                            </div>
                        ) : (
                             <div className="text-center py-8 text-gray-400">
                                <p>No tables found? <button onClick={() => handleDiscoverTables()} className="text-blue-600 hover:underline">Retry Scan</button></p>
                             </div>
                        )}

                        <div className="flex gap-4">
                            <button className="bg-gray-100 text-gray-700 px-6 py-2 rounded-lg font-medium hover:bg-gray-200">
                                Add Another Client
                            </button>
                            <a href="/admin/semantic" className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 flex items-center gap-2">
                                Go to Semantic Mapping <ArrowRight size={16}/>
                            </a>
                        </div>
                    </div>
                )}
            </div>
        </div>
    </div>
  );
}
