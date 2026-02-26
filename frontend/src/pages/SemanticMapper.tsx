import { useState, useEffect } from "react";
import { useAdmin } from "../context/AdminContext";
import { Check, Database, Save, AlertTriangle, Loader2, HelpCircle } from "lucide-react";
import { apiFetch } from "../utils/api";

interface ColumnMapping {
  table_name: string;
  column_name: string;
  label: string;
  synonyms: string; 
  data_format: string;
  is_default_date: boolean;
}

export default function SemanticMapper() {
  const { clientId, apiKey } = useAdmin();
  const [tables, setTables] = useState<{name: string, columns: string[]}[]>([]);
  const [selectedTable, setSelectedTable] = useState("");
  const [mappings, setMappings] = useState<ColumnMapping[]>([]);
  
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);

  const API_BASE = import.meta.env.DEV ? "http://localhost:8000/api" : "/api";

  const showMessage = (type: "success" | "error", text: string) => {
      setMessage({ type, text });
      setTimeout(() => setMessage(null), 4000);
  };

  // 1. Fetch Tables for Discovery
  useEffect(() => {
    if (!clientId) return;
    const fetchTables = async () => {
        setLoading(true);
        try {
            const res = await apiFetch(`${API_BASE}/clients/${clientId}/tables`);
            if (!res.ok) throw new Error("Failed to fetch discovery");
            const data = await res.json();
            setTables(data.tables || []);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };
    fetchTables();
  }, [clientId]);

  // Handle Input Changes
  const handleMappingChange = (index: number, field: keyof ColumnMapping, value: any) => {
      const newMappings = [...mappings];
      newMappings[index] = { ...newMappings[index], [field]: value };
      setMappings(newMappings);
  };

  // Select Table -> Populate Mappings State
  const handleTableSelect = (tableName: string) => {
      setSelectedTable(tableName);
      if (!tableName) return;
      
      const table = tables.find(t => t.name === tableName);
      if (table) {
          // Initialize empty mappings for all columns
          const initialMappings = table.columns.map(col => ({
             table_name: tableName,
             column_name: col,
             label: col.replace(/_/g, " "),
             synonyms: "", // Init as empty string
             data_format: "text",
             is_default_date: false
          }));
          setMappings(initialMappings);
      }
  };

  const handleSave = async () => {
      if (!apiKey) return showMessage("error", "API Key missing (Reload page or select client)");
      setSaving(true);
      
      try {
          // Transform string synonyms back to array for API
          const payload = { 
              mappings: mappings.map(m => ({
                  ...m,
                  synonyms: m.synonyms.split(",").map(s => s.trim()).filter(Boolean)
              }))
          };

          const res = await apiFetch(`${API_BASE}/v2/semantic/columns`, {
              method: "POST",
              headers: { 
                  "Content-Type": "application/json",
                  "X-API-Key": apiKey 
              },
              body: JSON.stringify(payload)
          });
          
          if (!res.ok) {
              const err = await res.json();
              throw new Error(err.detail || "Save failed");
          }
          
          showMessage("success", "Semantic mappings saved successfully!");
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setSaving(false);
      }
  };

  if (!clientId) return <div className="p-8 text-center text-gray-500">Please select a client from the dashboard.</div>;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-6 border-b border-gray-100 flex justify-between items-center">
            <div>
                <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                    <Database size={20} className="text-blue-600"/> Semantic Mapper
                </h2>
                <p className="text-sm text-gray-500 mt-1">Define business labels for your raw database columns.</p>
            </div>
            {message && (
                <div className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                   {message.type === "success" ? <Check size={16}/> : <AlertTriangle size={16}/>}
                   {message.text}
                </div>
            )}
        </div>

        <div className="p-6">
            {/* Table Selector */}
            <div className="mb-8 max-w-md">
                <label className="block text-sm font-bold text-gray-700 mb-2">Select Database Table</label>
                <div className="relative">
                    <select 
                        className="w-full border border-gray-300 rounded-lg p-3 pr-10 appearance-none bg-white focus:ring-2 focus:ring-blue-100 outline-none"
                        value={selectedTable}
                        onChange={e => handleTableSelect(e.target.value)}
                        disabled={loading}
                    >
                        <option value="">-- Choose Table --</option>
                        {tables.map(t => <option key={t.name} value={t.name}>{t.name}</option>)}
                    </select>
                    {loading && <div className="absolute right-3 top-3"><Loader2 size={18} className="animate-spin text-gray-400"/></div>}
                </div>
                {tables.length === 0 && !loading && (
                    <p className="text-xs text-red-500 mt-2">No tables found. Run discovery first.</p>
                )}
            </div>

            {/* Mappings Editor */}
            {selectedTable && (
                <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="overflow-x-auto border rounded-xl">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-gray-50 text-gray-600 font-bold border-b">
                                <tr>
                                    <th className="p-4">Raw Column</th>
                                    <th className="p-4 w-1/4">Business Label <span className="text-red-500">*</span></th>
                                    <th className="p-4 w-1/4">
                                        <div className="flex items-center gap-1" title="Comma-separated (e.g. Tax ID, TIN)">
                                            Synonyms <HelpCircle size={14} className="text-gray-400"/>
                                        </div>
                                    </th>
                                    <th className="p-4">Data Type</th>
                                    <th className="p-4 text-center">Is Date Filter?</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y">
                                {mappings.map((m, idx) => (
                                    <tr key={idx} className="hover:bg-blue-50/30 transition-colors">
                                        <td className="p-4 font-mono text-gray-600">{m.column_name}</td>
                                        <td className="p-4">
                                            <input 
                                                className="w-full border border-gray-300 rounded p-2 focus:border-blue-500 outline-none"
                                                value={m.label}
                                                onChange={e => handleMappingChange(idx, "label", e.target.value)}
                                                placeholder="e.g. Total Revenue"
                                            />
                                        </td>
                                        <td className="p-4">
                                            <input 
                                                className="w-full border border-gray-300 rounded p-2 focus:border-blue-500 outline-none placeholder:text-gray-300"
                                                value={m.synonyms}
                                                onChange={e => handleMappingChange(idx, "synonyms", e.target.value)}
                                                placeholder="e.g. Sales, Income"
                                            />
                                        </td>
                                        <td className="p-4">
                                            <select 
                                                className="w-full border border-gray-300 rounded p-2 bg-white"
                                                value={m.data_format}
                                                onChange={e => handleMappingChange(idx, "data_format", e.target.value)}
                                            >
                                                <option value="text">Text</option>
                                                <option value="number">Number</option>
                                                <option value="currency">Currency</option>
                                                <option value="date">Date</option>
                                                <option value="boolean">Boolean</option>
                                            </select>
                                        </td>
                                        <td className="p-4 text-center">
                                            <input 
                                                type="checkbox"
                                                className="w-5 h-5 text-blue-600 rounded focus:ring-blue-500"
                                                checked={m.is_default_date}
                                                onChange={e => handleMappingChange(idx, "is_default_date", e.target.checked)}
                                            />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="mt-6 flex justify-end">
                        <button 
                            onClick={handleSave}
                            disabled={saving}
                            className="bg-blue-600 text-white px-6 py-3 rounded-lg font-bold flex items-center gap-2 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-lg shadow-blue-200"
                        >
                            {saving ? <Loader2 size={18} className="animate-spin"/> : <Save size={18} />}
                            {saving ? "Saving..." : "Save Mappings"}
                        </button>
                    </div>
                </div>
            )}
        </div>
    </div>
  );
}
