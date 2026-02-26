import { useState, useEffect } from "react";
import { useAdmin } from "../context/AdminContext";
import { LayoutTemplate, Play, Save, Code, Loader2, Check, AlertTriangle } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { apiFetch } from "../utils/api";

interface SemanticColumn {
  table: string;
  column: string;
  label: string;
}

export default function ReportBuilder() {
  const { clientId, apiKey } = useAdmin();
  const navigate = useNavigate();
  const location = useLocation();
  
  // State
  const [reportName, setReportName] = useState("");
  const [baseTable, setBaseTable] = useState("");
  const [tables, setTables] = useState<string[]>([]); // Just names
  const [semanticColumns, setSemanticColumns] = useState<SemanticColumn[]>([]);
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]); // Labels
  const [dateColumn, setDateColumn] = useState<string>("");
  const [dateRange, setDateRange] = useState<string>("last_30_days");
  
  // Joins State
  const [relationships, setRelationships] = useState<any>({}); // The full graph
  const [joins, setJoins] = useState<string[]>([]); // Linear chain of table names

  // Outputs
  const [previewSql, setPreviewSql] = useState("");
  const [previewData, setPreviewData] = useState<any[]>([]); 
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);

  // 0. Check for Edit Mode (Load from State)
  useEffect(() => {
      if (location.state?.report) {
          const report = location.state.report;
          const def = report.builder_definition || {}; // Guard for old reports
          
          setReportName(report.display_name);
          if (def.base_table) setBaseTable(def.base_table);
          if (def.columns) setSelectedColumns(def.columns);
          if (def.date_filter) {
              setDateColumn(def.date_filter.column);
              setDateRange(def.date_filter.range);
          }
          if (def.joins) setJoins(def.joins);
      }
  }, [location.state]);

  const API_BASE = import.meta.env.DEV ? "http://localhost:8000/api" : "/api";

  const showMessage = (type: "success" | "error", text: string) => {
      setMessage({ type, text });
      setTimeout(() => setMessage(null), 5000);
  };

  // 1. Fetch Schema (Semantic) & Relationships
  useEffect(() => {
    if (!apiKey) return;
    
    const fetchData = async () => {
        setLoading(true);
        try {
            // Fetch Schema
            const schemaRes = await apiFetch(`${API_BASE}/v2/semantic/schema`, {
                headers: { "X-API-Key": apiKey }
            });
            if (schemaRes.ok) {
                const data = await schemaRes.json();
                const uniqueTables = Array.from(new Set(data.map((m: any) => m.table_name))) as string[];
                setTables(uniqueTables);
                setSemanticColumns(data.map((m: any) => ({
                    table: m.table_name,
                    column: m.column_name,
                    label: m.label
                })));
            }

            // Fetch Relationships
            const relRes = await apiFetch(`${API_BASE}/v2/builder/relationships`, {
                headers: { "X-API-Key": apiKey }
            });
            if (relRes.ok) {
                const data = await relRes.json();
                setRelationships(data.graph || {});
            }
        } catch (err) {
            console.error("Failed to fetch data", err);
        } finally {
            setLoading(false);
        }
    };
    fetchData();
  }, [apiKey]);

  // Handle Preview
  const handlePreview = async () => {
      if (!baseTable || selectedColumns.length === 0) return showMessage("error", "Select base table and columns");
      setPreviewLoading(true);
      setPreviewSql("");
      setPreviewData([]);
      
      try {
          const payload = {
              client_id: clientId,
              request: {
                  base_table: baseTable,
                  columns: selectedColumns,
                  date_filter: dateColumn ? { column: dateColumn, range: dateRange } : undefined,
                  joins: joins
              }
          };

          const res = await apiFetch(`${API_BASE}/v2/builder/preview/data`, {
              method: "POST",
              headers: { 
                  "Content-Type": "application/json",
                  "X-API-Key": apiKey!
              },
              body: JSON.stringify(payload)
          });
          
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || "Preview failed");
          
          setPreviewSql(data.sql);
          setPreviewData(data.data || []);
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setPreviewLoading(false);
      }
  };

  // Handle Save
  const handleSave = async () => {
      if (!reportName) return showMessage("error", "Please enter a report name");
      if (!previewSql) return showMessage("error", "Please preview the report first");
      setSaving(true);
      
      try {
           const payload = {
              client_id: clientId,
              report_name: reportName,
              builder_definition: {
                  base_table: baseTable,
                  columns: selectedColumns,
                  date_filter: dateColumn ? { column: dateColumn, range: dateRange } : undefined,
                  joins: joins
              }
          };

          const res = await apiFetch(`${API_BASE}/v2/builder/save`, {
              method: "POST",
              headers: { 
                  "Content-Type": "application/json",
                  "X-API-Key": apiKey!
              },
              body: JSON.stringify(payload)
          });
          
          if (!res.ok) throw new Error("Save failed");
          
          showMessage("success", "Report Saved Successfully!");
          // Redirect to reports page
          setTimeout(() => navigate("/admin/reports"), 1500);
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setSaving(false);
      }
  };

  const availableColumns = semanticColumns.filter(c => 
      c.table === baseTable || joins.includes(c.table)
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Configuration */}
        <div className="lg:col-span-1 space-y-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
                <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                    <LayoutTemplate size={20} className="text-purple-600"/> Report Config
                </h2>
                
                {/* Base Table */}
                <div className="mb-4">
                    <label className="block text-sm font-semibold text-gray-700 mb-2">1. Base Table</label>
                    <select 
                        className="w-full border p-2 rounded bg-white"
                        value={baseTable}
                        onChange={e => {
                            setBaseTable(e.target.value);
                            setSelectedColumns([]); // Reset
                        }}
                    >
                        <option value="">-- Select Table --</option>
                        {tables.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                </div>

                {/* Columns (Multi-select) */}
                <div className="mb-4">
                     <div className="flex justify-between items-center mb-2">
                        <label className="block text-sm font-semibold text-gray-700">2. Select Columns</label>
                        {availableColumns.length > 0 && (
                            <button 
                                onClick={() => {
                                    if (selectedColumns.length === availableColumns.length) setSelectedColumns([]);
                                    else setSelectedColumns(availableColumns.map(c => c.label));
                                }}
                                className="text-xs text-blue-600 font-medium hover:underline"
                            >
                                {selectedColumns.length === availableColumns.length ? "Deselect All" : "Select All"}
                            </button>
                        )}
                     </div>
                     <div className="border rounded-lg max-h-48 overflow-y-auto p-2">
                        {availableColumns.length === 0 && <p className="text-xs text-gray-400 p-2">Select a base table first.</p>}
                        {availableColumns.map(col => (
                            <label key={col.label} className="flex items-center gap-2 p-2 hover:bg-gray-50 rounded cursor-pointer">
                                <input 
                                    type="checkbox" 
                                    className="rounded text-purple-600 focus:ring-purple-500"
                                    checked={selectedColumns.includes(col.label)}
                                    onChange={e => {
                                        if (e.target.checked) setSelectedColumns([...selectedColumns, col.label]);
                                        else setSelectedColumns(selectedColumns.filter(c => c !== col.label));
                                    }}
                                />
                                <span className="text-sm font-medium">{col.label}</span>
                            </label>
                        ))}
                     </div>
                </div>

                 {/* Date Filter */}
                <div className="mb-4">
                     <label className="block text-sm font-semibold text-gray-700 mb-2">3. Date Filter (Optional)</label>
                     <select 
                        className="w-full border p-2 rounded bg-white mb-2"
                        value={dateColumn}
                        onChange={e => setDateColumn(e.target.value)}
                        disabled={!baseTable}
                     >
                         <option value="">-- No Date Filter --</option>
                         {availableColumns.map(col => <option key={col.label} value={col.label}>{col.label}</option>)}
                     </select>
                     
                     {dateColumn && (
                         <select 
                            className="w-full border p-2 rounded bg-white"
                            value={dateRange}
                            onChange={e => setDateRange(e.target.value)}
                         >
                             <option value="last_30_days">Last 30 Days</option>
                             <option value="last_7_days">Last 7 Days</option>
                             <option value="this_month">This Month</option>
                             <option value="today">Today</option>
                         </select>
                     )}
                </div>

                 {/* Join Selector */}
                 <div className="mb-4">
                      <label className="block text-sm font-semibold text-gray-700 mb-2">4. Add Related Data (Joins)</label>
                      <div className="space-y-2">
                          {joins.map((t, idx) => (
                              <div key={idx} className="flex items-center justify-between bg-purple-50 p-2 rounded border border-purple-100">
                                  <span className="text-xs font-bold text-purple-700 uppercase">{t}</span>
                                  <button 
                                      onClick={() => setJoins(joins.slice(0, idx))}
                                      className="text-red-500 hover:text-red-700"
                                  >
                                      &times;
                                  </button>
                              </div>
                          ))}
                          
                          {joins.length < 3 && (
                              <select 
                                  className="w-full border p-2 rounded bg-white text-sm"
                                  value=""
                                  onChange={e => {
                                      if (e.target.value) setJoins([...joins, e.target.value]);
                                  }}
                                  disabled={!baseTable}
                              >
                                  <option value="">+ Add Related Table...</option>
                                  {Object.keys(relationships[joins[joins.length - 1] || baseTable] || {}).map(t => (
                                      <option key={t} value={t}>{t}</option>
                                  ))}
                              </select>
                          )}
                      </div>
                 </div>

                <button 
                    onClick={handlePreview}
                    disabled={loading || !baseTable}
                    className="w-full bg-purple-600 text-white py-2 rounded-lg font-bold hover:bg-purple-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                >
                    {loading ? <Loader2 size={16} className="animate-spin"/> : <Play size={16}/>}
                    Generate Preview
                </button>
            </div>
        </div>

        {/* Right: Preview & Save */}
        <div className="lg:col-span-2 space-y-6">
             {message && (
                <div className={`p-4 rounded-lg flex items-center gap-3 ${message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                   {message.type === "success" ? <Check size={18}/> : <AlertTriangle size={18}/>}
                   {message.text}
                </div>
            )}

            {previewSql && (
                <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 animate-in fade-in slide-in-from-bottom-4 duration-500 flex flex-col h-full max-h-[600px]">
                    <div className="flex justify-between items-center mb-4 flex-shrink-0">
                        <div className="flex items-center gap-4">
                            <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                                <Code size={20} className="text-slate-500"/> Generated SQL
                            </h2>
                            <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded font-mono border border-green-200 flex items-center gap-1">
                                <Check size={10} /> Deterministic
                            </span>
                        </div>
                        {/* 4. Joins Section */}
                        <div className="space-y-4 pt-4 border-t border-gray-100">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                                    4. Add Related Data (Joins)
                                </h3>
                                <button 
                                    onClick={async () => {
                                        if (!confirm("This will re-scan the database for relationships. Continue?")) return;
                                        try {
                                            const res = await apiFetch(`${import.meta.env.VITE_API_URL}/v2/builder/reset-cache`, {
                                                method: 'POST',
                                                headers: { 'X-API-Key': apiKey || "" }
                                            });
                                            if (res.ok) {
                                                // Re-fetch relationships
                                                const relRes = await apiFetch(`${import.meta.env.VITE_API_URL}/v2/builder/relationships?client_id=${clientId}`, {
                                                    headers: { 'X-API-Key': apiKey || "" }
                                                });
                                                const relData = await relRes.json();
                                                if (relData.status === 'success') {
                                                    setRelationships(relData.graph);
                                                    alert("Relationships refreshed successfully!");
                                                }
                                            }
                                        } catch (e) {
                                            console.error(e);
                                            alert("Failed to refresh relationships");
                                        }
                                    }}
                                    className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                                >
                                    Force Refresh
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div className="bg-slate-900 rounded-lg p-4 mb-6 flex-shrink-0">
                        <pre className="text-green-300 font-mono text-sm leading-relaxed overflow-x-auto">{previewSql}</pre>
                    </div>

                    {/* Data Results Table */}
                    <div className="flex-1 flex flex-col min-h-0 border rounded-xl overflow-hidden shadow-sm">
                        <div className="bg-gray-50 border-b px-4 py-2 flex justify-between items-center">
                             <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">Data Preview (Limit 50)</span>
                             <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{previewData.length} Rows</span>
                        </div>
                        <div className="overflow-auto bg-white flex-1 relative">
                             {previewLoading ? (
                                 <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
                                     <Loader2 className="animate-spin text-purple-600" size={32}/>
                                 </div>
                             ) : previewData.length > 0 ? (
                                <table className="w-full text-left text-sm whitespace-nowrap">
                                    <thead className="bg-gray-50 sticky top-0 z-10 text-gray-700 font-semibold shadow-sm">
                                        <tr>
                                            {Object.keys(previewData[0]).map(key => (
                                                <th key={key} className="p-3 border-r last:border-r-0 border-b">{key}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100">
                                        {previewData.map((row, i) => (
                                            <tr key={i} className="hover:bg-blue-50/30 transition-colors">
                                                {Object.values(row).map((val: any, j) => (
                                                    <td key={j} className="p-3 border-r last:border-r-0 max-w-xs overflow-hidden text-ellipsis text-gray-600">
                                                        {val === null ? <span className="text-gray-300 italic">null</span> : String(val)}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                             ) : (
                                 <div className="flex items-center justify-center h-full text-gray-400 italic">No data returned</div>
                             )}
                        </div>
                    </div>

                    <div className="border-t pt-6 mt-6 flex-shrink-0">
                        <h3 className="text-md font-bold mb-4">Save Report</h3>
                        <div className="flex gap-4">
                            <input 
                                className="flex-1 border p-3 rounded-lg focus:ring-2 focus:ring-purple-200 outline-none"
                                placeholder="Report Name (e.g. Monthly Revenue)"
                                value={reportName}
                                onChange={e => setReportName(e.target.value)}
                            />
                            <button 
                                onClick={handleSave}
                                disabled={saving || !reportName}
                                className="bg-emerald-600 text-white px-6 py-3 rounded-lg font-bold hover:bg-emerald-700 flex items-center gap-2 disabled:opacity-50 transition-all shadow-lg shadow-emerald-200"
                            >
                                {saving ? <Loader2 size={18} className="animate-spin"/> : <Save size={18}/>}
                                Save to Library
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {!previewSql && !loading && (
                <div className="h-64 border-2 border-dashed border-gray-200 rounded-xl flex items-center justify-center text-gray-400">
                    <p>Configure options and click "Generate Preview" to see results.</p>
                </div>
            )}
        </div>
    </div>
  );
}
