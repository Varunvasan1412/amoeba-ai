import { useState, useEffect, useRef } from "react";
import { 
    Shield, CheckCircle, AlertTriangle, XCircle, RefreshCcw, 
    ArrowRight, Settings2, Zap, RotateCcw, 
    Loader2, Search, ChevronDown, Bot, Activity, 
    MousePointer2, Edit3 
} from "lucide-react";
import { useAdmin } from "../context/AdminContext";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../utils/api";

const formatSuggestedFix = (fix: any, warning: any) => {
    if (!fix) return "No fix suggested";
    if (fix.action === 'rename_semantic_label') return `Rename label to "${fix.value}"`;
    if (fix.action === 'update_navigation') return `Map route to table "${fix.value || '...'}"`;
    return fix.description || "Apply recommended resolution";
};

export default function SystemHealth() {
    const { clientId } = useAdmin();
    const navigate = useNavigate();
    const [warnings, setWarnings] = useState<any[]>([]);
    const [availableTables, setAvailableTables] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [applyingId, setApplyingId] = useState<string | null>(null);
    const [isApplyingAll, setIsApplyingAll] = useState(false);
    const [manualFixes, setManualFixes] = useState<Record<string, any>>({});
    const [lastActionReport, setLastActionReport] = useState<{status: string, message: string} | null>(null);
    const [lastUndoBatch, setLastUndoBatch] = useState<any[] | null>(null);
    const [searchTerm, setSearchTerm] = useState("");
    
    // New tab state
    
    // New tab state
    const [activeTab, setActiveTab] = useState<'auto' | 'manual' | 'compare'>('auto');
    
    // Compare & Resolve State
    const [compareSearch1, setCompareSearch1] = useState("");
    const [compareSearch2, setCompareSearch2] = useState("");
    const [compareResults1, setCompareResults1] = useState<any[]>([]);
    const [compareResults2, setCompareResults2] = useState<any[]>([]);
    const [compareSlot1, setCompareSlot1] = useState<any>(null);
    const [compareSlot2, setCompareSlot2] = useState<any>(null);
    const [editStates, setEditStates] = useState<Record<string, any>>({});

    useEffect(() => {
        if (clientId) {
            fetchWarnings();
            
            // Attempt to restore previous revert state
            const savedRevert = localStorage.getItem(`amoeba_revert_${clientId}`);
            if (savedRevert) {
                try {
                    setLastUndoBatch(JSON.parse(savedRevert));
                } catch (e) {
                    localStorage.removeItem(`amoeba_revert_${clientId}`);
                }
            } else {
                setLastUndoBatch(null);
            }
        }
    }, [clientId]);

    const fetchWarnings = async () => {
        setLoading(true);
        try {
            const response = await apiFetch(`/admin/validation/warnings?client_id=${clientId}`);
            const data = await response.json();
            setWarnings(data.warnings || []);
            setAvailableTables(data.available_tables || []);
        } catch (err) {
            console.error("Failed to fetch warnings", err);
        } finally {
            setLoading(false);
        }
    };

    const handleManualChange = (warningId: string, value: any) => {
        setManualFixes(prev => ({
            ...prev,
            [warningId]: value
        }));
    };

    const applyFix = async (warning: any) => {
        setApplyingId(warning.id);
        setLastActionReport(null);
        
        const fixPayload = { ...warning.suggested_fix };
        if (manualFixes[warning.id] !== undefined) {
            fixPayload.value = manualFixes[warning.id];
            fixPayload.description = `Manually set to '${manualFixes[warning.id]}'`;
        }

        try {
            const response = await apiFetch(`/admin/validation/apply-fix`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(fixPayload)
            });
            
            const result = await response.json();
            if (response.ok) {
                await fetchWarnings();
                
                if (result.undo_fixes && result.undo_fixes.length > 0) {
                    setLastUndoBatch(result.undo_fixes);
                    localStorage.setItem(`amoeba_revert_${clientId}`, JSON.stringify(result.undo_fixes));
                } else {
                    setLastUndoBatch(null);
                    localStorage.removeItem(`amoeba_revert_${clientId}`);
                }
                
                setLastActionReport({ status: 'success', message: 'Applied fix successfully.' });
                const newManuals = { ...manualFixes };
                delete newManuals[warning.id];
                setManualFixes(newManuals);
            } else {
                setLastActionReport({ status: 'error', message: result.detail || 'Failed to apply fix.' });
            }
        } catch (err) {
            setLastActionReport({ status: 'error', message: 'Network error. Check server logs.' });
        } finally {
            setApplyingId(null);
        }
    };

    const applyManualFix = async (warning: any) => {
        const table = manualFixes[warning.id];
        if (!table) return;
        setApplyingId(warning.id);
        try {
            const response = await apiFetch(`/admin/validation/apply-fix`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: "update_navigation",
                    field: "table_name",
                    value: table,
                    id: warning.id,
                    description: `Manually mapped to '${table}'`
                })
            });
            if (response.ok) {
                await fetchWarnings();
                setLastActionReport({ status: 'success', message: 'Mapping saved successfully.' });
            }
        } finally {
            setApplyingId(null);
        }
    };

    const searchCompare = async (term: string, slot: 1 | 2) => {
        if (!term || term.length < 2) return;
        try {
            const response = await apiFetch(`/admin/validation/term-search?client_id=${clientId}&term=${encodeURIComponent(term)}`);
            const data = await response.json();
            if (slot === 1) setCompareResults1(data); else setCompareResults2(data);
        } catch (err) {
            console.error("Search failed", err);
        }
    };

    const handleCompareEdit = (id: string, field: string, value: any) => {
        setEditStates(prev => ({
            ...prev,
            [id]: {
                ...(prev[id] || {}),
                [field]: value
            }
        }));
    };

    const saveCompareEdit = async (item: any) => {
        const edits = editStates[item.id];
        if (!edits) return;

        setApplyingId(item.id.toString());
        try {
            const batch = [];
            if (item.source === 'navigation') {
                if (edits.label !== undefined) {
                    batch.push({
                        action: "rename_navigation_label",
                        item_id: item.db_id || item.id,
                        old_label: item.label,
                        new_label: edits.label
                    });
                }
            } else {
                if (edits.label !== undefined) {
                    batch.push({
                        action: "rename_semantic_label",
                        entry_id: item.db_id || item.id,
                        old_term: item.label,
                        new_term: edits.label,
                        is_synonym: false
                    });
                }
            }
            
            if (batch.length > 0) {
                const response = await apiFetch('/admin/validation/run-batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ fixes: batch })
                });
                const result = await response.json();
                if (response.ok && result.status === 'success' && result.applied > 0) {
                    setLastActionReport({ status: 'success', message: `Updated ${item.label} successfully.` });
                    if (compareSlot1?.id === item.id) setCompareSlot1({...item, ...edits});
                    if (compareSlot2?.id === item.id) setCompareSlot2({...item, ...edits});
                    fetchWarnings();
                } else {
                    setLastActionReport({ 
                        status: 'error', 
                        message: result.message || `Failed to update ${item.label}. It may have been deleted or moved.` 
                    });
                }
            }
        } catch (err) {
            setLastActionReport({ status: 'error', message: 'Network error while saving edits.' });
        } finally {
            setApplyingId(null);
        }
    };

    const applyAllFixes = async () => {
        if (!window.confirm("This will apply all auto-suggested fixes. Continue?")) return;
        setIsApplyingAll(true);
        setLastActionReport(null);
        try {
            const response = await apiFetch(`/admin/validation/apply-all?client_id=${clientId}`, {
                method: 'POST'
            });
            const result = await response.json();
            if (response.ok) {
                await fetchWarnings();
                if (result.undo_fixes && result.undo_fixes.length > 0) {
                    setLastUndoBatch(result.undo_fixes);
                    localStorage.setItem(`amoeba_revert_${clientId}`, JSON.stringify(result.undo_fixes));
                }
                setLastActionReport({ 
                    status: result.status === 'success' ? 'success' : 'warning', 
                    message: result.message || `Applied ${result.applied} fixes.` 
                });
            } else {
                setLastActionReport({ status: 'error', message: result.detail || 'Failed to apply batch fixes.' });
            }
        } catch (err) {
            setLastActionReport({ status: 'error', message: 'Network error during batch application.' });
        } finally {
            setIsApplyingAll(false);
        }
    };

    const applySelectedManualFixes = async () => {
        const selectedWarnings = manualWarnings.filter(w => manualFixes[w.id]);
        if (selectedWarnings.length === 0) return;
        if (!window.confirm(`Apply ${selectedWarnings.length} manually selected fixes?`)) return;
        
        setIsApplyingAll(true);
        setLastActionReport(null);
        const batchFixes = selectedWarnings.map(w => ({
            ...w.suggested_fix,
            value: manualFixes[w.id],
            description: `Manually mapped to '${manualFixes[w.id]}'`
        }));
        
        try {
            const response = await apiFetch(`/admin/validation/run-batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ fixes: batchFixes })
            });
            const result = await response.json();
            if (response.ok) {
                await fetchWarnings();
                const remainingManuals = { ...manualFixes };
                selectedWarnings.forEach(w => delete remainingManuals[w.id]);
                setManualFixes(remainingManuals);
                if (result.undo_fixes && result.undo_fixes.length > 0) {
                    setLastUndoBatch(result.undo_fixes);
                    localStorage.setItem(`amoeba_revert_${clientId}`, JSON.stringify(result.undo_fixes));
                }
                setLastActionReport({ status: 'success', message: `Successfully applied ${selectedWarnings.length} manual fixes.` });
            }
        } catch (err) {
            setLastActionReport({ status: 'error', message: 'Network error.' });
        } finally {
            setIsApplyingAll(false);
        }
    };

    const navigateToSource = (warning: any) => {
        if (warning.type === 'navigation_missing_table' || warning.type === 'duplicate_label') {
            navigate(`/admin/routes`);
        } else if (warning.type === 'semantic_conflict') {
            navigate(`/admin/semantic`);
        }
    };

    if (!clientId) return null;

    const filteredWarnings = warnings.filter(w => {
        if (!searchTerm) return true;
        const term = searchTerm.toLowerCase().replace(/_/g, ' ');
        const safeStringMatch = (str: any) => (typeof str === 'string' && str.toLowerCase().replace(/_/g, ' ').includes(term));
        return (
            safeStringMatch(w.type) ||
            safeStringMatch(w.message) ||
            safeStringMatch(w.table1) ||
            safeStringMatch(w.term1) ||
            (w.suggested_fix && safeStringMatch(w.suggested_fix.value))
        );
    });

    const fixableWarnings = filteredWarnings.filter(w => w.suggested_fix?.value !== null);
    const manualWarnings = filteredWarnings.filter(w => w.suggested_fix?.value === null);
    const fixableCount = fixableWarnings.length;
    const selectedManualCount = manualWarnings.filter(w => manualFixes[w.id]).length;

    useEffect(() => {
        if (fixableCount === 0 && manualWarnings.length > 0 && activeTab === 'auto') {
            setActiveTab('manual');
        }
    }, [fixableCount, manualWarnings.length]);

    return (
        <div className="max-w-5xl mx-auto p-8 h-screen flex flex-col">
            <header className="mb-8 flex-shrink-0">
                <div className="flex items-center gap-4 mb-2">
                    <Link to="/admin" className="text-blue-600 hover:underline text-sm flex items-center gap-1">
                        <ArrowRight size={14} className="rotate-180" /> Back to Dashboard
                    </Link>
                </div>
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
                            <Shield className="text-blue-600" size={32} />
                            System Health
                        </h1>
                        <p className="text-gray-500 mt-2">Automated diagnostics and configuration fixes.</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="relative group">
                            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                            <input 
                                type="text"
                                placeholder="Search warnings..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="pl-9 pr-4 py-3 bg-white border border-gray-100 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 shadow-sm w-[250px] transition-all focus:w-[300px]"
                            />
                        </div>
                        <button 
                            onClick={fetchWarnings}
                            className="p-3 text-gray-500 hover:bg-gray-100 rounded-xl transition-colors border border-gray-100 bg-white shadow-sm"
                            title="Refresh Diagnostics"
                        >
                            <RefreshCcw size={20} className={loading ? "animate-spin" : ""} />
                        </button>
                    </div>
                </div>

                {lastActionReport && (
                    <div className={`mt-6 p-4 rounded-xl flex items-center justify-between border ${
                        lastActionReport.status === 'success' ? 'bg-emerald-50 border-emerald-100 text-emerald-800' : 
                        lastActionReport.status === 'error' ? 'bg-red-50 border-red-100 text-red-800' : 'bg-amber-50 border-amber-100 text-amber-800'
                    }`}>
                        <div className="flex items-center gap-3">
                            {lastActionReport.status === 'success' ? <CheckCircle size={20} /> : <AlertTriangle size={20} />}
                            <p className="font-bold">{lastActionReport.message}</p>
                        </div>
                        <button onClick={() => setLastActionReport(null)} className="text-[10px] uppercase font-bold opacity-50 hover:opacity-100">Dismiss</button>
                    </div>
                )}
            </header>

            {loading ? (
                <div className="flex flex-col items-center justify-center py-20 flex-1">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
                    <p className="text-gray-500">Scanning configuration...</p>
                </div>
            ) : (
                <div className="flex-1 flex flex-col min-h-0 overflow-hidden bg-white border border-gray-200 rounded-3xl shadow-sm">
                    {/* Tabs Header */}
                    <div className="flex border-b border-gray-200 bg-gray-50/50 rounded-t-3xl border-b shadow-sm z-10">
                        <button 
                            onClick={() => setActiveTab('auto')}
                            className={`flex flex-col flex-1 py-5 px-6 items-center border-b-2 transition-all ${
                                activeTab === 'auto' ? 'border-blue-600 bg-blue-50/50' : 'border-transparent hover:bg-gray-100 text-gray-500'
                            }`}
                        >
                            <div className="flex items-center gap-2 mb-1">
                                <Zap size={18} className={activeTab === 'auto' ? 'text-blue-600 fill-current' : ''} />
                                <span className={`font-bold text-lg ${activeTab === 'auto' ? 'text-blue-900' : ''}`}>Auto-Fixes</span>
                            </div>
                            <span className={`text-[10px] px-2 py-0.5 rounded-full ${activeTab === 'auto' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>{fixableCount}</span>
                        </button>
                        <button 
                            onClick={() => setActiveTab('manual')}
                            className={`flex flex-col flex-1 py-5 px-6 items-center border-b-2 transition-all ${
                                activeTab === 'manual' ? 'border-amber-500 bg-amber-50/50' : 'border-transparent hover:bg-gray-100 text-gray-500'
                            }`}
                        >
                            <div className="flex items-center gap-2 mb-1">
                                <Settings2 size={18} className={activeTab === 'manual' ? 'text-amber-600' : ''} />
                                <span className={`font-bold text-lg ${activeTab === 'manual' ? 'text-amber-900' : ''}`}>Manual Issues</span>
                            </div>
                            <span className={`text-[10px] px-2 py-0.5 rounded-full ${activeTab === 'manual' ? 'bg-amber-500 text-white' : 'bg-gray-200 text-gray-600'}`}>{manualWarnings.length}</span>
                        </button>
                        <button 
                            onClick={() => setActiveTab('compare')}
                            className={`flex flex-col flex-1 py-5 px-6 items-center border-b-2 transition-all ${
                                activeTab === 'compare' ? 'border-purple-500 bg-purple-50/50' : 'border-transparent hover:bg-gray-100 text-gray-500'
                            }`}
                        >
                            <div className="flex items-center gap-2 mb-1">
                                <RotateCcw size={18} className={activeTab === 'compare' ? 'text-purple-600' : ''} />
                                <span className={`font-bold text-lg ${activeTab === 'compare' ? 'text-purple-900' : ''}`}>Compare & Fix</span>
                            </div>
                            <span className="text-[10px] uppercase font-bold text-purple-600">Resolve Conflict</span>
                        </button>
                    </div>

                    <div className="flex-1 overflow-y-auto p-6 bg-gray-50/20">
                        {activeTab === 'auto' && (
                            <div className="space-y-4">
                                {fixableCount > 0 && (
                                    <div className="flex justify-end mb-4">
                                        <button 
                                            onClick={applyAllFixes}
                                            disabled={isApplyingAll}
                                            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold shadow-md hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
                                        >
                                            {isApplyingAll ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} fill="currentColor" />}
                                            Apply All Auto-Fixes
                                        </button>
                                    </div>
                                )}
                                {fixableWarnings.length === 0 ? (
                                    <div className="text-center py-20 text-gray-400">
                                        <CheckCircle size={40} className="mx-auto mb-4 opacity-20" />
                                        <p>No auto-fixable issues detected.</p>
                                    </div>
                                ) : (
                                    fixableWarnings.map((w, index) => (
                                        <WarningCard key={w.id} warning={w} isFixable={true} index={index} navigateToSource={navigateToSource} applyFix={applyFix} applyingId={applyingId} />
                                    ))
                                )}
                            </div>
                        )}

                        {activeTab === 'manual' && (
                            <div className="space-y-4">
                                {selectedManualCount > 0 && (
                                    <div className="flex justify-end mb-4">
                                        <button onClick={applySelectedManualFixes} disabled={isApplyingAll} className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-bold shadow-md hover:bg-amber-600 flex items-center gap-2">
                                            {isApplyingAll ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
                                            Submit Selected ({selectedManualCount})
                                        </button>
                                    </div>
                                )}
                                {manualWarnings.length === 0 ? (
                                    <div className="text-center py-20 text-gray-400">
                                        <CheckCircle size={40} className="mx-auto mb-4 opacity-20" />
                                        <p>No manual resolutions required.</p>
                                    </div>
                                ) : (
                                    manualWarnings.map((w, index) => (
                                        <WarningCard key={w.id} warning={w} index={index} navigateToSource={navigateToSource} manualFixes={manualFixes} handleManualChange={handleManualChange} availableTables={availableTables} applyingId={applyingId} applyManualFix={applyManualFix} />
                                    ))
                                )}
                            </div>
                        )}

                        {activeTab === 'compare' && (
                            <div className="space-y-6">
                                <div className="bg-purple-50 border border-purple-100 rounded-2xl p-4 flex gap-3 text-sm text-purple-800">
                                    <Bot className="text-purple-500 mt-1" size={18} />
                                    <div>
                                        <p className="font-bold mb-1">Conflict Resolver</p>
                                        <p className="opacity-90 leading-relaxed">If two terms (like "Lead Category" and "Master Category") are confusing the AI, find them here and give them unique, descriptive labels.</p>
                                    </div>
                                </div>
                                <div className="grid grid-cols-2 gap-6">
                                    {/* Slot 1 */}
                                    <div className="space-y-4">
                                        <div className="relative">
                                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                                            <input 
                                                type="text" placeholder="Search item 1..." value={compareSearch1}
                                                onChange={(e) => { setCompareSearch1(e.target.value); searchCompare(e.target.value, 1); }}
                                                className="w-full pl-9 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-100 outline-none font-medium"
                                            />
                                            {compareResults1.length > 0 && !compareSlot1 && (
                                                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-20 max-h-60 overflow-y-auto">
                                                    {compareResults1.map(res => (
                                                        <button key={res.id} onClick={() => { setCompareSlot1(res); setCompareSearch1(""); setCompareResults1([]); }} className="w-full text-left p-3 hover:bg-purple-50 border-b last:border-0">
                                                            <p className="font-bold text-sm">{res.label}</p>
                                                            <p className="text-[10px] text-gray-400 uppercase">{res.table}</p>
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                        {compareSlot1 ? (
                                            <CompareCard item={compareSlot1} onClose={() => setCompareSlot1(null)} onEdit={(f, v) => handleCompareEdit(compareSlot1.id, f, v)} editState={editStates[compareSlot1.id] || {}} onSave={() => saveCompareEdit(compareSlot1)} applying={applyingId === compareSlot1.id.toString()} />
                                        ) : (
                                            <div className="border-2 border-dashed border-gray-200 rounded-2xl h-[350px] flex flex-col items-center justify-center text-gray-400">
                                                <MousePointer2 size={32} className="mb-2 opacity-10" />
                                                <p className="text-sm font-medium">Select first item</p>
                                            </div>
                                        )}
                                    </div>
                                    {/* Slot 2 */}
                                    <div className="space-y-4">
                                        <div className="relative">
                                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={16} />
                                            <input 
                                                type="text" placeholder="Search item 2..." value={compareSearch2}
                                                onChange={(e) => { setCompareSearch2(e.target.value); searchCompare(e.target.value, 2); }}
                                                className="w-full pl-9 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:ring-2 focus:ring-purple-100 outline-none font-medium"
                                            />
                                            {compareResults2.length > 0 && !compareSlot2 && (
                                                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-20 max-h-60 overflow-y-auto">
                                                    {compareResults2.map(res => (
                                                        <button key={res.id} onClick={() => { setCompareSlot2(res); setCompareSearch2(""); setCompareResults2([]); }} className="w-full text-left p-3 hover:bg-purple-50 border-b last:border-0">
                                                            <p className="font-bold text-sm">{res.label}</p>
                                                            <p className="text-[10px] text-gray-400 uppercase">{res.table}</p>
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                        {compareSlot2 ? (
                                            <CompareCard item={compareSlot2} onClose={() => setCompareSlot2(null)} onEdit={(f, v) => handleCompareEdit(compareSlot2.id, f, v)} editState={editStates[compareSlot2.id] || {}} onSave={() => saveCompareEdit(compareSlot2)} applying={applyingId === compareSlot2.id.toString()} />
                                        ) : (
                                            <div className="border-2 border-dashed border-gray-200 rounded-2xl h-[350px] flex flex-col items-center justify-center text-gray-400">
                                                <MousePointer2 size={32} className="mb-2 opacity-10" />
                                                <p className="text-sm font-medium">Select second item</p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

function WarningCard({ warning, isFixable, index, navigateToSource, applyFix, applyManualFix, manualFixes, handleManualChange, availableTables, applyingId }: any) {
    return (
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm p-6 hover:shadow-md transition-all flex gap-4" style={{ zIndex: 1000 - index }}>
            <div className={`w-1.5 rounded-full ${warning.severity === 'error' ? 'bg-red-500' : 'bg-amber-500'}`}></div>
            <div className="flex-1">
                <div className="flex justify-between items-start mb-4">
                    <div>
                        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${warning.severity === 'error' ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600'}`}>
                            {warning.type.replace(/_/g, ' ')}
                        </span>
                        <h3 className="text-base font-bold text-gray-800 mt-2">{warning.message}</h3>
                    </div>
                    <button onClick={() => navigateToSource(warning)} className="p-2 text-gray-400 hover:text-blue-600"><ArrowRight size={18} /></button>
                </div>

                {isFixable ? (
                    <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4 flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-700">{formatSuggestedFix(warning.suggested_fix, warning)}</p>
                        <button onClick={() => applyFix(warning)} disabled={applyingId === warning.id} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-xs font-black shadow-sm disabled:opacity-50">
                            {applyingId === warning.id ? <RefreshCcw size={14} className="animate-spin" /> : <Zap size={14} className="inline mr-1" />}
                            {applyingId === warning.id ? "APPLYING..." : "FIX"}
                        </button>
                    </div>
                ) : warning.type === 'missing_table_mapping' ? (
                    <div className="bg-amber-50/50 border border-amber-100 rounded-xl p-4">
                        <SearchableSelect options={availableTables} value={manualFixes?.[warning.id] || ''} onChange={(val: string) => handleManualChange(warning.id, val)} placeholder="Map to table..." />
                        {manualFixes?.[warning.id] && (
                            <button onClick={() => applyManualFix(warning)} disabled={applyingId === warning.id} className="mt-3 w-full bg-amber-500 text-white py-2 rounded-lg text-xs font-black">
                                {applyingId === warning.id ? "SAVING..." : "SAVE MAPPING"}
                            </button>
                        )}
                    </div>
                ) : null}
            </div>
        </div>
    );
}

function CompareCard({ item, onClose, onEdit, editState, onSave, applying }: any) {
    return (
        <div className="bg-white border-2 border-purple-100 shadow-xl rounded-2xl p-6 relative animate-in fade-in zoom-in-95 duration-200">
            <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"><XCircle size={18} /></button>
            <div className="flex items-center gap-2 mb-6 text-purple-600">
                <Activity size={20} />
                <h4 className="font-black text-xs uppercase tracking-widest">Target Configuration</h4>
            </div>

            <div className="space-y-5">
                <div>
                    <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-1">Friendly Label</label>
                    <div className="relative group">
                        <Edit3 size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-purple-500" />
                        <input 
                            type="text" 
                            value={editState.label !== undefined ? editState.label : item.label} 
                            onChange={(e) => onEdit('label', e.target.value)}
                            className="w-full pl-10 pr-4 py-3 bg-gray-50 border border-gray-100 rounded-xl font-bold text-gray-800 text-lg outline-none focus:ring-2 focus:ring-purple-100 focus:bg-white transition-all"
                        />
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-50/50 p-3 rounded-xl border border-gray-100">
                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-1">Database Table</label>
                        <p className="text-sm font-mono font-bold text-gray-700">{item.table}</p>
                    </div>
                    <div className="bg-gray-50/50 p-3 rounded-xl border border-gray-100">
                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-1">Module</label>
                        <p className="text-sm font-bold text-gray-700">{item.module || 'Unassigned'}</p>
                    </div>
                </div>

                <div className="pt-4 flex gap-3">
                    <button 
                        onClick={onSave}
                        disabled={applying || editState.label === undefined || editState.label === item.label}
                        className="flex-1 bg-purple-600 text-white py-3 rounded-xl font-black text-sm shadow-lg shadow-purple-100 hover:bg-purple-700 transition-all active:scale-95 disabled:opacity-30 disabled:scale-100 flex items-center justify-center gap-2"
                    >
                        {applying ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                        {applying ? "SAVING..." : "UPDATE CONFIG"}
                    </button>
                </div>
            </div>
        </div>
    );
}

function SearchableSelect({ options, value, onChange, placeholder }: any) {
    const [isOpen, setIsOpen] = useState(false);
    const [search, setSearch] = useState("");
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handler = (e: any) => { if (ref.current && !ref.current.contains(e.target)) setIsOpen(false); };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, []);

    const filtered = options.filter((o: string) => o.toLowerCase().includes(search.toLowerCase()));

    return (
        <div className="relative" ref={ref}>
            <div onClick={() => setIsOpen(!isOpen)} className="w-full bg-white border border-gray-200 rounded-xl px-4 py-2.5 text-sm cursor-pointer flex justify-between items-center shadow-sm">
                <span className={value ? "text-gray-800 font-bold" : "text-gray-400"}>{value || placeholder}</span>
                <ChevronDown size={16} className={isOpen ? "rotate-180 transition-all" : "transition-all"} />
            </div>
            {isOpen && (
                <div className="absolute z-50 w-full mt-2 bg-white border border-gray-200 rounded-xl shadow-2xl overflow-hidden max-h-60 overflow-y-auto">
                    <div className="p-2 border-b border-gray-50 bg-gray-50">
                        <input autoFocus placeholder="Search tables..." className="w-full p-2 text-xs border rounded" value={search} onChange={(e) => setSearch(e.target.value)} />
                    </div>
                    {filtered.map((o: string) => (
                        <div key={o} onClick={() => { onChange(o); setIsOpen(false); }} className="px-4 py-2 text-sm hover:bg-blue-50 cursor-pointer">{o}</div>
                    ))}
                </div>
            )}
        </div>
    );
}
