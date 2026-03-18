import { useState, useEffect } from "react";
import { useAdmin } from "../context/AdminContext";
import { Check, Database, Save, AlertTriangle, Loader2, HelpCircle, ChevronDown, Link2 } from "lucide-react";
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
            if (!res.ok) throw new Error("Failed to fetch discovery");
            const data = await res.json();
            setTables(data.tables || []);

            const rRes = await apiFetch(`${API_BASE}/relationships`.replace(/\/\//g, '/').replace(':/', '://'), {
                headers: { "X-API-Key": apiKey || "" }
            });
            const rData = await rRes.json();
            setRels(Array.isArray(rData) ? rData : []);

        } catch (err) {
            console.error(err);
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
          const semRes = await apiFetch(`${API_BASE}/semantic/tables/${tableName}`.replace(/\/\//g, '/').replace(':/', '://'), {
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
          const semRes = await apiFetch(`${API_BASE}/semantic/columns`.replace(/\/\//g, '/').replace(':/', '://'), {
              method: "POST",
              headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
              body: JSON.stringify(semanticPayload)
          });
          if (!semRes.ok) throw new Error("Failed to save semantic mappings");

          // 2. Save Field Metadata
          const updatePromises = fieldMeta.map(async (meta) => {
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
    <div className="space-y-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="p-6 border-b border-gray-100 flex justify-between items-center">
                <div>
                    <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                        <Database size={20} className="text-blue-600"/> Intelligence Layer
                    </h2>
                    <p className="text-sm text-gray-500 mt-1">Refine how AI perceives and interacts with your data.</p>
                </div>
                {message && (
                    <div className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                    {message.type === "success" ? <Check size={16}/> : <AlertTriangle size={16}/>}
                    {message.text}
                    </div>
                )}
            </div>

            <div className="p-6">
                <div className="mb-8 max-w-md">
                    <label className="block text-sm font-bold text-gray-700 mb-2">Select Database Table</label>
                    <SearchableDropdown
                        options={tables.map(t => ({ value: t.name, label: t.name }))}
                        value={selectedTable}
                        onChange={handleTableSelect}
                        disabled={loading}
                        placeholder="-- Choose Table --"
                    />
                </div>

                {selectedTable && (
                    <div className="space-y-10 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        {/* Part 1: Business Names */}
                        <div className="space-y-4">
                            <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                                <Check size={18} className="text-green-500"/> Business Names & AI Keywords
                            </h3>
                            <div className="border rounded-xl">
                                <table className="w-full text-left text-sm">   
                                    <thead className="bg-gray-50 text-gray-600 font-bold border-b">
                                        <tr>
                                            <th className="p-4">Raw Column</th>
                                            <th className="p-4 w-1/4">Business Label</th>
                                            <th className="p-4 w-1/4">AI Keywords / Synonyms</th>
                                            <th className="p-4">Format</th> 
                                            <th className="p-4 text-center">Date Filter?</th>
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
                                                    />
                                                </td>
                                                <td className="p-4">
                                                    <input
                                                        className="w-full border border-gray-300 rounded p-2 focus:border-blue-500 outline-none"
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
                                                    </select>
                                                </td>
                                                <td className="p-4 text-center">
                                                    <input type="checkbox" className="w-5 h-5" checked={m.is_default_date} onChange={e => handleMappingChange(idx, "is_default_date", e.target.checked)}/>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Part 2: UX Configuration */}
                        <div className="space-y-4">
                            <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                                <Save size={18} className="text-blue-500"/> Form UX & Data Integrity
                            </h3>
                            <div className="border rounded-xl">
                                <table className="w-full text-left text-sm">
                                    <thead className="bg-gray-50 text-gray-600 font-bold border-b">
                                        <tr>
                                            <th className="p-4">Field</th>
                                            <th className="p-4">Input Type</th>
                                            <th className="p-4">Storage</th>
                                            <th className="p-4">Dropdown Source</th>
                                            <th className="p-4 text-center">Req?</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y">
                                        {fieldMeta.map((meta, idx) => {
                                            const link = rels.find(r => 
                                                (r.parent_table === selectedTable && r.parent_column === meta.column_name) ||
                                                (r.child_table === selectedTable && r.child_column === meta.column_name)
                                            );
                                            const sourceTable = link ? (link.parent_table === selectedTable ? link.child_table : link.parent_table) : null;
                                            const samples = sourceTable ? sampleData[sourceTable] : null;

                                            return (
                                                <tr key={idx}>
                                                    <td className="p-4 font-bold">{meta.label}</td>
                                                    <td className="p-4">
                                                        <select className="border rounded p-1" value={meta.input_type} onChange={e => handleMetaChange(idx, "input_type", e.target.value)}>
                                                            <option value="text">Text</option>
                                                            <option value="dropdown">Dropdown</option>
                                                            <option value="date">Date</option>
                                                            <option value="checkbox">Checkbox</option>
                                                            <option value="textarea">Textarea</option>
                                                            <option value="number">Number</option>
                                                        </select>
                                                    </td>
                                                    <td className="p-4">
                                                        <select className="border rounded p-1 text-xs" value={meta.storage_type} onChange={e => handleMetaChange(idx, "storage_type", e.target.value)}>
                                                            <option value="string">STRING</option>
                                                            <option value="integer">INTEGER</option>
                                                            <option value="float">FLOAT</option>
                                                            <option value="boolean">BOOLEAN</option>
                                                            <option value="date">DATE</option>
                                                        </select>
                                                    </td>
                                                    <td className="p-4">
                                                        {meta.input_type === 'dropdown' && sourceTable ? (
                                                            <div className="space-y-1">
                                                                <div className="flex items-center gap-1 text-[10px] text-blue-600 font-bold uppercase"><Link2 size={10}/> {sourceTable}</div>
                                                                <SearchableDropdown
                                                                    className="w-full"
                                                                    options={(link?.selected_columns || []).map(c => ({
                                                                        value: c,
                                                                        label: `${c} ${samples?.[c] ? `("${samples[c]}")` : ""}`
                                                                    }))}
                                                                    value={meta.display_column}
                                                                    onChange={(val) => handleMetaChange(idx, "display_column", val)}
                                                                    placeholder="Choose Label..."
                                                                />
                                                            </div>
                                                        ) : meta.input_type === 'dropdown' ? (
                                                            <span className="text-red-400 text-xs flex items-center gap-1"><AlertTriangle size={12}/> No Relationship</span>
                                                        ) : <span className="text-gray-300 italic">N/A</span>}
                                                    </td>
                                                    <td className="p-4 text-center">
                                                        <input type="checkbox" checked={meta.required} onChange={e => handleMetaChange(idx, "required", e.target.checked)}/>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="mt-6 flex justify-end">
                            <button
                                onClick={handleSave}
                                disabled={saving}
                                className="bg-blue-600 text-white px-8 py-3 rounded-xl font-bold flex items-center gap-2 hover:bg-blue-700 disabled:opacity-50 transition-all shadow-lg shadow-blue-200"
                            >
                                {saving ? <Loader2 size={18} className="animate-spin"/> : <Save size={18} />}
                                {saving ? "Saving..." : "Save Intelligence Layer"}   
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    </div>
  );
}
