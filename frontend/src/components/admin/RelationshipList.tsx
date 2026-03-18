import React, { useEffect, useState, useMemo } from 'react';
import { apiFetch } from '../../utils/api';
import { 
  Search, ShieldCheck, Zap, AlertCircle, 
  Loader2, Filter, Database, X, Trash2,
  ArrowRight, Layers, Layout, Check
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
  selected_columns: string[];
}

interface RelationshipListProps {
  apiKey: string | null;
  onDataLoaded?: (rels: Relationship[], schema: any[]) => void;
}

export const RelationshipList: React.FC<RelationshipListProps> = ({ apiKey, onDataLoaded }) => {
  const [rels, setRels] = useState<Relationship[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState<'all' | 'enabled' | 'disabled'>('all');

  const [schemaData, setSchemaData] = useState<any[]>([]);
  const [showColumnModal, setShowColumnModal] = useState<Relationship | null>(null);
  const [selectedCols, setSelectedCols] = useState<string[]>([]);

  const fetchData = async () => {
    if (!apiKey) return;
    setLoading(true);
    try {
      const API_BASE = import.meta.env.VITE_API_URL || "";
      const url = `${API_BASE}/api/v2/relationships`.replace(/\/\//g, '/').replace(':/', '://');
      const res = await apiFetch(url, { headers: { "X-API-Key": apiKey } });
      const data = await res.json();
      if (Array.isArray(data)) {
          setRels(data);
          const schemaRes = await apiFetch(`${API_BASE}/api/v2/semantic/schema`.replace(/\/\//g, '/').replace(':/', '://'), { headers: { "X-API-Key": apiKey } });
          const sData = await schemaRes.json();
          setSchemaData(sData);
          if (onDataLoaded) onDataLoaded(data, sData);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [apiKey]);

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

  const handleDelete = async (id: number) => {
    if (!apiKey || !confirm("Are you sure you want to delete this connection?")) return;
    try {
        const API_BASE = import.meta.env.VITE_API_URL || "";
        const res = await apiFetch(`${API_BASE}/api/v2/relationships/${id}`.replace(/\/\//g, '/').replace(':/', '://'), {
            method: "DELETE",
            headers: { "X-API-Key": apiKey }
        });
        if (res.ok) {
            setRels(prev => prev.filter(r => r.id !== id));
        }
    } catch (err) {}
  };

  const handleSaveColumns = async () => {
    if (!showColumnModal || !apiKey) return;
    try {
      const API_BASE = import.meta.env.VITE_API_URL || "";
      const url = `${API_BASE}/api/v2/relationships/${showColumnModal.id}/columns`.replace(/\/\//g, '/').replace(':/', '://');
      await apiFetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": apiKey },
        body: JSON.stringify({ columns: selectedCols })
      });
      setRels(prev => prev.map(r => r.id === showColumnModal.id ? { ...r, selected_columns: selectedCols } : r));
      setShowColumnModal(null);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleColumn = (col: string) => {
    setSelectedCols(prev => prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]);
  };

  const filteredRels = useMemo(() => {
    return rels.filter(r => {
      const matchesSearch = r.parent_table.toLowerCase().includes(searchTerm.toLowerCase()) || r.child_table.toLowerCase().includes(searchTerm.toLowerCase()) || r.parent_column.toLowerCase().includes(searchTerm.toLowerCase()) || r.child_column.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFilter = filterStatus === 'all' || (filterStatus === 'enabled' && r.is_enabled) || (filterStatus === 'disabled' && !r.is_enabled);
      return matchesSearch && matchesFilter;
    });
  }, [rels, searchTerm, filterStatus]);

  const getColsForTable = (table: string) => schemaData.filter(s => s.table_name === table).map(s => s.column_name);

  return (
    <div className="flex flex-col h-full bg-white relative">
      {/* Column Picker Modal */}
      {showColumnModal && (
          <div className="fixed inset-0 z-[110] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-6 animate-in fade-in duration-300">
              <div className="bg-white w-full max-w-md rounded-3xl shadow-2xl overflow-hidden border border-slate-100 flex flex-col max-h-[80vh]">
                  <div className="p-6 border-b border-slate-50 flex justify-between items-center">
                      <div>
                          <h3 className="text-lg font-bold text-slate-800">Select Data Payload</h3>
                          <p className="text-xs text-slate-400">Choose which columns to pull from <span className="font-mono text-blue-600 bg-blue-50 px-1 rounded">{showColumnModal.child_table}</span></p>
                      </div>
                      <button onClick={() => setShowColumnModal(null)} className="p-2 hover:bg-slate-50 rounded-xl transition-colors text-slate-400"><X size={20} /></button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto p-6 space-y-2 bg-slate-50/30">
                      {getColsForTable(showColumnModal.child_table).map(col => (
                          <button 
                            key={col} 
                            onClick={() => toggleColumn(col)}
                            className={`w-full flex items-center justify-between p-3 rounded-xl border transition-all ${selectedCols.includes(col) ? 'bg-blue-50 border-blue-200 text-blue-700 shadow-sm' : 'bg-white border-slate-100 text-slate-600 hover:border-slate-200'}`}
                          >
                              <span className="text-sm font-semibold">{col}</span>
                              {selectedCols.includes(col) && <Check size={16} className="text-blue-600" />}
                          </button>
                      ))}
                  </div>

                  <div className="p-6 border-t border-slate-50 flex gap-3">
                      <button 
                        onClick={handleSaveColumns}
                        className="flex-1 bg-blue-600 text-white py-3 rounded-2xl font-bold text-sm hover:bg-blue-700 transition-all shadow-lg shadow-blue-100 flex items-center justify-center gap-2"
                      >
                          Apply Column Selection
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
                          <th className="p-4 text-[10px] font-bold text-slate-400 uppercase tracking-wider text-center">Payload</th>
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
                              <td className="p-4 text-center">
                                  <button 
                                    onClick={() => {
                                        setSelectedCols(r.selected_columns || []);
                                        setShowColumnModal(r);
                                    }}
                                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-50 text-blue-600 rounded-xl text-[10px] font-bold hover:bg-blue-100 transition-all border border-blue-100"
                                  >
                                      <Filter size={12} />
                                      {r.selected_columns?.length || 0} Fields
                                  </button>
                              </td>
                              <td className="p-4">
                                  {r.risk_level === 'safe' ? <span className="text-emerald-600 text-[10px] font-bold uppercase flex items-center gap-1"><ShieldCheck size={12}/> Safe</span> :
                                   r.risk_level === 'heuristic' ? <span className="text-amber-600 text-[10px] font-bold uppercase flex items-center gap-1"><Zap size={12}/> AI Guess</span> :
                                   <span className="text-blue-600 text-[10px] font-bold uppercase flex items-center gap-1"><Layers size={12}/> Manual</span>}
                              </td>
                              <td className="p-4 text-right">
                                  <div className="flex items-center justify-end gap-2">
                                      <button onClick={() => toggleRel(r.id, r.is_enabled)} className="relative inline-flex h-5 w-10 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none" style={{ backgroundColor: r.is_enabled ? '#2563eb' : '#cbd5e1' }}>
                                          <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-md ring-0 transition duration-200 ease-in-out ${r.is_enabled ? 'translate-x-5' : 'translate-x-0'}`} />
                                      </button>
                                      <button onClick={() => handleDelete(r.id)} className="p-1.5 hover:bg-red-50 text-slate-300 hover:text-red-500 rounded-lg transition-all"><Trash2 size={14} /></button>
                                  </div>
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
