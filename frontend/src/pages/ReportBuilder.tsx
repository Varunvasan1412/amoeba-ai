import { useState, useEffect, useCallback, useRef } from "react";
import { useAdmin } from "../context/AdminContext";
import { 
  LayoutTemplate, Code, Loader2, Check,
  AlertTriangle, ArrowRight, ArrowLeft, Database, 
  Table, ChevronRight, Settings2, Eye, Rocket, GitBranch,
  GripVertical, X, Wand2
} from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { apiFetch } from "../utils/api";
import { JoinGraph } from "../components/admin/JoinGraph";
import { SearchableDropdown } from "../components/admin/SearchableDropdown";

interface SemanticColumn {
  table: string;
  column: string;
  label: string;
}

interface JoinDefinition {
  table: string;
  parent: string;
}

export default function ReportBuilder() {
  const { clientId, apiKey } = useAdmin();
  const navigate = useNavigate();
  const location = useLocation();
  
  const [step, setStep] = useState(1);
  const [reportName, setReportName] = useState("");
  const [baseTable, setBaseTable] = useState("");
  const [tables, setTables] = useState<string[]>([]);
  const [semanticColumns, setSemanticColumns] = useState<SemanticColumn[]>([]);
  const [selectedColumns, setSelectedColumns] = useState<{name: string, label: string}[]>([]);
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [dateColumn, setDateColumn] = useState<string>("");
  const [dateRange, setDateRange] = useState<string>("last_30_days");
  const [relationships, setRelationships] = useState<any>({});
  const [joins, setJoins] = useState<JoinDefinition[]>([]);
  const [previewSql, setPreviewSql] = useState("");
  const [previewData, setPreviewData] = useState<any[]>([]); 
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);

  const dragItem = useRef<number | null>(null);
  const dragOverItem = useRef<number | null>(null);

  useEffect(() => {
      if (location.state?.report) {
          const report = location.state.report;
          const def = report.builder_definition || {};
          setReportName(report.display_name);
          if (def.base_table) setBaseTable(def.base_table);
          if (def.columns) {
              const cols = def.columns.map((c: any) => {
                  if (typeof c === 'string') {
                      const cleanLabel = c.includes(':') ? c.split(':')[1] : c;
                      return { name: c, label: cleanLabel };
                  }
                  return c;
              });
              setSelectedColumns(cols);
          }
          if (def.date_filter) {
              setDateColumn(def.date_filter.column);
              setDateRange(def.date_filter.range);
          }
          if (def.joins) {
              const normalized = def.joins.map((j: any, i: number) => {
                  if (typeof j === 'string') {
                      return { table: j, parent: i === 0 ? def.base_table : def.joins[i-1] };
                  }
                  return j;
              });
              setJoins(normalized);
          }
      }
  }, [location.state]);

  const API_BASE = import.meta.env.DEV ? "/api" : "/api";

  const showMessage = (type: "success" | "error", text: string) => {
      setMessage({ type, text });
      setTimeout(() => setMessage(null), 5000);
  };

  // Sanitize labels to ensure they are clean by default (no table prefixes)
  useEffect(() => {
    if (selectedColumns.length > 0) {
        const hasDirtyLabel = selectedColumns.some(c => c.label.includes(':') && c.label === c.name);
        if (hasDirtyLabel) {
            setSelectedColumns(prev => prev.map(c => {
                if (c.label.includes(':') && c.label === c.name) {
                    return { ...c, label: c.label.split(':')[1] };
                }
                return c;
            }));
        }
    }
  }, [selectedColumns]);

  const handleAutoMap = useCallback(() => {
    console.log("🛠️ Starting Auto-Map...", { joins, hasRelationships: !!relationships });
    if (!relationships || joins.length === 0) return;

    const newSelected = [...selectedColumns];
    let count = 0;

    joins.forEach(join => {
        const relMeta = relationships[join.parent]?.[join.table];
        if (relMeta && relMeta.selected_columns && relMeta.selected_columns.length > 0) {
            console.log(`📍 Found ${relMeta.selected_columns.length} preset(s) for ${join.table}`);
            relMeta.selected_columns.forEach((colName: string) => {
                // Find the semantic label for this column in this table
                const semanticCol = semanticColumns.find(c => 
                    c.table.toLowerCase() === join.table.toLowerCase() && 
                    c.column.toLowerCase() === colName.toLowerCase()
                );
                
                if (semanticCol) {
                    const uniqueKey = `${join.table}:${semanticCol.label}`;
                    if (!newSelected.some(sc => sc.name === uniqueKey)) {
                        const cleanLabel = semanticCol.label.includes(':') ? semanticCol.label.split(':')[1] : semanticCol.label;
                        newSelected.push({ name: uniqueKey, label: cleanLabel });
                        count++;
                        console.log(`✅ Auto-selected: ${uniqueKey}`);
                    }
                } else {
                    console.warn(`⚠️ Could not find semantic metadata for ${join.table}.${colName}`);
                }
            });
        }
    });

    if (count > 0) {
        setSelectedColumns(newSelected);
        showMessage("success", `Auto-mapped ${count} fields from Governance!`);
    } else {
        showMessage("info" as any, "No new fields to map from Governance. Check your Relationship Governance 'Data Payload' settings.");
    }
  }, [joins, relationships, semanticColumns, selectedColumns]);

  useEffect(() => {
    if (!apiKey) return;
    const fetchData = async () => {
        try {
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
        }
    };
    fetchData();
  }, [apiKey]);

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
                  columns: selectedColumns, // Now sending objects!
                  date_filter: dateColumn ? { column: dateColumn, range: dateRange } : undefined,
                  joins: joins
              }
          };
          const res = await fetch(`/api/reports/build?client_id=${clientId}`, {
              method: "POST",
              headers: { "Content-Type": "application/json", "X-API-Key": apiKey! },
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

  const handleSave = async () => {
      if (!reportName) return showMessage("error", "Please enter a report name");
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
              headers: { "Content-Type": "application/json", "X-API-Key": apiKey! },
              body: JSON.stringify(payload)
          });
          if (!res.ok) throw new Error("Save failed");
          showMessage("success", "Report Saved Successfully!");
          setTimeout(() => navigate("/admin/reports"), 1500);
      } catch (err: any) {
          showMessage("error", err.message);
      } finally {
          setSaving(false);
      }
  };

  const handleDragStart = (e: React.DragEvent, index: number) => {
      dragItem.current = index;
      if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
      setTimeout(() => { if (e.target instanceof HTMLElement) e.target.classList.add("opacity-50", "scale-95"); }, 0);
  };

  const handleDragEnter = (e: React.DragEvent, index: number) => {
      e.preventDefault();
      dragOverItem.current = index;
      if (dragItem.current !== null && dragOverItem.current !== null && dragItem.current !== dragOverItem.current) {
          const newCols = [...selectedColumns];
          const draggedContent = newCols[dragItem.current];
          newCols.splice(dragItem.current, 1);
          newCols.splice(dragOverItem.current, 0, draggedContent);
          dragItem.current = dragOverItem.current;
          setSelectedColumns(newCols);
      }
  };

  const handleDragEnd = (e: React.DragEvent) => {
      dragItem.current = null;
      dragOverItem.current = null;
      if (e.target instanceof HTMLElement) e.target.classList.remove("opacity-50", "scale-95");
  };

  const activeTables = [baseTable, ...joins.map(j => j.table)].filter(Boolean);
  const availableColumns = semanticColumns.filter(c => activeTables.includes(c.table));
  const previewCols = selectedColumns.map(sc => sc.label);

  return (
    <div className="max-w-7xl mx-auto py-6 px-4">
        <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 mb-8">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
                        <LayoutTemplate className="text-purple-600" /> Report Builder
                    </h1>
                    <p className="text-sm text-gray-500">Design powerful business reports by connecting your data visually.</p>
                </div>
                <div className="flex gap-3">
                    {step > 1 && (
                        <button onClick={() => setStep(step - 1)} className="flex items-center gap-2 px-4 py-2 border rounded-xl hover:bg-gray-50 transition-colors font-medium text-gray-600">
                            <ArrowLeft size={18} /> Back
                        </button>
                    )}
                    {step === 1 && (
                        <button 
                            disabled={!baseTable}
                            onClick={() => setStep(2)}
                            className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all font-bold disabled:opacity-50 shadow-lg shadow-blue-100"
                        >
                            Select Fields <ArrowRight size={18} />
                        </button>
                    )}
                    {step === 2 && (
                        <button 
                            disabled={selectedColumns.length === 0}
                            onClick={() => { setStep(3); handlePreview(); }}
                            className="flex items-center gap-2 px-6 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700 transition-all font-bold shadow-lg shadow-purple-100"
                        >
                            Review & Launch <ArrowRight size={18} />
                        </button>
                    )}
                </div>
            </div>

            <div className="flex items-center gap-4 relative overflow-x-auto pb-2">
                {[
                    { id: 1, label: "Architecture", icon: Database },
                    { id: 2, label: "Field Mapping", icon: Settings2 },
                    { id: 3, label: "Launch", icon: Eye }
                ].map((s, idx) => (
                    <div key={s.id} className="flex items-center gap-2 shrink-0">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold transition-all ${
                            step === s.id ? "bg-purple-600 text-white shadow-lg shadow-purple-200" : 
                            step > s.id ? "bg-green-100 text-green-600" : "bg-gray-100 text-gray-400"
                        }`}>
                            {step > s.id ? <Check size={16} /> : s.id}
                        </div>
                        <span className={`text-sm font-bold ${step === s.id ? "text-gray-800" : "text-gray-400"}`}>{s.label}</span>
                        {idx < 2 && <ChevronRight size={16} className="text-gray-300 mx-2" />}
                    </div>
                ))}
            </div>
        </div>

        {step === 1 && (
            <div className="space-y-6 animate-in fade-in duration-500">
                <div className="bg-purple-50 p-6 rounded-3xl border border-purple-100 mb-2">
                    <h3 className="text-purple-900 font-bold flex items-center gap-2 mb-1 text-sm uppercase tracking-wider">
                        <GitBranch size={18} /> Step 1: Data Architecture
                    </h3>
                    <p className="text-purple-700 text-xs leading-relaxed max-w-2xl">
                        Define your data universe. Select a starting table and visually branch out to connect related information. 
                        This mindmap forms the structural backbone of your report and determines which fields will be available in the next step.
                    </p>
                </div>

                <div className="bg-white p-6 rounded-3xl border border-gray-100 shadow-sm">
                    <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                        <Database size={20} className="text-blue-500" /> 1. Select Starting Table
                    </h2>
                    <div className="max-w-md">
                        <SearchableDropdown
                            options={tables.map(t => ({ value: t, label: t }))}
                            value={baseTable}
                            onChange={val => {
                                setBaseTable(val);
                                setJoins([]);
                                setSelectedColumns([]);
                            }}
                            placeholder="-- Choose Base Table (e.g. Sales) --"
                        />
                    </div>
                </div>

                <div className="bg-white rounded-3xl border border-gray-100 shadow-sm">
                    <div className="p-6 border-b border-gray-50 flex justify-between items-center bg-slate-50/50">
                        <div>
                            <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                                <Table size={20} className="text-purple-500" /> 2. Map Relationships
                            </h2>
                            <p className="text-xs text-gray-500 mt-1">Click a table to branch out and explore related data.</p>
                        </div>
                        {joins.length > 0 && (
                            <button onClick={() => setJoins([])} className="text-xs font-bold text-red-500 uppercase hover:underline">Clear Map</button>
                        )}
                    </div>
                    <div className="h-[600px] relative">
                        {baseTable ? (
                            <JoinGraph 
                                baseTable={baseTable}
                                relationships={relationships}
                                onJoinsChange={setJoins}
                                initialJoins={joins}
                            />
                        ) : (
                            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 bg-slate-50/30">
                                <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mb-4 border border-slate-200 shadow-inner">
                                    <Database size={32} className="opacity-20" />
                                </div>
                                <p className="font-medium">Please select a base table above to begin.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        )}

        {step === 2 && (
            <div className="space-y-8 animate-in fade-in duration-500">
                    <div className="p-6 border-b border-gray-50 flex justify-between items-center bg-slate-50/50">
                        <div>
                            <h3 className="text-blue-900 font-bold flex items-center gap-2 mb-1 text-sm uppercase tracking-wider">
                                <Settings2 size={18} /> Step 2: Field Mapping
                            </h3>
                            <p className="text-blue-700 text-xs leading-relaxed max-w-2xl">
                                Pick your signals. Select the specific business fields you want to include in this report from each connected table. 
                            </p>
                        </div>
                        <button 
                            onClick={handleAutoMap}
                            className="bg-white text-purple-600 border-2 border-purple-100 px-6 py-2.5 rounded-2xl font-black text-[10px] uppercase tracking-widest hover:border-purple-500 hover:bg-purple-50 transition-all flex items-center gap-2 shadow-sm"
                        >
                            <Wand2 size={14} /> ✨ Auto-Map from Governance
                        </button>
                    </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {activeTables.map(tableName => {
                        const tableCols = semanticColumns.filter(c => c.table === tableName);
                        const allSelected = tableCols.every(c => selectedColumns.some(sc => sc.name === `${tableName}:${c.label}`));
                        const toggleTable = () => {
                            if (allSelected) {
                                setSelectedColumns(selectedColumns.filter(sc => !sc.name.startsWith(`${tableName}:`)));
                            } else {
                                const newQualified = tableCols
                                    .map(c => {
                                        const cleanLabel = c.label.includes(':') ? c.label.split(':')[1] : c.label;
                                        return { name: `${tableName}:${c.label}`, label: cleanLabel };
                                    })
                                    .filter(q => !selectedColumns.some(sc => sc.name === q.name));
                                setSelectedColumns([...selectedColumns, ...newQualified]);
                            }
                        };
                        return (
                            <div key={tableName} className="bg-white rounded-3xl border border-gray-100 shadow-sm overflow-hidden flex flex-col">
                                <div className="p-4 bg-slate-800 text-white flex justify-between items-center">
                                    <div className="flex items-center gap-2">
                                        <Table size={16} className="text-blue-400" />
                                        <span className="font-bold text-xs uppercase tracking-widest">{tableName}</span>
                                    </div>
                                    <button onClick={toggleTable} className={`text-[9px] font-black uppercase tracking-tighter px-2 py-1 rounded transition-colors ${allSelected ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30' : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30'}`}>
                                        {allSelected ? 'Deselect All' : 'Select All'}
                                    </button>
                                </div>
                                <div className="p-4 flex-1 max-h-[400px] overflow-y-auto space-y-1 bg-gray-50/30">
                                    {tableCols.map(col => {
                                        const uniqueKey = `${tableName}:${col.label}`;
                                        const isSelected = selectedColumns.some(c => c.name === uniqueKey);
                                        return (
                                            <label key={uniqueKey} className="flex items-center gap-3 p-3 hover:bg-white hover:shadow-md rounded-2xl cursor-pointer transition-all group border border-transparent hover:border-purple-100">
                                                <input type="checkbox" className="w-5 h-5 rounded-lg border-2 border-gray-200 text-purple-600 focus:ring-purple-500 transition-all" checked={isSelected} onChange={e => {
                                                    if (e.target.checked) {
                                                        const cleanLabel = col.label.includes(':') ? col.label.split(':')[1] : col.label;
                                                        setSelectedColumns(prev => [...prev, { name: uniqueKey, label: cleanLabel }]);
                                                    }
                                                    else setSelectedColumns(prev => prev.filter(c => c.name !== uniqueKey));
                                                }} />
                                                <div className="flex flex-col">
                                                    <span className="text-sm font-bold text-gray-700 group-hover:text-purple-700 transition-colors">{col.label}</span>
                                                    <span className="text-[10px] text-gray-400 font-mono">{col.column}</span>
                                                </div>
                                            </label>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
                </div>

                <div className="bg-white p-8 rounded-3xl border border-gray-100 shadow-sm">
                    <h2 className="text-lg font-bold text-gray-800 mb-6 flex items-center gap-2">
                        <ChevronRight size={20} className="text-orange-500" /> 3. Additional Filters (Optional)
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div>
                            <label className="block text-xs font-bold text-gray-400 uppercase mb-2">Time-Series Field</label>
                            <SearchableDropdown
                                options={availableColumns.map(col => ({
                                    value: `${col.table}:${col.label}`,
                                    label: `${col.table}: ${col.label}`
                                }))}
                                value={dateColumn}
                                onChange={val => setDateColumn(val)}
                                placeholder="-- No Date Filter --"
                            />
                        </div>
                            <div>
                                <label className="block text-xs font-bold text-gray-400 uppercase mb-2">Default Range</label>
                                <SearchableDropdown
                                    options={[
                                        { value: "last_30_days", label: "Last 30 Days" },
                                        { value: "last_7_days", label: "Last 7 Days" },
                                        { value: "this_month", label: "This Month" },
                                        { value: "today", label: "Today" }
                                    ]}
                                    value={dateRange}
                                    onChange={val => setDateRange(val)}
                                    placeholder="Select range..."
                                />
                            </div>
                    </div>
                </div>
            </div>
        )}

        {step === 3 && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-in fade-in duration-500">
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-emerald-50 p-6 rounded-3xl border border-emerald-100 mb-2">
                        <h3 className="text-emerald-900 font-bold flex items-center gap-2 mb-1 text-sm uppercase tracking-wider">
                            <Rocket size={18} /> Step 3: Deployment Console
                        </h3>
                        <p className="text-emerald-700 text-xs leading-relaxed max-w-2xl">
                            Final verification. Review your automatically optimized SQL and see a live preview of the results 
                            before "launching" this report to your organization. The name you give it here will be its identifier in the chat.
                        </p>
                    </div>

                    <div className="bg-slate-900 rounded-3xl p-6 shadow-xl relative group">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-sm font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                <Code size={16} /> Optimized SQL
                            </h2>
                            <span className="text-[10px] bg-green-500/20 text-green-400 px-2 py-1 rounded-lg font-bold border border-green-500/30">Verified Deterministic</span>
                        </div>
                        <pre className="text-green-300 font-mono text-xs leading-relaxed overflow-x-auto p-4 bg-black/30 rounded-2xl">
                            {previewSql || "-- SQL will be generated on preview..."}
                        </pre>
                    </div>

                    <div className="bg-white rounded-3xl border border-gray-100 shadow-sm overflow-hidden flex flex-col min-h-[400px]">
                        <div className="p-4 bg-gray-50 border-b flex justify-between items-center">
                            <span className="text-xs font-bold text-gray-500 uppercase">Live Data Preview</span>
                            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-bold">{previewData.length} Sample Rows</span>
                        </div>
                        <div className="flex-1 overflow-auto relative">
                            {previewLoading ? (
                                <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
                                    <Loader2 className="animate-spin text-purple-600" size={32}/>
                                </div>
                            ) : previewData.length > 0 ? (
                                 <table className="w-full text-left text-xs whitespace-nowrap">
                                     <thead className="bg-slate-50 sticky top-0 font-bold text-slate-600 border-b shadow-sm">
                                         <tr>{previewCols.map(col => (<th key={col} className="p-4 font-black uppercase tracking-wider">{col}</th>))}</tr>
                                     </thead>
                                    <tbody className="divide-y divide-gray-100">
                                        {previewData.map((row, i) => (
                                            <tr key={i} className="hover:bg-blue-50/30 transition-colors">
                                                {previewCols.map((col, j) => (<td key={j} className="p-4 text-gray-600">{row[col] === null || row[col] === undefined ? <span className="text-gray-300 italic font-mono">null</span> : String(row[col])}</td>))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : (
                                <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
                                    <AlertTriangle size={32} className="opacity-20" />
                                    <p className="italic text-sm">No data returned for this configuration.</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="lg:col-span-1">
                    <div className="bg-white p-8 rounded-3xl border border-gray-100 shadow-xl sticky top-6">
                        <div className="mb-8">
                            <h3 className="text-xl font-bold text-gray-800 mb-2">Deploy View</h3>
                            <p className="text-sm text-gray-500 leading-relaxed">Give your view a recognizable business name. It will be immediately available in the chat.</p>
                        </div>
                        <div className="space-y-6">
                            <div>
                                <label className="block text-xs font-bold text-gray-400 uppercase mb-2 ml-1">Business Display Name</label>
                                <input className="w-full border-2 border-gray-100 p-4 rounded-2xl focus:border-purple-500 outline-none transition-all font-bold text-lg shadow-sm bg-gray-50/50" placeholder="e.g. Monthly Revenue" value={reportName} onChange={e => setReportName(e.target.value)} />
                            </div>
                            <div className="p-5 bg-purple-50 rounded-2xl border border-purple-100 text-purple-700 space-y-3 shadow-sm">
                                <div className="flex justify-between text-[10px] font-bold uppercase tracking-widest opacity-60"><span>Deployment Summary</span></div>
                                <div className="space-y-1">
                                    <div className="text-xs font-medium flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-purple-400" /><strong>{selectedColumns.length}</strong> Semantic Fields</div>
                                    <div className="text-xs font-medium flex items-center gap-2"><div className="w-1.5 h-1.5 rounded-full bg-purple-400" /><strong>{activeTables.length}</strong> Tables Joined</div>
                                </div>
                            </div>

                            <div className="mt-6 mb-4">
                                <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3 ml-1">Column Order</label>
                                <div className="space-y-2 max-h-64 overflow-y-auto pr-2 custom-scrollbar">
                                    {selectedColumns.map((col, idx) => (
                                        <div 
                                            key={col.name} 
                                            draggable
                                            onDragStart={(e) => handleDragStart(e, idx)}
                                            onDragEnter={(e) => handleDragEnter(e, idx)}
                                            onDragEnd={handleDragEnd}
                                            onDragOver={(e) => e.preventDefault()}
                                            className="group flex items-center justify-between p-3 bg-gray-50 border border-gray-100 rounded-xl hover:border-purple-200 hover:bg-purple-50/30 transition-all cursor-move active:scale-95 shadow-sm"
                                        >
                                            <div className="flex items-center gap-3 overflow-hidden flex-1">
                                                <GripVertical size={14} className="text-gray-300 group-hover:text-purple-400 shrink-0" />
                                                <div className="flex flex-col flex-1 overflow-hidden">
                                                    <span className="text-[9px] font-bold text-gray-400 uppercase tracking-tighter truncate opacity-70 mb-0.5">{col.name}</span>
                                                    {editingIdx === idx ? (
                                                        <input 
                                                            autoFocus
                                                            className="w-full bg-white border border-purple-300 rounded px-2 py-0.5 text-xs font-bold outline-none text-purple-700 shadow-[0_0_10px_rgba(147,51,234,0.1)]"
                                                            value={col.label}
                                                            onChange={(e) => {
                                                                const newCols = [...selectedColumns];
                                                                newCols[idx].label = e.target.value;
                                                                setSelectedColumns(newCols);
                                                            }}
                                                            onBlur={() => setEditingIdx(null)}
                                                            onKeyDown={(e) => e.key === 'Enter' && setEditingIdx(null)}
                                                        />
                                                    ) : (
                                                        <div 
                                                            className="flex items-center gap-2 group/edit"
                                                            onDoubleClick={() => setEditingIdx(idx)}
                                                            title="Double click to rename Export Heading"
                                                        >
                                                            <span className="text-xs font-black text-purple-600 truncate cursor-text">
                                                                {col.label}
                                                            </span>
                                                            <Code size={10} className="text-purple-300 opacity-0 group-hover/edit:opacity-100 transition-opacity" />
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                            <button onClick={() => setSelectedColumns(prev => prev.filter(c => c.name !== col.name))} className="p-1 hover:bg-red-100 rounded-lg text-gray-300 hover:text-red-500 transition-colors ml-2">
                                                <X size={12}/>
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            {message && (
                                <div className={`p-4 rounded-2xl flex items-center gap-3 animate-in zoom-in-95 duration-200 border-2 ${message.type === "success" ? "bg-green-50 text-green-700 border-green-100" : "bg-red-50 text-red-700 border-red-100"}`}>
                                    {message.type === "success" ? <Check size={18} className="shrink-0"/> : <AlertTriangle size={18} className="shrink-0"/>}
                                    <span className="text-sm font-bold">{message.text}</span>
                                </div>
                            )}
                            <button onClick={handleSave} disabled={saving || !reportName} className="w-full bg-emerald-600 text-white py-5 rounded-2xl font-black hover:bg-emerald-700 transition-all shadow-xl shadow-emerald-100 text-lg uppercase tracking-widest flex items-center justify-center gap-3 disabled:opacity-50">
                                {saving ? <Loader2 size={24} className="animate-spin"/> : <Rocket size={24} className="animate-bounce" />}
                                {saving ? 'Deploying...' : 'Launch View'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        )}
    </div>
  );
}
