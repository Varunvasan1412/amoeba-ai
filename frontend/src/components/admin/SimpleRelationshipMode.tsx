import React, { useState, useMemo, useEffect } from 'react';
import { Check, X, Search, Database, Key, Link as LinkIcon, ArrowRight, ArrowDown, Loader2, ChevronRight, XCircle } from 'lucide-react';
import { apiFetch } from '../../utils/api';
import { toast } from 'react-toastify';
import { SearchableDropdown } from './SearchableDropdown';

interface Concept {
    database_table: string;
    ui_label: string;
    is_doubtful?: boolean;
}

interface Relationship {
    id: number;
    parent_table: string;
    child_table: string;
    parent_column: string;
    child_column: string;
    approval_status: string;
    is_enabled: boolean;
}

interface PhysicalSchema {
    [tableName: string]: {
        columns: {name: string, type: string}[];
        primary_keys: string[];
        foreign_keys: {
            constrained_columns: string[];
            referred_table: string;
            referred_columns: string[];
        }[];
    }
}

interface Props {
    allRels: Relationship[];
    appConcepts: Concept[];
    apiKey: string;
    onRefresh: () => void;
}

export const SimpleRelationshipMode: React.FC<Props> = ({ allRels, appConcepts, apiKey, onRefresh }) => {
    const [schema, setSchema] = useState<PhysicalSchema>({});
    const [search, setSearch] = useState('');
    const [selectedTable, setSelectedTable] = useState<string | null>(null);
    const [activeRel, setActiveRel] = useState<Relationship | null>(null);
    const [loadingSchema, setLoadingSchema] = useState(true);

    // Manual Investigation State
    const [investigateA, setInvestigateA] = useState('');
    const [investigateB, setInvestigateB] = useState('');
    const [candidates, setCandidates] = useState<any[]>([]);
    const [loadingCandidates, setLoadingCandidates] = useState(false);

    useEffect(() => {
        if (!apiKey) return;
        setLoadingSchema(true);
        apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/v2/relationships/physical-schema`, {
            headers: { 'X-API-Key': apiKey }
        })
        .then(res => res.json())
        .then(data => setSchema(data))
        .catch(err => console.error("Schema fetch error", err))
        .finally(() => setLoadingSchema(false));
    }, [apiKey]);

    const getConceptLabel = (tableName: string) => {
        const c = appConcepts.find(c => c.database_table === tableName);
        return c ? c.ui_label : 'Unmapped Concept';
    };

    const handleUpdateStatus = async (relId: number, status: string) => {
        try {
            const res = await apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/v2/relationships/${relId}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
                body: JSON.stringify({ status })
            });
            if (res.ok) {
                toast.success(`Relationship marked as ${status}`);
                setActiveRel(null);
                onRefresh();
            } else {
                toast.error("Failed to update status");
            }
        } catch (e: any) {
            toast.error(e.message);
        }
    };

    const handleManualInvestigate = async () => {
        if (!investigateA || !investigateB || !apiKey) return;
        setLoadingCandidates(true);
        try {
            const res = await apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/v2/relationships/candidates?table_a=${investigateA}&table_b=${investigateB}`, {
                headers: { 'X-API-Key': apiKey }
            });
            const data = await res.json();
            if (res.ok) {
                setCandidates(data);
                if (data.length === 0) toast.info("No candidates found between these tables.");
            } else {
                toast.error(data.detail || "Failed to find candidates.");
            }
        } catch (err: any) {
            toast.error(err.message);
        } finally {
            setLoadingCandidates(false);
        }
    };

    const handleCreateManual = async (candidate: any) => {
        try {
            const res = await apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/v2/relationships`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
                body: JSON.stringify({
                    parent_table: candidate.target_table, // target is usually the PK table, i.e. parent
                    parent_column: candidate.target_column,
                    child_table: candidate.source_table,  // source is the FK table, i.e. child
                    child_column: candidate.source_column
                })
            });
            if (res.ok) {
                toast.success("Relationship created successfully!");
                setInvestigateA('');
                setInvestigateB('');
                setCandidates([]);
                onRefresh();
            } else {
                const data = await res.json();
                toast.error(data.detail || "Failed to create relationship.");
            }
        } catch (err: any) {
            toast.error(err.message);
        }
    };

    const filteredTables = useMemo(() => {
        const query = search.toLowerCase();
        return Object.keys(schema).filter(t => {
            if (t.toLowerCase().includes(query)) return true;
            const cLabel = getConceptLabel(t).toLowerCase();
            if (cLabel.includes(query)) return true;
            return false;
        }).sort();
    }, [schema, search, appConcepts]);

    const conceptOptions = useMemo(() => {
        return Object.keys(schema).map(t => ({
            value: t,
            label: `${getConceptLabel(t)} (${t})`
        })).sort((a, b) => a.label.localeCompare(b.label));
    }, [schema, appConcepts]);

    return (
        <div className="bg-slate-50 rounded-3xl overflow-hidden border border-slate-200 flex flex-col">
            {/* Top Section: 3 Panes */}
            <div className="flex h-[600px] border-b border-slate-200">
                {/* Left Pane: Table List */}
            <div className="w-1/3 bg-white border-r border-slate-200 flex flex-col">
                <div className="p-4 border-b border-slate-200 bg-slate-50/50">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                        <input 
                            type="text" 
                            placeholder="Search tables or concepts..."
                            className="w-full pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto p-2">
                    {loadingSchema ? (
                        <div className="flex items-center justify-center h-full text-slate-400">
                            <Loader2 className="animate-spin" size={24} />
                        </div>
                    ) : filteredTables.length > 0 ? (
                        filteredTables.map(t => (
                            <div 
                                key={t} 
                                onClick={() => setSelectedTable(t)}
                                className={`p-3 mx-2 my-1 rounded-xl cursor-pointer transition-all flex items-center justify-between group ${selectedTable === t ? 'bg-indigo-50 border border-indigo-200 shadow-sm' : 'hover:bg-slate-50 border border-transparent'}`}
                            >
                                <div>
                                    <div className={`font-bold text-sm ${selectedTable === t ? 'text-indigo-900' : 'text-slate-700 group-hover:text-slate-900'}`}>{getConceptLabel(t)}</div>
                                    <div className="text-xs text-slate-500 font-mono mt-0.5">{t}</div>
                                </div>
                                <ChevronRight size={16} className={selectedTable === t ? 'text-indigo-400' : 'text-transparent group-hover:text-slate-300'} />
                            </div>
                        ))
                    ) : (
                        <div className="text-center p-6 text-sm text-slate-400">No tables found.</div>
                    )}
                </div>
            </div>

            {/* Middle Pane: Schema Explorer */}
            <div className="flex-1 flex flex-col bg-slate-50 relative overflow-hidden">
                {selectedTable && schema[selectedTable] ? (
                    <div className="absolute inset-0 overflow-y-auto p-8">
                        <div className="mb-8">
                            <h2 className="text-2xl font-black text-slate-800">{getConceptLabel(selectedTable)}</h2>
                            <p className="text-sm font-mono text-slate-500 flex items-center gap-2 mt-1">
                                <Database size={14} /> {selectedTable}
                            </p>
                        </div>

                        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-8">
                            <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 font-bold text-slate-700 text-sm flex items-center gap-2">
                                Schema & Active Relationships
                            </div>
                            <div className="p-5 font-mono text-sm overflow-x-auto">
                                <div className="text-slate-800 font-bold mb-3">{selectedTable}</div>
                                {schema[selectedTable].columns.map((col, idx) => {
                                    const isPk = schema[selectedTable].primary_keys.includes(col.name);
                                    
                                    // Find relationships where this column is the child (FK)
                                    const outRel = allRels.find(r => r.child_table === selectedTable && r.child_column === col.name);
                                    
                                    return (
                                        <div key={idx} className="flex items-start mb-2 group relative min-w-max">
                                            <div className="w-8 shrink-0 flex justify-end pr-2 text-slate-400">
                                                {isPk && <Key size={14} className="text-amber-500" />}
                                                {!isPk && outRel && <LinkIcon size={14} className="text-indigo-400" />}
                                            </div>
                                            <div className="flex-1 flex items-center gap-4">
                                                <div className="flex items-center">
                                                    <span className={`${isPk || outRel ? 'text-slate-800 font-medium' : 'text-slate-500'}`}>{col.name}</span>
                                                    <span className="text-slate-400 text-xs ml-3 shrink-0">{col.type}</span>
                                                </div>
                                                {/* Visual Connection mapping */}
                                                {outRel && (
                                                    <div className="flex items-center text-indigo-500 gap-2 opacity-70 group-hover:opacity-100 transition-opacity whitespace-nowrap ml-4">
                                                        <span className="text-indigo-400">──►</span>
                                                        <span className="font-bold text-indigo-700">{outRel.parent_table}.{outRel.parent_column}</span>
                                                        <button 
                                                            onClick={(e) => { e.stopPropagation(); setActiveRel(outRel); }}
                                                            className="ml-3 text-xs bg-indigo-50 text-indigo-600 px-2 py-1 rounded border border-indigo-100 font-sans cursor-pointer hover:bg-indigo-100 opacity-0 group-hover:opacity-100 transition-opacity"
                                                        >
                                                            Manage
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>
                ) : (

                    <div className="absolute inset-0 flex flex-col items-center justify-center p-8 text-center text-slate-400">
                        <Database size={48} className="mb-4 text-slate-200" strokeWidth={1} />
                        <h3 className="text-lg font-bold text-slate-600">Select a table to explore</h3>
                        <p className="text-sm max-w-sm mt-2">View the database schema, primary keys, and foreign key connections visually.</p>
                    </div>
                )}
            </div>

            {/* Right Pane: Manual Investigation */}
            <div className="w-1/3 bg-white border-l border-slate-200 flex flex-col">
                <div className="p-5 border-b border-slate-200 bg-slate-50/50">
                    <h3 className="font-black text-slate-800 flex items-center gap-2"><Search size={16} className="text-indigo-500" /> Manual Investigation</h3>
                    <p className="text-xs text-slate-500 mt-1">Investigate specific pairs of tables.</p>
                </div>
                
                <div className="p-5 space-y-4 border-b border-slate-100">
                    <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1.5 block">Table A</label>
                        <SearchableDropdown
                            options={conceptOptions}
                            value={investigateA}
                            onChange={setInvestigateA}
                            placeholder="Select Table A"
                        />
                    </div>
                    <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1.5 block">Table B</label>
                        <SearchableDropdown
                            options={conceptOptions}
                            value={investigateB}
                            onChange={setInvestigateB}
                            placeholder="Select Table B"
                        />
                    </div>
                    <button 
                        onClick={handleManualInvestigate}
                        disabled={loadingCandidates || !investigateA || !investigateB}
                        className="w-full py-2.5 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-200 rounded-xl font-bold text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2"
                    >
                        {loadingCandidates ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />} Find Candidates
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-5 bg-slate-50">
                    {candidates.length > 0 ? (
                        <div className="space-y-4">
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Candidate Connections</h4>
                            {candidates.map((c, i) => (
                                <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm text-sm">
                                    <div className="flex flex-col gap-2 font-mono text-xs mb-3 bg-slate-50 p-2 rounded-lg border border-slate-100">
                                        <div className="text-slate-600">{c.source_table}.<span className="font-bold text-slate-800">{c.source_column}</span></div>
                                        <div className="flex justify-center text-indigo-400"><ArrowRight size={14}/></div>
                                        <div className="text-slate-600">{c.target_table}.<span className="font-bold text-slate-800">{c.target_column}</span></div>
                                    </div>
                                    <div className="text-xs text-slate-500 mb-3 flex items-center gap-1">
                                        Method: <span className="font-semibold text-slate-700 capitalize">{c.method || 'Explicit FK'}</span>
                                    </div>
                                    <button 
                                        onClick={() => handleCreateManual(c)}
                                        className="w-full py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-lg font-bold text-xs transition-colors"
                                    >
                                        Use Connection
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center text-slate-400 text-xs py-8">
                            Select two tables and search to find potential connections.
                        </div>
                    )}
                </div>
            </div>
            </div>

            {/* Bottom Section: Full Width Relationships */}
            {selectedTable && schema[selectedTable] && (allRels.filter(r => r.child_table === selectedTable).length > 0 || allRels.filter(r => r.parent_table === selectedTable).length > 0) && (
                <div className="p-8 bg-white min-h-[300px]">
                    <h3 className="text-xl font-black text-slate-800 mb-6 flex items-center gap-2">
                        <LinkIcon size={20} className="text-indigo-500" /> Connections for {getConceptLabel(selectedTable)}
                    </h3>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        {/* Forward Relationships (Outgoing) */}
                        {allRels.filter(r => r.child_table === selectedTable).length > 0 && (
                            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden h-fit">
                                <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 font-bold text-slate-700 text-sm flex items-center gap-2">
                                    Outgoing Relationships (FKs)
                                </div>
                                <div className="p-6 font-mono text-sm grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    {allRels.filter(r => r.child_table === selectedTable).map(r => (
                                        <div key={r.id} className="group flex flex-col p-5 border border-slate-100 rounded-xl bg-slate-50/50 hover:bg-slate-50 transition-colors shadow-sm">
                                            <div className="flex-1 flex flex-col justify-center">
                                                <div className="text-slate-800 font-bold truncate" title={`${selectedTable}.${r.child_column}`}>
                                                    {selectedTable}.{r.child_column}
                                                </div>
                                                <div className="text-indigo-400 my-2 flex justify-center">
                                                    <ArrowDown size={16} />
                                                </div>
                                                <div className="text-slate-500 truncate" title={`${r.parent_table}.${r.parent_column}`}>
                                                    {r.parent_table}.<span className="font-bold text-slate-700">{r.parent_column}</span>
                                                </div>
                                            </div>
                                            <button 
                                                onClick={() => setActiveRel(r)}
                                                className="mt-4 w-full py-2 text-xs bg-white text-indigo-600 rounded-lg border border-indigo-200 font-sans font-bold cursor-pointer hover:bg-indigo-50 shadow-sm transition-colors"
                                            >
                                                Manage
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Reverse Relationships (Incoming) */}
                        {allRels.filter(r => r.parent_table === selectedTable).length > 0 && (
                            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden h-fit">
                                <div className="px-5 py-3 border-b border-slate-100 bg-slate-50 font-bold text-slate-700 text-sm flex items-center gap-2">
                                    Incoming Relationships
                                </div>
                                <div className="p-6 font-mono text-sm grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    {allRels.filter(r => r.parent_table === selectedTable).map(r => (
                                        <div key={r.id} className="group flex flex-col p-5 border border-slate-100 rounded-xl bg-slate-50/50 hover:bg-slate-50 transition-colors shadow-sm">
                                            <div className="flex-1 flex flex-col justify-center">
                                                <div className="text-slate-500 truncate" title={`${r.child_table}.${r.child_column}`}>
                                                    {r.child_table}.<span className="font-bold text-slate-700">{r.child_column}</span>
                                                </div>
                                                <div className="text-indigo-400 my-2 flex justify-center">
                                                    <ArrowDown size={16} />
                                                </div>
                                                <div className="text-slate-800 font-bold truncate" title={`${selectedTable}.${r.parent_column}`}>
                                                    {selectedTable}.{r.parent_column}
                                                </div>
                                            </div>
                                            <button 
                                                onClick={() => setActiveRel(r)}
                                                className="mt-4 w-full py-2 text-xs bg-white text-indigo-600 rounded-lg border border-indigo-200 font-sans font-bold cursor-pointer hover:bg-indigo-50 shadow-sm transition-colors"
                                            >
                                                Manage
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Detail Panel Modal (over everything) */}
            {activeRel && (
                <div className="fixed inset-0 z-[120] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6 animate-in fade-in">
                    <div className="bg-white w-full max-w-xl rounded-3xl shadow-2xl overflow-hidden border border-slate-100 flex flex-col">
                        <div className="p-6 border-b border-slate-50 flex justify-between items-center bg-slate-50/50">
                            <h3 className="text-lg font-black text-slate-800 flex items-center gap-2">
                                <LinkIcon size={18} className="text-indigo-500" /> Connection Approval
                            </h3>
                            <button onClick={() => setActiveRel(null)} className="p-2 hover:bg-slate-200 rounded-xl text-slate-400 transition-colors"><X size={20} /></button>
                        </div>
                        
                        <div className="p-8 space-y-8">
                            {/* Visual Technical Map */}
                            <div>
                                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Technical Schema</h4>
                                <div className="font-mono text-sm bg-slate-50 p-6 rounded-2xl border border-slate-100 space-y-4 shadow-inner">
                                    <div>
                                        <div className="font-bold text-slate-800 mb-2">{activeRel.child_table}</div>
                                        <div className="pl-4 flex items-center gap-3">
                                            <LinkIcon size={14} className="text-indigo-400 shrink-0" />
                                            <span className="text-slate-600">{activeRel.child_column}</span>
                                            <span className="text-indigo-400 font-bold mx-2">───────────────►</span>
                                        </div>
                                    </div>
                                    <div>
                                        <div className="font-bold text-slate-800 mb-2">{activeRel.parent_table}</div>
                                        <div className="pl-4 flex items-center gap-3">
                                            <Key size={14} className="text-amber-500 shrink-0" />
                                            <span className="text-slate-600">{activeRel.parent_column}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Business Interpretation */}
                            <div>
                                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Business Interpretation</h4>
                                <div className="inline-flex items-center justify-center space-x-3 bg-indigo-50 px-6 py-4 rounded-2xl border border-indigo-100 text-lg font-medium text-indigo-900 w-full shadow-sm">
                                    <span className="font-black">{getConceptLabel(activeRel.child_table)}</span>
                                    <span className="text-indigo-400 text-sm uppercase font-bold tracking-wider">belongs to</span>
                                    <span className="font-black">{getConceptLabel(activeRel.parent_table)}</span>
                                </div>
                            </div>
                        </div>

                        <div className="p-6 border-t border-slate-100 flex gap-3 bg-slate-50/50">
                            {activeRel.approval_status !== 'approved' && (
                                <button 
                                    onClick={() => handleUpdateStatus(activeRel.id, 'approved')}
                                    className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white py-3.5 rounded-xl font-bold text-sm transition-all shadow-sm flex items-center justify-center gap-2"
                                >
                                    <Check size={18} /> Explicitly Approve
                                </button>
                            )}
                            <button 
                                onClick={() => handleUpdateStatus(activeRel.id, 'rejected')}
                                className="flex-1 bg-white hover:bg-red-50 text-red-600 border border-slate-200 hover:border-red-200 py-3.5 rounded-xl font-bold text-sm transition-all shadow-sm flex items-center justify-center gap-2"
                            >
                                <XCircle size={18} /> Reject
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
