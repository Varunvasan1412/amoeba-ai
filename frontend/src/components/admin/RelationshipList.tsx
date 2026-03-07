import React, { useEffect, useState, useMemo } from 'react';
import { apiFetch } from '../../utils/api';
import { 
  Search, ShieldCheck, Zap, AlertCircle, 
  ToggleLeft, ToggleRight, Loader2, Filter,
  ArrowUpDown, Database, ChevronRight, Plus, X, Link2, GitCommit, Trash2,
  ArrowRight, Layers, Layout, ArrowDown, Check
} from 'lucide-react';


interface Relationship {
  id: number;
  parent_table: string;
  parent_column: string;
  child_table: string;
  child_column: string;
  is_enabled: boolean;
  risk_level: string;
  confidence_score: number;
}

interface JoinStep {
  sourceTable: string;
  sourceCol: string;
  targetTable: string;
  targetCol: string;
}

interface RelationshipListProps {
  apiKey: string | null;
}

export const RelationshipList: React.FC<RelationshipListProps> = ({ apiKey }) => {
  const [rels, setRels] = useState<Relationship[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'enabled' | 'disabled'>('all');

  const [showAddModal, setShowAddModal] = useState(false);
  const [chain, setChain] = useState<JoinStep[]>([
      { sourceTable: '', sourceCol: '', targetTable: '', targetCol: '' }
  ]);
  const [schemaData, setSchemaData] = useState<any[]>([]);
  const [savingChain, setSavingChain] = useState(false);

  const fetchData = async () => {
    if (!apiKey) return;
    setLoading(true);
    try {
      const API_BASE = import.meta.env.VITE_API_URL || "";
      const url = `${API_BASE}/api/v2/relationships`.replace(/\/\//g, '/').replace(':/', '://');
      const res = await apiFetch(url, { headers: { "X-API-Key": apiKey } });
      const data = await res.json();
      if (Array.isArray(data)) setRels(data);

      const schemaRes = await apiFetch(`${API_BASE}/api/v2/semantic/schema`.replace(/\/\//g, '/').replace(':/', '://'), { headers: { "X-API-Key": apiKey } });
      setSchemaData(await schemaRes.json());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [apiKey]);

  const handleEstablishChain = async () => {
    setSavingChain(true);
    try {
        const API_BASE = import.meta.env.VITE_API_URL || "";
        for (const step of chain) {
            if (!step.sourceTable || !step.targetTable || !step.sourceCol || !step.targetCol) continue;
            await apiFetch(`${API_BASE}/api/v2/relationships`.replace(/\/\//g, '/').replace(':/', '://'), {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-API-Key": apiKey || "" },
                body: JSON.stringify({
                    parent_table: step.sourceTable,
                    parent_column: step.sourceCol,
                    child_table: step.targetTable,
                    child_column: step.targetCol
                })
            });
        }
        setShowAddModal(false);
        setChain([{ sourceTable: '', sourceCol: '', targetTable: '', targetCol: '' }]);
        fetchData();
    } catch (err) {
        console.error(err);
    } finally {
        setSavingChain(false);
    }
  };

  const addStep = () => {
      const lastStep = chain[chain.length - 1];
      setChain([...chain, { 
          sourceTable: lastStep.targetTable,
          sourceCol: '', 
          targetTable: '', 
          targetCol: '' 
      }]);
  };

  const removeStep = (index: number) => {
      if (chain.length === 1) return;
      setChain(chain.filter((_, i) => i !== index));
  };

  const updateStep = (index: number, data: Partial<JoinStep>) => {
      const newChain = [...chain];
      newChain[index] = { ...newChain[index], ...data };
      setChain(newChain);
  };

  const toggleRel = async (id: number, currentStatus: boolean) => {
    try {
      const API_BASE = import.meta.env.VITE_API_URL || "";
      const url = `${API_BASE}/api/v2/relationships/${id}/toggle`.replace(/\/\//g, '/').replace(':/', '://');
      await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": apiKey || "" },
        body: JSON.stringify({ is_enabled: !currentStatus })
      });
      setRels(prev => prev.map(r => r.id === id ? { ...r, is_enabled: !currentStatus } : r));
    } catch (err) {
      console.error(err);
    }
  };

  const filteredRels = useMemo(() => {
    return rels.filter(r => {
      const matchesSearch = r.parent_table.toLowerCase().includes(searchTerm.toLowerCase()) || r.child_table.toLowerCase().includes(searchTerm.toLowerCase()) || r.parent_column.toLowerCase().includes(searchTerm.toLowerCase()) || r.child_column.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFilter = filterStatus === 'all' || (filterStatus === 'enabled' && r.is_enabled) || (filterStatus === 'disabled' && !r.is_enabled);
      return matchesSearch && matchesFilter;
    });
  }, [rels, searchTerm, filterStatus]);

  const uniqueTables = Array.from(new Set(schemaData.map(s => s.table_name)));
  const getColsForTable = (table: string) => schemaData.filter(s => s.table_name === table).map(s => s.column_name);

  return (
    <div className="flex flex-col h-full bg-white relative">
      {/* Chain Builder Modal - MINIMALIST REDESIGN */}
      {showAddModal && (
          <div className="absolute inset-0 z-[100] bg-slate-900/40 backdrop-blur-sm flex items-start justify-center p-6 animate-in fade-in duration-200 overflow-y-auto">
              <div className="bg-white w-full max-w-4xl rounded-2xl shadow-2xl overflow-hidden mt-10 border border-slate-200 flex flex-col">
                  <div className="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-white sticky top-0 z-10">
                      <div>
                          <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                              <Link2 size={20} className="text-blue-600" /> Multi-Table Data Path
                          </h3>
                          <p className="text-slate-400 text-xs mt-0.5">Link multiple tables in a single logical sequence.</p>
                      </div>
                      <button onClick={() => setShowAddModal(false)} className="p-2 hover:bg-slate-50 rounded-lg transition-colors text-slate-400"><X size={20} /></button>
                  </div>
                  
                  <div className="p-8 space-y-4 bg-white overflow-y-auto max-h-[60vh]">
                      {chain.map((step, idx) => (
                          <div key={idx} className="flex flex-col gap-2 animate-in slide-in-from-top-2 duration-300">
                              <div className="flex items-center gap-4 bg-slate-50/50 p-4 rounded-xl border border-slate-100 relative group">
                                  <div className="flex-1 space-y-2">
                                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tight ml-1">Source Table</span>
                                      <div className="grid grid-cols-2 gap-2">
                                          <select 
                                            className="bg-white border border-slate-200 p-2.5 rounded-lg text-sm font-semibold text-slate-700 outline-none focus:border-blue-500"
                                            value={step.sourceTable}
                                            onChange={e => updateStep(idx, { sourceTable: e.target.value, sourceCol: '' })}
                                          >
                                              <option value="">Select Table</option>
                                              {uniqueTables.map(t => <option key={t} value={t}>{t}</option>)}
                                          </select>
                                          <select 
                                            className="bg-white border border-slate-200 p-2.5 rounded-lg text-xs text-slate-500 outline-none focus:border-blue-500"
                                            value={step.sourceCol}
                                            onChange={e => updateStep(idx, { sourceCol: e.target.value })}
                                          >
                                              <option value="">Select Column</option>
                                              {getColsForTable(step.sourceTable).map(c => <option key={c} value={c}>{c}</option>)}
                                          </select>
                                      </div>
                                  </div>

                                  <div className="pt-6 text-slate-300">
                                      <ArrowRight size={18} />
                                  </div>

                                  <div className="flex-1 space-y-2">
                                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-tight ml-1">Target Table</span>
                                      <div className="grid grid-cols-2 gap-2">
                                          <select 
                                            className="bg-white border border-slate-200 p-2.5 rounded-lg text-sm font-semibold text-slate-700 outline-none focus:border-blue-500"
                                            value={step.targetTable}
                                            onChange={e => updateStep(idx, { targetTable: e.target.value, targetCol: '' })}
                                          >
                                              <option value="">Select Table</option>
                                              {uniqueTables.map(t => <option key={t} value={t}>{t}</option>)}
                                          </select>
                                          <select 
                                            className="bg-white border border-slate-200 p-2.5 rounded-lg text-xs text-slate-500 outline-none focus:border-blue-500"
                                            value={step.targetCol}
                                            onChange={e => updateStep(idx, { targetCol: e.target.value })}
                                          >
                                              <option value="">Select Column</option>
                                              {getColsForTable(step.targetTable).map(c => <option key={c} value={c}>{c}</option>)}
                                          </select>
                                      </div>
                                  </div>

                                  {chain.length > 1 && (
                                      <button onClick={() => removeStep(idx)} className="mt-6 p-2 text-slate-300 hover:text-red-500 transition-colors"><Trash2 size={16}/></button>
                                  )}
                              </div>
                              {idx < chain.length - 1 && (
                                  <div className="flex justify-center -my-2 relative z-10">
                                      <div className="bg-blue-100 text-blue-600 rounded-full p-1 border-2 border-white">
                                          <ArrowDown size={12} />
                                      </div>
                                  </div>
                              )}
                          </div>
                      ))}

                      <button 
                        onClick={addStep}
                        className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-slate-100 text-slate-400 rounded-xl hover:border-blue-200 hover:text-blue-500 hover:bg-blue-50/20 transition-all text-xs font-bold"
                      >
                          <Plus size={14} /> Add Another Link
                      </button>
                  </div>

                  <div className="px-8 py-6 bg-slate-50 border-t border-slate-100 flex justify-end items-center gap-4">
                      <button onClick={() => setShowAddModal(false)} className="text-xs font-bold text-slate-400 hover:text-slate-600 px-4 py-2">Cancel</button>
                      <button 
                        onClick={handleEstablishChain}
                        disabled={savingChain || !chain[0].targetCol}
                        className="bg-blue-600 text-white px-8 py-2.5 rounded-xl font-bold text-sm hover:bg-blue-700 transition-all shadow-lg shadow-blue-100 disabled:opacity-50 flex items-center gap-2"
                      >
                          {savingChain ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
                          Save Connections
                      </button>
                  </div>
              </div>
          </div>
      )}

      {/* List Toolbar */}
      <div className="p-6 border-b border-gray-100 flex flex-col md:flex-row justify-between items-center gap-4 bg-gray-50/50">
          <div className="flex items-center gap-4 w-full md:w-auto">
              <div className="relative w-full md:w-80">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                  <input placeholder="Search connections..." className="w-full pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-xl focus:border-blue-500 outline-none transition-all shadow-sm text-sm font-medium" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
              </div>
              <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200 shadow-sm">
                  {(['all', 'enabled', 'disabled'] as const).map(s => (
                      <button key={s} onClick={() => setFilterStatus(s)} className={`px-4 py-1 rounded-lg text-[10px] font-bold uppercase transition-all ${filterStatus === s ? 'bg-slate-800 text-white shadow-md' : 'text-gray-400 hover:text-gray-600'}`}>{s}</button>
                  ))}
              </div>
          </div>
          <button 
            onClick={() => {
                setChain([{ sourceTable: '', sourceCol: '', targetTable: '', targetCol: '' }]);
                setShowAddModal(true);
            }} 
            className="w-full md:w-auto flex items-center justify-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-xl font-bold text-xs hover:bg-blue-700 transition-all shadow-lg shadow-blue-100"
          >
              <GitCommit size={16} /> Multi-Table Chain
          </button>
      </div>

      <div className="flex-1 overflow-auto bg-white">
          {loading && <div className="flex items-center justify-center py-32"><Loader2 className="animate-spin text-blue-600" size={32} /></div>}
          {!loading && filteredRels.length > 0 ? (
              <table className="w-full text-left border-collapse">
                  <thead className="sticky top-0 bg-white/90 backdrop-blur-md z-10 border-b border-slate-100 shadow-sm">
                      <tr>
                          <th className="p-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Source</th>
                          <th className="p-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider text-center">Logic</th>
                          <th className="p-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Target</th>
                          <th className="p-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider">Risk</th>
                          <th className="p-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider text-right">Status</th>
                      </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                      {filteredRels.map(r => (
                          <tr key={r.id} className="hover:bg-slate-50/50 transition-all">
                              <td className="p-4">
                                  <div className="flex items-center gap-3">
                                      <div className="p-2 bg-slate-50 rounded-lg text-slate-400"><Database size={16} /></div>
                                      <div><p className="text-sm font-bold text-slate-700">{r.parent_table}</p><p className="text-[10px] font-mono text-slate-400">{r.parent_column}</p></div>
                                  </div>
                              </td>
                              <td className="p-4 text-center"><div className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 rounded text-slate-400 font-mono text-[9px] font-bold"><span>JOIN</span></div></td>
                              <td className="p-4">
                                  <div className="flex items-center gap-3">
                                      <div className="p-2 bg-slate-50 rounded-lg text-slate-400"><Layout size={16} /></div>
                                      <div><p className="text-sm font-bold text-slate-700">{r.child_table}</p><p className="text-[10px] font-mono text-slate-400">{r.child_column}</p></div>
                                  </div>
                              </td>
                              <td className="p-4">
                                  {r.risk_level === 'safe' ? <span className="text-emerald-600 text-[10px] font-bold uppercase flex items-center gap-1"><ShieldCheck size={12}/> Safe</span> :
                                   r.risk_level === 'heuristic' ? <span className="text-amber-600 text-[10px] font-bold uppercase flex items-center gap-1"><Zap size={12}/> AI Guess</span> :
                                   <span className="text-blue-600 text-[10px] font-bold uppercase flex items-center gap-1"><Layers size={12}/> Manual</span>}
                              </td>
                              <td className="p-4 text-right">
                                  <button onClick={() => toggleRel(r.id, r.is_enabled)} className="relative inline-flex h-5 w-10 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none" style={{ backgroundColor: r.is_enabled ? '#2563eb' : '#cbd5e1' }}>
                                      <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${r.is_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
                                  </button>
                              </td>
                          </tr>
                      ))}
                  </tbody>
              </table>
          ) : !loading && (<div className="flex flex-col items-center justify-center py-32 text-slate-300"><Filter size={48} className="mb-4 opacity-10" /><p className="font-bold uppercase tracking-widest text-[10px]">No Matches Found</p></div>)}
      </div>
    </div>
  );
};
