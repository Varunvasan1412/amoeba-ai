import { useState, useEffect } from "react";
import { useAdmin } from "../context/AdminContext";
import { Check, Database, Save, AlertTriangle, Loader2, Link2 } from "lucide-react";
import { apiFetch } from "../utils/api";
import { SearchableDropdown } from "../components/admin/SearchableDropdown";

interface ColumnMapping {
  table_name: string;
  column_name: string;
  label: string;
  synonyms: string; 
  data_format: string;
  is_default_date: boolean;
}

interface FieldMetadata {
    id?: number;
    client_id: number;
    table_name: string;
    column_name: string;
    label: string;
    input_type: string;
    storage_type: string;
    data_source_table?: string;
    value_column?: string;
    display_column?: string;
    required: boolean;
    readonly: boolean;
    is_visible: boolean;
    default_value?: string;
}

interface Relationship {
    id: number;
    parent_table: string;
    parent_column: string;
    child_table: string;
    child_column: string;
    selected_columns: string[];
}

export default function SemanticMapper() {
  const { clientId, apiKey } = useAdmin();
  const [tables, setTables] = useState<{name: string, columns: string[]}[]>([]);
  const [selectedTable, setSelectedTable] = useState("");
  
  // Data States
  const [mappings, setMappings] = useState<ColumnMapping[]>([]);
  const [fieldMeta, setFieldMeta] = useState<FieldMetadata[]>([]);
  const [rels, setRels] = useState<Relationship[]>([]);
  const [sampleData, setSampleData] = useState<Record<string, any>>({}); 

  const [activeTab, setActiveTab] = useState<'definitions' | 'ux'>('definitions');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);

  const API_BASE = import.meta.env.VITE_API_URL || "";

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
            const res = await apiFetch(`${API_BASE}/clients/${clientId}/tables`.replace(/\/\//g, '/').replace(':/', '://'));
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(errorData.detail || "Failed to fetch discovery");
            }
            const data = await res.json();
            setTables(data.tables || []);

            const rRes = await apiFetch(`${API_BASE}/v2/relationships`.replace(/\/\//g, '/').replace(':/', '://'), {
                headers: { "X-API-Key": apiKey || "" }
            });
            const rData = await rRes.json();
            setRels(Array.isArray(rData) ? rData : []);

        } catch (err: any) {
            console.error(err);
            showMessage("error", err.message || "Failed to load discovery data.");
        } finally {
            setLoading(false);
        }
    };
    fetchTables();
  }, [clientId, apiKey]);

  // Handle Input Changes
  const handleMappingChange = (index: number, field: keyof ColumnMapping, value: any) => {
      const newMappings = [...mappings];
      newMappings[index] = { ...newMappings[index], [field]: value } as any;
      setMappings(newMappings);
  };

  const handleMetaChange = (index: number, field: keyof FieldMetadata, value: any) => {
      const next = [...fieldMeta];
      next[index] = { ...next[index], [field]: value } as any;
      setFieldMeta(next);
  };

  // Select Table -> Populate Mappings State
  const handleTableSelect = async (tableName: string) => {
      setSelectedTable(tableName);
      if (!tableName || !clientId) return;
      
      setLoading(true);
      try {
          // 1. Fetch Definitions
          const semRes = await apiFetch(`${API_BASE}/v2/semantic/tables/${tableName}`.replace(/\/\//g, '/').replace(':/', '://'), {
              headers: { "X-API-Key": apiKey || "" }
          });
          const semData = semRes.ok ? await semRes.json() : [];
          const semLookup = semData.reduce((acc: any, curr: any) => { acc[curr.column_name] = curr; return acc; }, {});

          const metaRes = await apiFetch(`${API_BASE}/field-metadata/${clientId}/${tableName}`.replace(/\/\//g, '/').replace(':/', '://'), {
            headers: { "X-API-Key": apiKey || "" }
          });

          const metaData = metaRes.ok ? await metaRes.json() : [];
          const metaLookup = metaData.reduce((acc: any, curr: any) => { acc[curr.column_name] = curr; return acc; }, {});

          const table = tables.find(t => t.name === tableName);
          if (table) {
              const initialMappings = table.columns.map(col => {
                 const existing = semLookup[col];
                 return {
                     table_name: tableName,
                     column_name: col,
                     label: existing ? existing.label : col.replace(/_/g, " "),
                     synonyms: existing && existing.synonyms ? existing.synonyms.join(", ") : "",
                     data_format: existing ? existing.data_format : "text",
                     is_default_date: existing ? existing.is_default_date : false
                 };
              });
              setMappings(initialMappings);

              const initialMeta = table.columns.map(col => {
                  const existing = metaLookup[col];
                  // Robust link finding: check both directions
                  const link = rels.find(r => 
                    (r.parent_table === tableName && r.parent_column === col) ||
                    (r.child_table === tableName && r.child_column === col)
                  );
                  
                  // Determine which table is the "source" of dropdown data
                  const sourceTable = link ? (link.parent_table === tableName ? link.child_table : link.parent_table) : "";
                  const sourceColumn = link ? (link.parent_table === tableName ? link.child_column : link.parent_column) : "id";

                  return {
                      id: existing?.id,
                      client_id: Number(clientId),
                      table_name: tableName,
                      column_name: col,
                      label: existing ? existing.label : col.replace(/_/g, " "),
                      input_type: existing ? existing.input_type : (link ? "dropdown" : "text"),
                      storage_type: existing ? existing.storage_type : "string",
                      data_source_table: existing?.data_source_table || sourceTable,
                      value_column: existing?.value_column || sourceColumn,
                      display_column: existing?.display_column || "",
                      required: existing ? existing.required : false,
                      readonly: existing ? existing.readonly : false,
                      is_visible: existing ? existing.is_visible : true,
                      default_value: existing?.default_value || ""
                  };
              });
              setFieldMeta(initialMeta);

              // Fetch samples
              const relatedTables = Array.from(new Set(
                  rels.filter(r => r.parent_table === tableName || r.child_table === tableName)
                      .map(r => r.parent_table === tableName ? r.child_table : r.parent_table)
              ));
              
              const samples: Record<string, any> = {};
              await Promise.all(relatedTables.map(async (t) => {
                  const sRes = await apiFetch(`${API_BASE}/field-metadata/sample/${clientId}/${t}`.replace(/\/\//g, '/').replace(':/', '://'), {
                      headers: { "X-API-Key": apiKey || "" }
                  });
                  if (sRes.ok) samples[t] = await sRes.json();
              }));
              setSampleData(samples);
          }
      } catch (err) {
          console.error(err);
      } finally {
          setLoading(false);
      }
  };

  const handleSave = async () => {
      if (!apiKey) return showMessage("error", "API Key missing.");
      setSaving(true);
      try {
          // 1. Save Semantic Mappings
          const semanticPayload = { 
              mappings: mappings.map(m => ({
                  ...m,
                  synonyms: m.synonyms.split(",").map(s => s.trim()).filter(Boolean)
              }))
          };
          const semRes = await apiFetch(`${API_BASE}/v2/semantic/columns`.replace(/\/\//g, '/').replace(':/', '://'), {
              method: "POST",
              headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
              body: JSON.stringify(semanticPayload)
          });
          if (!semRes.ok) throw new Error("Failed to save semantic mappings");

          // 2. Save Field Metadata (Sync labels from Business Definitions first)
          const syncedMeta = fieldMeta.map(meta => {
              const semanticMapping = mappings.find(m => m.column_name === meta.column_name);
              return semanticMapping ? { ...meta, label: semanticMapping.label } : meta;
          });
          const updatePromises = syncedMeta.map(async (meta) => {
            if (!meta.id) {
                const res = await apiFetch(`${API_BASE}/field-metadata`.replace(/\/\//g, '/').replace(':/', '://'), {
                    method: "POST", headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
                    body: JSON.stringify(meta)
                });
                return res.ok;
            } else {
                const res = await apiFetch(`${API_BASE}/field-metadata/${meta.id}`.replace(/\/\//g, '/').replace(':/', '://'), {
                    method: "PUT", headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
                    body: JSON.stringify(meta)
                });
                return res.ok;
            }
          });
          await Promise.all(updatePromises);

          showMessage("success", "Intelligence Layer updated successfully!");
          if (selectedTable) handleTableSelect(selectedTable);
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setSaving(false);
      }
  };

  if (!clientId) return <div className="p-8 text-center text-gray-500 font-bold uppercase tracking-widest text-xs">Please select a client from the dashboard.</div>;

  return (
    <div className="p-4 md:p-6 w-full max-w-[1400px] mx-auto min-h-screen flex flex-col gap-6">
        {/* Header - Pill Styled */}
        <header className="bg-white p-6 rounded-[32px] shadow-sm border border-gray-100 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-center gap-4">
                <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-3 rounded-2xl text-white shadow-xl shadow-blue-200">
                    <Database size={28} />
                </div>
                <div>
                    <h1 className="text-2xl font-black text-gray-900 tracking-tight">Semantic Graph</h1>
                    <p className="text-gray-500 text-xs font-medium">Fine-tune how AI perceives your database architecture.</p>
                </div>
            </div>

            <div className="w-full md:w-[320px] space-y-2">
                <label className="text-[10px] font-black text-gray-400 uppercase tracking-widest ml-1">Target Table</label>
                <SearchableDropdown
                    options={tables.map(t => ({ value: t.name, label: t.name }))}
                    value={selectedTable}
                    onChange={handleTableSelect}
                    placeholder="Choose Table..."
                />
            </div>
        </header>

        {selectedTable && (
            <div className="flex-1 flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                {/* Tabs / Toggler */}
                <div className="inline-flex bg-gray-100/50 p-1.5 rounded-2xl self-start border border-gray-100 shadow-inner">
                    <button 
                        onClick={() => setActiveTab('definitions')}
                        className={`px-8 py-3 rounded-xl text-sm font-black transition-all flex items-center gap-2 ${
                            activeTab === 'definitions' ? 'bg-white text-blue-600 shadow-md ring-1 ring-gray-100' : 'text-gray-500 hover:text-gray-700'
                        }`}
                    >
                        <Check size={18} />
                        FIELD DEFINITIONS
                        <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded-full ${activeTab === 'definitions' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>{mappings.length}</span>
                    </button>
                    <button 
                        onClick={() => setActiveTab('ux')}
                        className={`px-8 py-3 rounded-xl text-sm font-black transition-all flex items-center gap-2 ${
                            activeTab === 'ux' ? 'bg-white text-blue-600 shadow-md ring-1 ring-gray-100' : 'text-gray-500 hover:text-gray-700'
                        }`}
                    >
                        <Save size={18} />
                        FORM UX & INTEGRITY
                        <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded-full ${activeTab === 'ux' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>{fieldMeta.length}</span>
                    </button>
                </div>

                {/* Content Area */}
                <div className="bg-white rounded-[40px] shadow-2xl shadow-gray-200/50 border border-gray-100 overflow-hidden flex flex-col">
                    {activeTab === 'definitions' ? (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="bg-gray-50/50 border-b border-gray-100">
                                        <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[20%]">Column</th>
                                        <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[25%]">Business Label</th>
                                        <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[30%]">AI Synonyms</th>
                                        <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[15%]">Format</th>
                                        <th className="px-6 py-5 text-center text-[10px] font-black text-gray-400 uppercase tracking-widest w-[10%]">Date?</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50">
                                    {mappings.map((m, idx) => (
                                        <tr key={idx} className="hover:bg-blue-50/20 transition-all border-b border-gray-50 last:border-0 text-sm">
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-mono text-[10px] font-bold text-gray-400 bg-gray-50 px-2 py-1 rounded border border-gray-100">{m.column_name}</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <input
                                                    className="w-full bg-gray-50/50 border border-transparent rounded-xl px-4 py-2 font-bold text-gray-900 focus:bg-white focus:border-blue-100 focus:ring-4 focus:ring-blue-50 outline-none transition-all"
                                                    value={m.label}
                                                    onChange={e => handleMappingChange(idx, "label", e.target.value)}
                                                />
                                            </td>
                                            <td className="px-6 py-4">
                                                <input
                                                    className="w-full bg-gray-50/50 border border-transparent rounded-xl px-4 py-2 font-bold text-gray-900 focus:bg-white focus:border-blue-100 focus:ring-4 focus:ring-blue-50 outline-none transition-all"
                                                    value={m.synonyms}
                                                    onChange={e => handleMappingChange(idx, "synonyms", e.target.value)}
                                                    placeholder="e.g. Sales, Income"
                                                />
                                            </td>
                                            <td className="px-6 py-4">
                                                <select
                                                    className="w-full bg-gray-50/50 border border-transparent rounded-xl px-4 py-2 font-bold text-blue-600 focus:bg-white focus:border-blue-100 outline-none transition-all cursor-pointer"
                                                    value={m.data_format}
                                                    onChange={e => handleMappingChange(idx, "data_format", e.target.value)}
                                                >
                                                    <option value="text">TEXT</option>
                                                    <option value="number">NUMBER</option>
                                                    <option value="currency">CURRENCY</option>
                                                    <option value="date">DATE</option>
                                                </select>
                                            </td>
                                            <td className="px-6 py-4 text-center">
                                                <input 
                                                    type="checkbox" 
                                                    className="w-5 h-5 rounded-lg text-blue-600 border-gray-100 focus:ring-blue-50/50 cursor-pointer" 
                                                    checked={m.is_default_date} 
                                                    onChange={e => handleMappingChange(idx, "is_default_date", e.target.checked)}
                                                />
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="bg-gray-50/50 border-b border-gray-100">
                                        <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[25%]">Field Label</th>
                                        <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[25%]">Input Method</th>
                                        <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[20%]">Storage</th>
                                        <th className="px-6 py-5 text-center text-[10px] font-black text-gray-400 uppercase tracking-widest w-[15%]">Req?</th>
                                        <th className="px-6 py-5 text-center text-[10px] font-black text-gray-400 uppercase tracking-widest w-[15%]">Show?</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-50">
                                    {fieldMeta.map((meta, idx) => {
                                        const link = rels.find(r => 
                                            (r.parent_table === selectedTable && r.parent_column === meta.column_name) ||
                                            (r.child_table === selectedTable && r.child_column === meta.column_name)
                                        );
                                        const sourceTable = link ? (link.parent_table === selectedTable ? link.child_table : link.parent_table) : null;
                                        // Sync: Pull the Business Label from Field Definitions tab
                                        const semanticMapping = mappings.find(m => m.column_name === meta.column_name);
                                        const displayLabel = semanticMapping?.label || meta.label;

                                        return (
                                            <tr key={idx} className="hover:bg-blue-50/20 transition-all border-b border-gray-50 last:border-0 text-sm">
                                                <td className="px-6 py-4">
                                                    <div className="flex flex-col">
                                                        <span className="font-black text-gray-900">{displayLabel}</span>
                                                        {meta.input_type === 'dropdown' && sourceTable && (
                                                            <div className="flex items-center gap-1 mt-1">
                                                                <Link2 size={10} className="text-blue-500" />
                                                                <span className="text-[9px] font-black text-blue-500 uppercase tracking-widest">FROM {sourceTable}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <select 
                                                        className="w-full bg-gray-50/50 border border-transparent rounded-xl px-4 py-2 font-bold text-gray-900 focus:bg-white focus:border-blue-100 outline-none transition-all cursor-pointer"
                                                        value={meta.input_type}
                                                        onChange={e => handleMetaChange(idx, "input_type", e.target.value)}
                                                    >
                                                        <option value="text">SIMPLE TEXT</option>
                                                        <option value="dropdown">SMART DROPDOWN</option>
                                                        <option value="date">DATE PICKER</option>
                                                        <option value="checkbox">BOOLEAN SWITCH</option>
                                                        <option value="textarea">MULTI-LINE AREA</option>
                                                        <option value="number">NUMERIC INPUT</option>
                                                    </select>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <select
                                                        className="w-full bg-gray-50/50 border border-transparent rounded-xl px-4 py-2 font-bold text-gray-400 focus:bg-white focus:border-blue-100 outline-none transition-all cursor-pointer uppercase text-[10px] tracking-widest"
                                                        value={meta.storage_type}
                                                        onChange={e => handleMetaChange(idx, "storage_type", e.target.value)}
                                                    >
                                                        <option value="string">STRING</option>
                                                        <option value="integer">INTEGER</option>
                                                        <option value="float">FLOAT</option>
                                                        <option value="boolean">BOOLEAN</option>
                                                        <option value="date">DATE</option>
                                                    </select>
                                                </td>
                                                <td className="px-6 py-4 text-center">
                                                    <input 
                                                        type="checkbox" 
                                                        className="w-5 h-5 rounded-lg text-blue-600 border-gray-100 focus:ring-blue-50/50 cursor-pointer" 
                                                        checked={meta.required} 
                                                        onChange={e => handleMetaChange(idx, "required", e.target.checked)}
                                                    />
                                                </td>
                                                <td className="px-6 py-4 text-center">
                                                    <input 
                                                        type="checkbox" 
                                                        className="w-5 h-5 rounded-lg text-blue-600 border-gray-100 focus:ring-blue-50/50 cursor-pointer" 
                                                        checked={meta.is_visible} 
                                                        onChange={e => handleMetaChange(idx, "is_visible", e.target.checked)}
                                                    />
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* Footer Action */}
                <div className="flex justify-end pt-4 pb-12">
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="bg-gradient-to-br from-blue-600 to-indigo-700 text-white px-12 py-5 rounded-[24px] font-black text-lg flex items-center justify-center gap-3 hover:shadow-2xl hover:shadow-blue-200 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 transition-all shadow-xl shadow-blue-100 min-w-[300px]"
                    >
                        {saving ? <Loader2 size={24} className="animate-spin"/> : <Save size={24} />}
                        {saving ? "UPDATING BRAIN..." : "DEPLOY SEMANTIC LAYER"}
                    </button>
                </div>
            </div>
        )}

        {message && (
            <div className={`fixed bottom-8 right-8 px-6 py-4 rounded-3xl shadow-2xl border flex items-center gap-3 animate-in slide-in-from-bottom-10 duration-500 z-[100] ${
                message.type === 'success' ? 'bg-white border-green-100 text-green-600' : 'bg-white border-red-100 text-red-600'
            }`}>
                <div className={`p-2 rounded-xl ${message.type === 'success' ? 'bg-green-50' : 'bg-red-50'}`}>
                    {message.type === 'success' ? <Check size={20} /> : <AlertTriangle size={20} />}
                </div>
                <span className="font-black text-sm uppercase tracking-tight">{message.text}</span>
            </div>
        )}
    </div>
  );
}
