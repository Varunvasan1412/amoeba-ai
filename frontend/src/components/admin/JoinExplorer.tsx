import React, { useState, useMemo } from 'react';
import { 
  Database, ArrowRight, Check, Link2, Plus, 
  Trash2, Layers, ArrowLeftRight, Search, AlertCircle, Hash,
  GitCommit, ChevronRight, X, Loader2, ArrowDown
} from 'lucide-react';
import { apiFetch } from '../../utils/api';
import { SearchableDropdown } from './SearchableDropdown';

interface Relationship {
  id: number;
  parent_table: string;
  parent_column: string;
  child_table: string;
  child_column: string;
  is_enabled: boolean;
  selected_columns: string[];
}

interface ChainStep {
    sourceTable: string;
    sourceCol: string;
    targetTable: string;
    targetCol: string;
    selectedColumns: string[];
}

interface JoinExplorerProps {
  rels: Relationship[];
  schemaData: any[];
  apiKey: string | null;
  onRefresh: () => void;
}

export const JoinExplorer: React.FC<JoinExplorerProps> = ({ rels, schemaData, apiKey, onRefresh }) => {
    // Mode State
    const [mode, setMode] = useState<'single' | 'chain'>('single');

    // Selection State (Single)
    const [tableA, setTableA] = useState('');
    const [colA, setColA] = useState('');
    const [tableB, setTableB] = useState('');
    const [colB, setColB] = useState('');
    const [pulledData, setPulledData] = useState<string[]>([]);
    const [saving, setSaving] = useState(false);
    
    // Selection State (Chain)
    const [chain, setChain] = useState<ChainStep[]>([
        { sourceTable: '', sourceCol: '', targetTable: '', targetCol: '', selectedColumns: [] }
    ]);

    // Management State
    const [filterTable, setFilterTable] = useState<string>('All');
    const [searchTerm, setSearchTerm] = useState('');

    // Shared Logic
    const allTables = useMemo(() => Array.from(new Set(schemaData.map(s => s.table_name))).sort(), [schemaData]);
    const getColsForTable = (table: string) => schemaData.filter(s => s.table_name === table).map(s => s.column_name).sort();
    
    const colsA = useMemo(() => getColsForTable(tableA), [tableA, schemaData]);
    const colsB = useMemo(() => getColsForTable(tableB), [tableB, schemaData]);

    const tablesWithRels = useMemo(() => {
        const set = new Set(rels.map(r => r.parent_table));
        return ['All', ...Array.from(set).sort()];
    }, [rels]);

    const filteredRels = useMemo(() => {
        return rels.filter(r => {
            const matchesTable = filterTable === 'All' || r.parent_table === filterTable;
            const matchesSearch = r.child_table.toLowerCase().includes(searchTerm.toLowerCase()) || 
                                r.parent_table.toLowerCase().includes(searchTerm.toLowerCase());
            return matchesTable && matchesSearch;
        });
    }, [rels, filterTable, searchTerm]);

    const handleSaveSingle = async () => {
        if (!tableA || !colA || !tableB || !colB || !apiKey) {
            alert("Please complete the connection details.");
            return;
        }
        setSaving(true);
        try {
            const API_BASE = import.meta.env.VITE_API_URL || "";
            const res = await apiFetch(`${API_BASE}/api/v2/relationships`.replace(/\/\//g, '/').replace(':/', '://'), {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
                body: JSON.stringify({
                    parent_table: tableA,
                    parent_column: colA,
                    child_table: tableB,
                    child_column: colB
                })
            });

            if (!res.ok) throw new Error("Failed to create link");
            const data = await res.json();
            
            if (data.id && pulledData.length > 0) {
                await apiFetch(`${API_BASE}/api/v2/relationships/${data.id}/columns`.replace(/\/\//g, '/').replace(':/', '://'), {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
                    body: JSON.stringify({ columns: pulledData })
                });
            }

            setTableA(''); setColA(''); setTableB(''); setColB(''); setPulledData([]);
            onRefresh();
            alert("Connection Saved!");
        } catch (err: any) {
            alert(err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleSaveChain = async () => {
        if (!apiKey) return;
        setSaving(true);
        try {
            const API_BASE = import.meta.env.VITE_API_URL || "";
            for (const step of chain) {
                if (!step.sourceTable || !step.targetTable || !step.sourceCol || !step.targetCol) continue;
                
                // 1. Create Rel
                const res = await apiFetch(`${API_BASE}/api/v2/relationships`.replace(/\/\//g, '/').replace(':/', '://'), {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
                    body: JSON.stringify({
                        parent_table: step.sourceTable,
                        parent_column: step.sourceCol,
                        child_table: step.targetTable,
                        child_column: step.targetCol
                    })
                });
                
                if (!res.ok) continue;
                const data = await res.json();

                // 2. Save Columns (Payload)
                if (data.id && step.selectedColumns.length > 0) {
                    await apiFetch(`${API_BASE}/api/v2/relationships/${data.id}/columns`.replace(/\/\//g, '/').replace(':/', '://'), {
                        method: "POST",
                        headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
                        body: JSON.stringify({ columns: step.selectedColumns })
                    });
                }
            }
            setChain([{ sourceTable: '', sourceCol: '', targetTable: '', targetCol: '', selectedColumns: [] }]);
            setMode('single');
            onRefresh();
            alert("Chain Established!");
        } catch (err: any) {
            alert(err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!apiKey || !confirm("Are you sure you want to delete this connection?")) return;
        try {
            const API_BASE = import.meta.env.VITE_API_URL || "";
            const res = await apiFetch(`${API_BASE}/api/v2/relationships/${id}`.replace(/\/\//g, '/').replace(':/', '://'), {
                method: "DELETE",
                headers: { "X-API-Key": apiKey }
            });
            if (res.ok) {
                onRefresh();
            }
        } catch (err) {}
    };

    const updateChainStep = (index: number, data: Partial<ChainStep>) => {
        const newChain = [...chain];
        newChain[index] = { ...newChain[index], ...data };
        setChain(newChain);
    };

    const addChainStep = () => {
        const last = chain[chain.length - 1];
        setChain([...chain, { 
            sourceTable: last.targetTable, 
            sourceCol: '', 
            targetTable: '', 
            targetCol: '', 
            selectedColumns: [] 
        }]);
    };

    const removeChainStep = (index: number) => {
        if (chain.length === 1) return;
        setChain(chain.filter((_, i) => i !== index));
    };

    const handleSwap = () => {
        const tempTable = tableA;
        const tempCol = colA;
        setTableA(tableB);
        setColA(colB);
        setTableB(tempTable);
        setColB(tempCol);
        setPulledData([]); // Reset pulled data as the target table changed
    };

    return (
        <div className="flex flex-col h-full bg-[#f8fafc] font-sans">
            
            {/* --- BUILDER TOGGLE --- */}
            <div className="bg-white border-b border-slate-200 px-8 py-4">
                <div className="max-w-6xl mx-auto flex items-center justify-between">
                    <div className="flex bg-slate-100 p-1 rounded-xl">
                        <button onClick={() => setMode('single')} className={`px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${mode === 'single' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-400'}`}>Single Link</button>
                        <button onClick={() => setMode('chain')} className={`px-4 py-2 rounded-lg text-[10px] font-black uppercase tracking-widest transition-all ${mode === 'chain' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-400'}`}>Multi-Table Chain</button>
                    </div>
                </div>
            </div>

            {/* --- BUILDER PANEL --- */}
            <div className="p-8 bg-white border-b border-slate-200">
                <div className="max-w-6xl mx-auto">
                    
                    {mode === 'single' ? (
                        <>
                            <div className="flex items-center gap-3 mb-8">
                                <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-100">
                                    <Plus size={20} strokeWidth={3} />
                                </div>
                                <h2 className="text-2xl font-black text-slate-900 tracking-tight">Create Data Connection</h2>
                            </div>

                            <div className="flex flex-col lg:flex-row gap-6 items-start animate-in fade-in slide-in-from-top-2">
                                <div className="flex-1 w-full bg-slate-50 p-5 rounded-2xl border border-slate-200 space-y-3">
                                    <div>
                                        <label className="text-[10px] font-black text-indigo-600 uppercase tracking-widest block mb-1">1. Reference Table (Master Data)</label>
                                        <p className="text-[9px] text-slate-400 mb-2 italic">The source of truth (e.g. Employee Types, Categories, Products)</p>
                                    </div>
                                    <SearchableDropdown
                                        options={allTables.map(t => ({ value: t, label: t }))}
                                        value={tableA}
                                        onChange={val => { setTableA(val); setColA(''); }}
                                        placeholder="Select Master Table..."
                                    />
                                    <div className="pt-1">
                                        <label className="text-[9px] font-bold text-slate-500 uppercase block mb-1">Primary Key (usually 'id')</label>
                                        <SearchableDropdown
                                            options={colsA.map(c => ({ value: c, label: c }))}
                                            value={colA}
                                            onChange={val => setColA(val)}
                                            disabled={!tableA}
                                            placeholder="Select ID Column..."
                                        />
                                    </div>
                                </div>

                                <div className="hidden lg:flex flex-col items-center justify-center pt-12">
                                    <button 
                                        onClick={handleSwap}
                                        title="Swap Sides"
                                        className="p-3 bg-white border border-slate-200 rounded-full text-slate-400 hover:text-indigo-600 hover:border-indigo-200 hover:shadow-lg transition-all active:scale-95"
                                    >
                                        <ArrowLeftRight size={20} />
                                    </button>
                                </div>

                                <div className="flex-1 w-full bg-slate-50 p-5 rounded-2xl border border-slate-200 space-y-3">
                                    <div>
                                        <label className="text-[10px] font-black text-blue-600 uppercase tracking-widest block mb-1">2. Connecting Table (Transactional)</label>
                                        <p className="text-[9px] text-slate-400 mb-2 italic">The table that refers to the master (e.g. Employee, Sales, Orders)</p>
                                    </div>
                                    <SearchableDropdown
                                        options={allTables.map(t => ({ value: t, label: t }))}
                                        value={tableB}
                                        onChange={val => { setTableB(val); setColB(''); setPulledData([]); }}
                                        placeholder="Select Connecting Table..."
                                    />
                                    <div className="pt-1">
                                        <label className="text-[9px] font-bold text-slate-500 uppercase block mb-1">Linking Column (The Foreign Key)</label>
                                        <SearchableDropdown
                                            options={colsB.map(c => ({ value: c, label: c }))}
                                            value={colB}
                                            onChange={val => setColB(val)}
                                            disabled={!tableB}
                                            placeholder="Select Link Column..."
                                        />
                                    </div>
                                </div>

                                <div className="flex-1 w-full bg-indigo-50/50 p-5 rounded-2xl border border-indigo-100">
                                    <div>
                                        <label className="text-[10px] font-black text-indigo-500 uppercase tracking-widest block mb-1">3. Data to Pull for Chat Selection</label>
                                        <p className="text-[9px] text-slate-400 mb-2 italic">Select the columns you want to show as labels in the chat (e.g. Name, Description)</p>
                                    </div>
                                    {tableB ? (
                                        <div className="max-h-[80px] overflow-y-auto flex flex-wrap gap-1.5 pr-2 scrollbar-thin bg-white/50 p-2 rounded-xl">
                                            {colsB.map(col => {
                                                const isSelected = pulledData.includes(col);
                                                return (
                                                    <button key={col} onClick={() => setPulledData(prev => isSelected ? prev.filter(c => c !== col) : [...prev, col])} className={`px-2 py-1 rounded-lg border text-[9px] font-bold transition-all ${isSelected ? 'bg-indigo-600 border-indigo-600 text-white shadow-sm' : 'bg-white border-slate-200 text-slate-500 hover:border-indigo-300'}`}>
                                                        {col}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    ) : <div className="h-[80px] flex flex-col items-center justify-center text-slate-300 bg-white/30 rounded-xl border-2 border-dashed border-slate-100"><Layers size={20} className="mb-1 opacity-20" /><span className="text-[9px] font-bold uppercase tracking-tighter">Choose Table First</span></div>}
                                    <button onClick={handleSaveSingle} disabled={!tableA || !colA || !tableB || !colB || saving} className="w-full mt-3 bg-slate-900 text-white py-3 rounded-xl font-bold hover:bg-black transition-all shadow-md flex items-center justify-center gap-2 disabled:opacity-30 text-xs">
                                        {saving ? <Plus size={16} className="animate-spin" /> : <Link2 size={16} />} Establish Connection
                                    </button>
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="animate-in fade-in slide-in-from-top-2">
                            <div className="flex items-center justify-between mb-8">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-100">
                                        <GitCommit size={20} strokeWidth={3} />
                                    </div>
                                    <h2 className="text-2xl font-black text-slate-900 tracking-tight">Multi-Table Path</h2>
                                </div>
                                <button onClick={handleSaveChain} disabled={saving || chain.some(s => !s.targetTable)} className="bg-indigo-600 text-white px-8 py-3 rounded-xl font-bold text-xs hover:bg-indigo-700 transition-all shadow-lg flex items-center gap-2 disabled:opacity-30">
                                    {saving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />} Save Path
                                </button>
                            </div>

                            <div className="space-y-4">
                                {chain.map((step, idx) => (
                                    <div key={idx} className="flex flex-col gap-3">
                                        <div className="flex flex-col lg:flex-row items-start gap-4 bg-slate-50/50 p-6 rounded-3xl border border-slate-100 relative group">
                                            {/* Step Header/Delete */}
                                            <div className="absolute -left-3 top-1/2 -translate-y-1/2 bg-white w-8 h-8 rounded-full border border-slate-200 flex items-center justify-center text-[10px] font-black text-slate-400 shadow-sm">{idx + 1}</div>
                                            
                                            {/* Source Table */}
                                            <div className="flex-1 w-full space-y-2">
                                                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest ml-1">Source</span>
                                                <SearchableDropdown
                                                    options={allTables.map(t => ({ value: t, label: t }))}
                                                    value={step.sourceTable}
                                                    onChange={val => updateChainStep(idx, { sourceTable: val, sourceCol: '' })}
                                                    placeholder="Select Table"
                                                />
                                                <SearchableDropdown
                                                    options={getColsForTable(step.sourceTable).map(c => ({ value: c, label: c }))}
                                                    value={step.sourceCol}
                                                    onChange={val => updateChainStep(idx, { sourceCol: val })}
                                                    disabled={!step.sourceTable}
                                                    placeholder="Select Column"
                                                />
                                            </div>

                                            <div className="lg:pt-10 text-slate-300"><ArrowRight size={16}/></div>

                                            {/* Target Table */}
                                            <div className="flex-1 w-full space-y-2">
                                                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest ml-1">Target</span>
                                                <SearchableDropdown
                                                    options={allTables.map(t => ({ value: t, label: t }))}
                                                    value={step.targetTable}
                                                    onChange={val => updateChainStep(idx, { targetTable: val, targetCol: '', selectedColumns: [] })}
                                                    placeholder="Select Table"
                                                />
                                                <SearchableDropdown
                                                    options={getColsForTable(step.targetTable).map(c => ({ value: c, label: c }))}
                                                    value={step.targetCol}
                                                    onChange={val => updateChainStep(idx, { targetCol: val })}
                                                    disabled={!step.targetTable}
                                                    placeholder="Select Column"
                                                />
                                            </div>

                                            {/* Data Puller for Target */}
                                            <div className="flex-1 w-full space-y-2">
                                                <span className="text-[9px] font-black text-indigo-400 uppercase tracking-widest ml-1">Extra Data from Target</span>
                                                {step.targetTable ? (
                                                    <div className="max-h-[80px] overflow-y-auto flex flex-wrap gap-1 bg-white p-2 rounded-xl border border-slate-200">
                                                        {getColsForTable(step.targetTable).map(col => {
                                                            const isSelected = step.selectedColumns.includes(col);
                                                            return (
                                                                <button key={col} onClick={() => {
                                                                    const next = isSelected ? step.selectedColumns.filter(c => c !== col) : [...step.selectedColumns, col];
                                                                    updateChainStep(idx, { selectedColumns: next });
                                                                }} className={`px-2 py-0.5 rounded text-[8px] font-bold border transition-all ${isSelected ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-slate-50 border-slate-100 text-slate-400 hover:border-indigo-200'}`}>
                                                                    {col}
                                                                </button>
                                                            );
                                                        })}
                                                    </div>
                                                ) : <div className="h-[80px] flex items-center justify-center border-2 border-dashed border-slate-100 rounded-xl text-slate-300 text-[8px] font-bold uppercase italic">Select Target to Pull Data</div>}
                                            </div>

                                            {chain.length > 1 && (
                                                <button onClick={() => removeChainStep(idx)} className="p-2 text-slate-300 hover:text-red-500 self-center"><Trash2 size={16}/></button>
                                            )}
                                        </div>
                                        {idx < chain.length - 1 && (
                                            <div className="flex justify-center -my-2 relative z-10">
                                                <div className="bg-indigo-100 text-indigo-600 rounded-full p-1 border-2 border-white"><ArrowDown size={12} /></div>
                                            </div>
                                        )}
                                    </div>
                                ))}

                                <button onClick={addChainStep} className="w-full py-4 border-2 border-dashed border-slate-100 rounded-3xl text-slate-300 hover:text-indigo-600 hover:border-indigo-100 hover:bg-indigo-50/20 transition-all text-[10px] font-black uppercase tracking-widest flex items-center justify-center gap-2">
                                    <Plus size={14}/> Add Link to Chain
                                </button>
                            </div>
                        </div>
                    )}

                </div>
            </div>

            {/* --- SMART CONSOLE --- */}
            <div className="flex-1 flex flex-col min-h-0">
                {/* Filter Bar */}
                <div className="px-8 pt-8 pb-4 bg-transparent">
                    <div className="max-w-6xl mx-auto">
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-lg font-black text-slate-800 tracking-tight flex items-center gap-2">
                                <Hash size={18} className="text-indigo-500" />
                                Connection Browser
                            </h3>
                            <div className="relative group">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={14} />
                                <input placeholder="Quick search..." className="pl-9 pr-4 py-2 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-700 w-48 focus:ring-4 focus:ring-indigo-50 outline-none transition-all" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
                            </div>
                        </div>

                        {/* Table Chips - THE SCROLL KILLER */}
                        <div className="flex items-center gap-2 overflow-x-auto pb-4 no-scrollbar">
                            {tablesWithRels.map(t => (
                                <button
                                    key={t}
                                    onClick={() => setFilterTable(t)}
                                    className={`
                                        px-4 py-2 rounded-full text-[10px] font-black uppercase tracking-widest whitespace-nowrap transition-all border
                                        ${filterTable === t 
                                            ? 'bg-indigo-600 border-indigo-600 text-white shadow-lg shadow-indigo-100' 
                                            : 'bg-white border-slate-200 text-slate-400 hover:border-indigo-300 hover:text-indigo-600'
                                        }
                                    `}
                                >
                                    {t} {t !== 'All' && <span className="ml-1 opacity-60">({rels.filter(r => r.parent_table === t).length})</span>}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Compact Data Area */}
                <div className="flex-1 overflow-auto px-8 pb-10">
                    <div className="max-w-6xl mx-auto">
                        <div className="bg-white rounded-[24px] border border-slate-200 shadow-sm overflow-hidden">
                            {filteredRels.length === 0 ? (
                                <div className="py-20 flex flex-col items-center justify-center text-slate-300">
                                    <AlertCircle size={40} className="mb-2 opacity-10" />
                                    <p className="font-bold uppercase tracking-widest text-[10px]">No links in this view</p>
                                </div>
                            ) : (
                                <table className="w-full text-left">
                                    <thead className="bg-slate-50 border-b border-slate-100">
                                        <tr>
                                            <th className="px-6 py-4 text-[9px] font-black text-slate-400 uppercase tracking-widest">Origin</th>
                                            <th className="px-6 py-4 text-[9px] font-black text-slate-400 uppercase tracking-widest">Target</th>
                                            <th className="px-6 py-4 text-[9px] font-black text-slate-400 uppercase tracking-widest">Data Pulled</th>
                                            <th className="px-6 py-4 text-[9px] font-black text-slate-400 uppercase tracking-widest text-right">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-50">
                                        {filteredRels.map(rel => (
                                            <tr key={rel.id} className="hover:bg-indigo-50/20 transition-colors group">
                                                <td className="px-6 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-400"><Database size={14} /></div>
                                                        <div>
                                                            <div className="text-xs font-black text-slate-800">{rel.parent_table}</div>
                                                            <div className="text-[9px] font-mono text-slate-400">{rel.parent_column}</div>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <ArrowRight size={12} className="text-slate-300" />
                                                        <div>
                                                            <div className="text-xs font-black text-slate-800">{rel.child_table}</div>
                                                            <div className="text-[9px] font-mono text-slate-400">{rel.child_column}</div>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <div className="flex flex-wrap gap-1">
                                                        {rel.selected_columns?.length > 0 ? (
                                                            rel.selected_columns.map(c => (
                                                                <span key={c} className="bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded text-[8px] font-bold border border-indigo-100 uppercase">{c}</span>
                                                            ))
                                                        ) : <span className="text-[8px] font-bold text-slate-300 uppercase tracking-tighter">None</span>}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 text-right">
                                                    <button onClick={() => handleDelete(rel.id)} className="p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"><Trash2 size={14} /></button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
