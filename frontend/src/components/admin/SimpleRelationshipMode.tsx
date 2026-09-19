import React, { useState, useMemo, useEffect } from 'react';
import { CheckCircle, AlertTriangle, XCircle, HelpCircle, Check, X, ChevronRight, Activity, Zap, Plus, Loader2 } from 'lucide-react';
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
    approval_status: string;
    is_enabled: boolean;
}

interface Props {
    allRels: Relationship[];
    appConcepts: Concept[];
    apiKey: string;
    onRefresh: () => void;
}

export const SimpleRelationshipMode: React.FC<Props> = ({ allRels, appConcepts, apiKey, onRefresh }) => {
    const [health, setHealth] = useState({ discovered: 0, needs_review: 0, ambiguous: 0, approved: 0, rejected: 0, total: 0 });
    const [activeRel, setActiveRel] = useState<Relationship | null>(null);
    
    // Sentence Builder State
    const [simpleSource, setSimpleSource] = useState('');
    const [simpleRelType, setSimpleRelType] = useState('belongs_to');
    const [simpleTarget, setSimpleTarget] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (!apiKey) return;
        apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/v2/relationships/health`, {
            headers: { 'X-API-Key': apiKey }
        })
        .then(res => res.json())
        .then(data => setHealth(data))
        .catch(err => console.error("Health fetch error", err));
    }, [apiKey, allRels]);

    const getConceptLabel = (tableName: string) => {
        const c = appConcepts.find(c => c.database_table === tableName);
        return c ? c.ui_label : 'Unmapped Concept';
    };

    const conceptOptions = useMemo(() => {
        return (appConcepts || [])
            .filter(c => !c.is_doubtful)
            .map(c => ({ value: c.database_table, label: c.ui_label }))
            .sort((a, b) => a.label.localeCompare(b.label));
    }, [appConcepts]);

    const handleSaveSimple = async () => {
        if (!simpleSource || !simpleTarget || !apiKey) return;
        setSaving(true);
        try {
            const res = await apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/v2/relationships/semantic`.replace(/\/\//g, '/').replace(':/', '://'), {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
                body: JSON.stringify({
                    source_table: simpleSource,
                    target_table: simpleTarget,
                    relationship_type: simpleRelType
                })
            });

            const data = await res.json();
            if (!res.ok) {
                toast.error(data.detail || "Failed to establish connection.");
            } else {
                setSimpleSource(''); setSimpleTarget(''); setSimpleRelType('belongs_to');
                onRefresh();
                toast.success("Relationship submitted for review!");
            }
        } catch (err: any) {
            toast.error(err.message);
        } finally {
            setSaving(false);
        }
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

    // Filter relationships requiring attention
    const needsAttention = allRels.filter(r => r.approval_status === 'needs_review' || r.approval_status === 'ambiguous' || r.approval_status === 'discovered');
    
    // Group active relationships by parent for the visual map
    const activeMap = useMemo(() => {
        const map: Record<string, { child: string; rel: Relationship }[]> = {};
        const active = allRels.filter(r => r.approval_status === 'approved' && r.is_enabled);
        active.forEach(r => {
            const pLabel = getConceptLabel(r.parent_table);
            const cLabel = getConceptLabel(r.child_table);
            if (!map[pLabel]) map[pLabel] = [];
            map[pLabel].push({ child: cLabel, rel: r });
        });
        return map;
    }, [allRels, appConcepts]);

    return (
        <div className="p-6 bg-slate-50 min-h-[600px] rounded-3xl animate-in fade-in space-y-8">
            
            {/* Secondary Option: Manual Connection */}
            <div className="bg-white rounded-3xl p-8 border border-slate-100 shadow-sm relative overflow-hidden">
                <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-50 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none"></div>
                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center">
                            <Plus size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-black text-slate-800">Teach Amoeba a Connection</h2>
                            <p className="text-sm text-slate-500 font-medium">Link your business concepts so Amoeba understands how they relate.</p>
                        </div>
                    </div>

                    <div className="flex flex-col md:flex-row items-center gap-4 bg-slate-50 p-6 rounded-[32px] border border-slate-100">
                        <div className="flex-1 w-full bg-white rounded-2xl border border-slate-200 shadow-sm relative z-50">
                            <SearchableDropdown
                                options={conceptOptions}
                                value={simpleSource}
                                onChange={setSimpleSource}
                                placeholder="Concept (e.g. Quotation)"
                            />
                        </div>
                        
                        <div className="relative group shrink-0 z-40">
                            <select 
                                value={simpleRelType}
                                onChange={(e) => setSimpleRelType(e.target.value)}
                                className="appearance-none bg-white border border-slate-200 px-6 py-3.5 rounded-2xl text-indigo-600 font-black text-sm outline-none cursor-pointer hover:border-indigo-300 transition-all shadow-sm pr-10"
                            >
                                <option value="belongs_to">belongs to</option>
                                <option value="contains">contains</option>
                            </select>
                        </div>

                        <div className="flex-1 w-full bg-white rounded-2xl border border-slate-200 shadow-sm relative z-30">
                            <SearchableDropdown
                                options={conceptOptions}
                                value={simpleTarget}
                                onChange={setSimpleTarget}
                                placeholder="Concept (e.g. Customer)"
                            />
                        </div>
                    </div>
                    
                    <button 
                        onClick={handleSaveSimple}
                        disabled={saving || !simpleSource || !simpleTarget}
                        className={`mt-6 w-full py-4 rounded-2xl font-black text-sm flex items-center justify-center gap-2 transition-all duration-300 shadow-lg 
                            ${saving || !simpleSource || !simpleTarget 
                                ? 'bg-slate-100 text-slate-400 cursor-not-allowed shadow-none' 
                                : 'bg-indigo-500 hover:bg-indigo-600 hover:-translate-y-0.5 text-white shadow-indigo-200'
                            }`}
                    >
                        {saving ? <Loader2 size={18} className="animate-spin" /> : <Zap size={18} />}
                        FIND CONNECTION
                    </button>
                </div>
            </div>

            {/* Health Summary */}
            <div>
                <h2 className="text-xl font-black text-slate-800 mb-4 flex items-center gap-2"><Activity size={20} className="text-blue-500"/> Relationship Health</h2>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col items-center justify-center">
                        <span className="text-3xl font-black text-slate-800">{health.discovered}</span>
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">Discovered</span>
                    </div>
                    <div className="bg-emerald-50 p-4 rounded-2xl border border-emerald-100 shadow-sm flex flex-col items-center justify-center">
                        <span className="text-3xl font-black text-emerald-600">{health.approved}</span>
                        <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest mt-1">Confirmed</span>
                    </div>
                    <div className="bg-amber-50 p-4 rounded-2xl border border-amber-100 shadow-sm flex flex-col items-center justify-center">
                        <span className="text-3xl font-black text-amber-600">{health.needs_review}</span>
                        <span className="text-[10px] font-bold text-amber-500 uppercase tracking-widest mt-1">Needs Review</span>
                    </div>
                    <div className="bg-orange-50 p-4 rounded-2xl border border-orange-100 shadow-sm flex flex-col items-center justify-center">
                        <span className="text-3xl font-black text-orange-600">{health.ambiguous}</span>
                        <span className="text-[10px] font-bold text-orange-500 uppercase tracking-widest mt-1">Ambiguous</span>
                    </div>
                    <div className="bg-slate-100 p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col items-center justify-center">
                        <span className="text-3xl font-black text-slate-500">{health.rejected}</span>
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">Rejected</span>
                    </div>
                </div>
            </div>

            {/* Needs Attention Panel */}
            {needsAttention.length > 0 && (
                <div className="bg-white border-2 border-amber-200 rounded-3xl p-6 shadow-md relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-amber-50 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none"></div>
                    <h3 className="text-lg font-black text-amber-600 flex items-center gap-2 mb-4 relative z-10"><AlertTriangle size={18} /> Needs Your Attention</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 relative z-10">
                        {needsAttention.map(rel => {
                            const pConcept = appConcepts.find(c => c.database_table === rel.parent_table);
                            const cConcept = appConcepts.find(c => c.database_table === rel.child_table);
                            const isMissingConcepts = !pConcept || !cConcept || pConcept.is_doubtful || cConcept.is_doubtful;
                            const isAmbiguous = rel.approval_status === 'ambiguous';
                            const pLabel = pConcept ? pConcept.ui_label : '';
                            const cLabel = cConcept ? cConcept.ui_label : '';
                            
                            return (
                                <div key={rel.id} className="bg-slate-50 border border-slate-200 p-4 rounded-2xl flex flex-col justify-between hover:border-amber-300 transition-colors cursor-pointer group" onClick={() => {
                                    if (!isMissingConcepts) setActiveRel(rel);
                                }}>
                                    <div>
                                        <div className="flex items-center gap-2 mb-2">
                                            {isAmbiguous ? <HelpCircle size={16} className="text-orange-500"/> : <Zap size={16} className="text-amber-500" />}
                                            <span className="text-xs font-bold text-slate-600 uppercase tracking-wider">{isAmbiguous ? 'Ambiguous' : (isMissingConcepts ? 'Discovered' : 'Needs Review')}</span>
                                        </div>
                                        
                                        {isMissingConcepts ? (
                                            <>
                                                <div className="text-sm font-semibold text-slate-800">
                                                    Connection discovered
                                                </div>
                                                <p className="text-xs text-slate-500 mt-2 line-clamp-2">
                                                    Business meaning not yet mapped
                                                </p>
                                            </>
                                        ) : (
                                            <>
                                                <div className="text-sm font-semibold text-slate-800">
                                                    {cLabel} <span className="text-slate-400 mx-1 font-normal">belongs to</span> {pLabel}
                                                </div>
                                                <p className="text-xs text-slate-500 mt-2 line-clamp-2">
                                                    {isAmbiguous 
                                                        ? 'Amoeba found more than one possible connection.' 
                                                        : 'Amoeba found a database relationship connecting these concepts.'}
                                                </p>
                                            </>
                                        )}
                                    </div>
                                    <div className="mt-4 flex justify-end">
                                        {isMissingConcepts ? (
                                            <button 
                                                onClick={(e) => { e.stopPropagation(); window.location.href = '/admin/semantic'; }}
                                                className="text-xs font-bold bg-blue-100 text-blue-700 px-3 py-1.5 rounded-lg hover:bg-blue-600 hover:text-white transition-colors"
                                            >
                                                Teach Concepts
                                            </button>
                                        ) : (
                                            <button className="text-xs font-bold bg-amber-100 text-amber-700 px-3 py-1.5 rounded-lg group-hover:bg-amber-500 group-hover:text-white transition-colors">
                                                Review
                                            </button>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Visual Business Map */}
            <div>
                <h3 className="text-lg font-black text-slate-800 mb-4 flex items-center gap-2"><CheckCircle size={18} className="text-emerald-500"/> Confirmed Relationships</h3>
                <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm">
                    {Object.keys(activeMap).length === 0 ? (
                        <div className="text-center py-10 text-slate-400 font-medium">No confirmed relationships yet.</div>
                    ) : (
                        <div className="space-y-6">
                            {Object.entries(activeMap).map(([parent, children]) => (
                                <div key={parent} className="border-l-2 border-slate-200 ml-4 relative">
                                    <div className="absolute -left-[9px] -top-1 w-4 h-4 rounded-full bg-indigo-500 border-4 border-white"></div>
                                    <div className="pl-6 pb-2">
                                        <h4 className="font-black text-slate-800 text-lg mb-3">{parent}</h4>
                                        <div className="space-y-2">
                                            {children.map((childObj, i) => (
                                                <div key={i} className="flex items-center gap-3 text-sm text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-100 w-max pr-6 cursor-pointer hover:bg-slate-100" onClick={() => setActiveRel(childObj.rel)}>
                                                    <span className="text-slate-400 shrink-0"><ChevronRight size={16}/></span>
                                                    <span><span className="italic text-slate-400 mr-2">has</span> {childObj.child}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Detail Modal */}
            {activeRel && (
                <div className="fixed inset-0 z-[120] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6 animate-in fade-in">
                    <div className="bg-white w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden border border-slate-100 flex flex-col">
                        <div className="p-6 border-b border-slate-50 flex justify-between items-center bg-slate-50/50">
                            <h3 className="text-lg font-black text-slate-800">Connection Details</h3>
                            <button onClick={() => setActiveRel(null)} className="p-2 hover:bg-slate-200 rounded-xl text-slate-400 transition-colors"><X size={20} /></button>
                        </div>
                        
                        <div className="p-8 text-center space-y-6">
                            <div className="inline-flex items-center justify-center space-x-3 bg-indigo-50 px-6 py-4 rounded-2xl border border-indigo-100 text-lg font-medium text-indigo-900 w-full">
                                <span className="font-black">{getConceptLabel(activeRel.child_table)}</span>
                                <span className="text-indigo-400 text-sm">belongs to</span>
                                <span className="font-black">{getConceptLabel(activeRel.parent_table)}</span>
                            </div>

                            <div className="text-left bg-slate-50 p-5 rounded-2xl border border-slate-100">
                                <p className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Why did Amoeba suggest this?</p>
                                <p className="text-sm text-slate-600 leading-relaxed">
                                    {activeRel.approval_status === 'ambiguous' 
                                        ? "Amoeba found multiple possible connections. The system could not confidently determine which one is intended without technical review."
                                        : "Amoeba found a database relationship connecting these concepts and verified that the referenced records are valid."}
                                </p>
                                {activeRel.approval_status === 'ambiguous' && (
                                    <div className="mt-4 p-3 bg-red-50 text-red-600 rounded-xl text-xs font-semibold flex items-start gap-2">
                                        <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                                        Please review the specific Foreign Keys in Advanced Mode to resolve this ambiguity safely.
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="p-6 border-t border-slate-100 flex gap-3 bg-slate-50/50">
                            {activeRel.approval_status !== 'ambiguous' && (
                                <button 
                                    onClick={() => handleUpdateStatus(activeRel.id, 'approved')}
                                    className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white py-3.5 rounded-xl font-bold text-sm transition-all shadow-sm flex items-center justify-center gap-2"
                                >
                                    <Check size={18} /> Confirm & Activate
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
