
import { useState, useEffect } from "react";
import { ArrowLeft, Shield, CheckCircle, XCircle, AlertTriangle, RefreshCw, Lock, Zap, BarChart, HardDrive, LayoutGrid, List as ListIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { useAdmin } from "../context/AdminContext";
import { apiFetch } from "../utils/api";
import RelationshipGraph from "./admin/RelationshipGraph";
import RelationshipBulkPanel from "./admin/RelationshipBulkPanel";

interface AllowedRelationship {
  id: number;
  client_id: number;
  parent_table: string;
  parent_column: string;
  child_table: string;
  child_column: string;
  is_enabled: boolean;
  is_restricted: boolean;
  created_at: string;
}

type GovernanceMode = "simple" | "guided" | "strict";

export default function RelationshipGovernance() {
  const { apiKey, clientId } = useAdmin();
  const [relationships, setRelationships] = useState<AllowedRelationship[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [mode, setMode] = useState<GovernanceMode>("guided");
  const [modeLoading, setModeLoading] = useState(false);
  const [viewMode, setViewMode] = useState<"list" | "graph">("list");

  // Fetch Logic
  const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
          if (!apiKey || !clientId) throw new Error("No Client Selected");
          const apiUrl = import.meta.env.VITE_API_URL || "";

          // 1. Fetch Client Mode
          // We don't have a direct GET /client/{id} public endpoint easily accessible 
          // without refactoring. We'll use list_clients for now as it's an admin page.
          const clientRes = await apiFetch(`${apiUrl}/api/clients`, {
              headers: { "X-API-Key": apiKey } 
          });
          if (clientRes.ok) {
              const clientData = await clientRes.json();
              const myClient = clientData.clients.find((c: any) => c.id === clientId);
              if (myClient) setMode(myClient.governance_mode || "guided");
          }

          // 2. Fetch Relationships
          const relRes = await apiFetch(`${apiUrl}/api/v2/relationships`, {
            headers: { "X-API-Key": apiKey }
          });
          
          if (!relRes.ok) {
               const text = await relRes.text();
               try {
                   const json = JSON.parse(text);
                   throw new Error(json.detail || "Failed to fetch relationships");
               } catch (e) {
                   throw new Error(`Failed to fetch relationships: ${relRes.status} ${relRes.statusText}`);
               }
          }
          
          const data = await relRes.json();
          setRelationships(data);

      } catch (err: any) {
          setError(err.message);
      } finally {
          setLoading(false);
      }
  };

  useEffect(() => {
    fetchAll();
  }, [apiKey, clientId]);

  const updateMode = async (newMode: GovernanceMode) => {
      if (!clientId) return;
      if (!confirm(`Switch to ${newMode.toUpperCase()} mode? This will re-run discovery.`)) return;

      setModeLoading(true);
      try {
          const apiUrl = import.meta.env.VITE_API_URL || "";
          const response = await apiFetch(`${apiUrl}/api/clients/${clientId}/governance-mode`, {
              method: "PATCH",
              headers: {
                  "Content-Type": "application/json",
                  "X-API-Key": apiKey || ""
              },
              body: JSON.stringify({ governance_mode: newMode })
          });

          if (!response.ok) throw new Error("Failed to update mode");
          
          setMode(newMode);
          await fetchAll(); // Refresh relationships
      } catch (err: any) {
          alert(err.message);
      } finally {
          setModeLoading(false);
      }
  };

  const toggleRelationship = async (id: number, currentStatus: boolean) => {
    try {
      if (!apiKey) return;
      if (mode === "simple") return; // Read-only in simple mode

      const apiUrl = import.meta.env.VITE_API_URL || "";

      // Optimistic update
      setRelationships(prev => prev.map(r => 
        r.id === id ? { ...r, is_enabled: !currentStatus } : r
      ));

      const response = await apiFetch(`${apiUrl}/api/v2/relationships/${id}/toggle`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey
        },
        body: JSON.stringify({ is_enabled: !currentStatus })
      });

      if (!response.ok) {
        // Revert on failure
        setRelationships(prev => prev.map(r => 
            r.id === id ? { ...r, is_enabled: currentStatus } : r
        ));
        throw new Error("Failed to toggle relationship");
      }
    } catch (err) {
      console.error(err);
      alert("Failed to update relationship status.");
    }
  };

  const toggleRestriction = async (id: number, currentStatus: boolean) => {
    try {
        if (!apiKey) return;
        
        const apiUrl = import.meta.env.VITE_API_URL || "";

        // Optimistic update
        setRelationships(prev => prev.map(r => 
          r.id === id ? { ...r, is_restricted: !currentStatus } : r
        ));
  
        const response = await apiFetch(`${apiUrl}/api/v2/relationships/${id}/restrict`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-API-Key": apiKey
          },
          body: JSON.stringify({ is_restricted: !currentStatus })
        });
  
        if (!response.ok) {
          // Revert
          setRelationships(prev => prev.map(r => 
              r.id === id ? { ...r, is_restricted: currentStatus } : r
          ));
          throw new Error("Failed to restrict relationship");
        }
      } catch (err) {
        console.error(err);
        alert("Failed to update restriction status.");
      }
  };

  if (!apiKey) return <div className="p-8">Please select a client first.</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center mb-8">
          <Link to="/admin" className="mr-4 p-2 bg-white rounded-full shadow-sm hover:bg-gray-50 transition-colors">
            <ArrowLeft size={20} className="text-gray-600" />
          </Link>
          <div>
            <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-2">
              <Shield className="text-purple-600" />
              Relationship Governance
            </h1>
            <p className="text-gray-500">Manage allowed database joins for the Query Builder.</p>
          </div>
          <div className="ml-auto flex gap-3">
              <button 
                onClick={fetchAll} 
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg shadow-sm hover:bg-gray-50 text-gray-600"
              >
                  <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
                  Refresh
              </button>
              
              <div className="flex bg-gray-200 p-1 rounded-lg">
                  <button
                    onClick={() => setViewMode("list")}
                    className={`p-2 rounded-md ${viewMode === "list" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-900"}`}
                    title="List View"
                  >
                      <ListIcon size={18} />
                  </button>
                  <button
                    onClick={() => setViewMode("graph")}
                    className={`p-2 rounded-md ${viewMode === "graph" ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-900"}`}
                    title="Graph View"
                  >
                      <LayoutGrid size={18} />
                  </button>
              </div>
          </div>
        </div>

        {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl mb-6 flex items-center gap-2">
                <AlertTriangle size={20} />
                {error}
            </div>
        )}

        {/* MODE BANNER */}
        <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-8">
            <div className="flex items-center justify-between">
                <div>
                     <h3 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-1">Governance Mode</h3>
                     <div className="flex items-center gap-2">
                        {mode === "simple" && <Zap className="text-blue-500" size={24} fill="currentColor" fillOpacity={0.1} />}
                        {mode === "guided" && <BarChart className="text-orange-500" size={24} />}
                        {mode === "strict" && <HardDrive className="text-red-600" size={24} />}
                        
                        <span className="text-2xl font-bold text-gray-800 capitalize">{mode} Mode</span>
                     </div>
                     <p className="text-gray-500 text-sm mt-1">
                         {mode === "simple" && "Zero friction. Relationships are auto-enabled (max depth 5). Controls hidden."}
                         {mode === "guided" && "Balanced control. Safe defaults enabled. Admin can override."}
                         {mode === "strict" && "Enterprise security. Default deny. Full manual control required."}
                     </p>
                </div>

                <div className="flex bg-gray-100 p-1 rounded-lg">
                    {["simple", "guided", "strict"].map((m) => (
                        <button
                            key={m}
                            disabled={modeLoading}
                            onClick={() => updateMode(m as GovernanceMode)}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                                mode === m 
                                    ? "bg-white text-gray-900 shadow-sm" 
                                    : "text-gray-500 hover:text-gray-900"
                            }`}
                        >
                            {m.charAt(0).toUpperCase() + m.slice(1)}
                        </button>
                    ))}
                </div>
            </div>
        </div>


        
        {/* Main Content Area */}
        {viewMode === "list" ? (
             /* Table */
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-gray-50 text-gray-500 text-sm font-medium border-b border-gray-100">
                            <tr>
                                <th className="px-6 py-4">Parent Table (One)</th>
                                <th className="px-6 py-4">Join On</th>
                                <th className="px-6 py-4">Child Table (Many)</th>
                                <th className="px-6 py-4 text-center">Status</th>
                                <th className="px-6 py-4 text-center">Restricted</th>
                                {mode !== "simple" && <th className="px-6 py-4 text-right">Actions</th>}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                            {loading && relationships.length === 0 ? (
                                <tr><td colSpan={6} className="px-6 py-8 text-center text-gray-400">Loading governance rules...</td></tr>
                            ) : relationships.length === 0 ? (
                                <tr><td colSpan={6} className="px-6 py-8 text-center text-gray-400">No relationships discovered yet. Ensure database has data.</td></tr>
                            ) : (
                                relationships.map((rel) => (
                                    <tr key={rel.id} className="hover:bg-gray-50/50 transition-colors group">
                                        <td className="px-6 py-4 font-medium text-gray-800">
                                            {rel.parent_table}
                                            <div className="text-xs text-gray-400 font-mono mt-0.5">{rel.parent_column}</div>
                                        </td>
                                        <td className="px-6 py-4 text-gray-400">
                                            <div className="flex items-center gap-2 text-xs bg-gray-100 px-2 py-1 rounded w-fit">
                                                One to Many
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 font-medium text-gray-800">
                                            {rel.child_table}
                                            <div className="text-xs text-gray-400 font-mono mt-0.5">{rel.child_column}</div>
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                                                rel.is_enabled 
                                                    ? "bg-green-50 text-green-700 border border-green-100" 
                                                    : "bg-gray-100 text-gray-500 border border-gray-200"
                                            }`}>
                                                {rel.is_enabled ? (
                                                    <><CheckCircle size={12} /> Enabled</>
                                                ) : (
                                                    <><XCircle size={12} /> Disabled</>
                                                )}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                           {rel.is_restricted && (
                                               <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-50 text-red-600 rounded text-xs border border-red-100">
                                                   <Lock size={10} /> Restricted
                                               </span>
                                           )}
                                        </td>
                                        {mode !== "simple" && (
                                            <td className="px-6 py-4 text-right">
                                                <div className="flex items-center justify-end gap-2">
                                                    <button 
                                                        onClick={() => toggleRelationship(rel.id, rel.is_enabled)}
                                                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                                                            rel.is_enabled 
                                                                ? "bg-white border-gray-200 text-gray-600 hover:bg-red-50 hover:text-red-600 hover:border-red-200" 
                                                                : "bg-purple-600 border-purple-600 text-white hover:bg-purple-700"
                                                        }`}
                                                    >
                                                        {rel.is_enabled ? "Disable" : "Enable"}
                                                    </button>
                                                    
                                                    <button 
                                                        onClick={() => toggleRestriction(rel.id, rel.is_restricted)}
                                                        className={`p-1.5 rounded-lg border transition-colors ${
                                                            rel.is_restricted
                                                                ? "bg-red-50 border-red-200 text-red-600"
                                                                : "bg-white border-gray-200 text-gray-400 hover:text-gray-600"
                                                        }`}
                                                        title="Restrict"
                                                    >
                                                        <Lock size={14} />
                                                    </button>
                                                </div>
                                            </td>
                                        )}
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        ) : (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-1">
                <RelationshipGraph apiKey={apiKey} />
            </div>
        )}
        
        <RelationshipBulkPanel apiKey={apiKey} onUpdate={fetchAll} />
      </div>
    </div>
  );
}


