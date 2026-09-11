import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';
import { Table, Pencil, Check, X, AlertTriangle, RefreshCcw, Search, Database } from 'lucide-react';
import { apiFetch } from '../../utils/api';

interface SemanticMappingResponse {
  id: number;
  ui_label: string;
  database_table: string;
  base_query: string | null;
  source_file: string | null;
  is_doubtful: boolean;
}

const SemanticMappingsPage: React.FC = () => {
  const { clientId } = useAdmin();
  const [mappings, setMappings] = useState<SemanticMappingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");

  useEffect(() => {
    if (clientId) {
      fetchMappings();
    }
  }, [clientId]);

  const fetchMappings = async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`/v2/semantic/mappings?client_id=${clientId}`);
      const data = await res.json();
      setMappings(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch semantic mappings', err);
      setMappings([]);
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (mapping: SemanticMappingResponse) => {
    setEditingId(mapping.id);
    setEditValue(mapping.database_table);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditValue("");
  };

  const saveEdit = async (id: number) => {
    try {
      const res = await apiFetch(`/v2/semantic/mappings/${id}?client_id=${clientId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ database_table: editValue })
      });

      if (res.ok) {
        setMappings(mappings.map(m => m.id === id ? { ...m, database_table: editValue, is_doubtful: false } : m));
        setEditingId(null);
      }
    } catch (err) {
      console.error('Failed to save mapping', err);
    }
  };

  if (!clientId) return <div className="p-8 text-center text-gray-500 font-black uppercase tracking-widest text-xs">Please select a client first.</div>;

  const filteredMappings = mappings.filter(m => 
    m.ui_label.toLowerCase().includes(searchTerm.toLowerCase()) || 
    m.database_table.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 flex items-center gap-3">
            <Database className="w-8 h-8 p-1.5 bg-blue-100 text-blue-600 rounded-lg" />
            Data Flow Overrides
          </h1>
          <p className="text-gray-500 mt-1">
            Map UI screens to their correct primary database table. Rows with <AlertTriangle className="inline w-4 h-4 text-amber-500" /> were guessed by the AI and should be verified.
          </p>
        </div>
        <button 
          onClick={fetchMappings}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors"
        >
          <RefreshCcw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200 bg-gray-50/50">
          <div className="relative max-w-md">
            <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
            <input 
              type="text"
              placeholder="Search UI Label or Table Name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
            />
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-gray-400">
            <RefreshCcw className="w-6 h-6 animate-spin mx-auto mb-2 opacity-50" />
            <p>Loading mappings...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-500 uppercase bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium">UI Label / Route</th>
                  <th className="px-6 py-4 font-medium">Target DB Table</th>
                  <th className="px-6 py-4 font-medium">Source File</th>
                  <th className="px-6 py-4 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredMappings.length === 0 ? (
                  <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-400">No mappings found.</td></tr>
                ) : (
                  filteredMappings.map(mapping => (
                    <tr key={mapping.id} className={`hover:bg-gray-50/50 transition-colors ${mapping.is_doubtful ? 'bg-amber-50/20' : ''}`}>
                      <td className="px-6 py-4 w-12">
                        {mapping.is_doubtful ? (
                          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-amber-100 text-amber-600" title="Doubtful mapping (guessed from URL)">
                            <AlertTriangle className="w-4 h-4" />
                          </div>
                        ) : (
                          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-emerald-100 text-emerald-600" title="Verified mapping (extracted from SQL)">
                            <Check className="w-4 h-4" />
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="font-medium text-gray-900">{mapping.ui_label}</div>
                        {mapping.base_query && (
                          <div className="mt-2 text-xs font-mono text-emerald-700 bg-emerald-50 p-2 rounded border border-emerald-100 break-all max-h-32 overflow-y-auto">
                            {mapping.base_query}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {editingId === mapping.id ? (
                          <input 
                            type="text" 
                            className="w-full px-3 py-1.5 border border-blue-300 rounded focus:ring-2 focus:ring-blue-500 outline-none"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && saveEdit(mapping.id)}
                            autoFocus
                          />
                        ) : (
                          <span className={`font-mono px-2 py-1 rounded ${mapping.is_doubtful ? 'bg-amber-50 text-amber-700 border border-amber-200/50' : 'bg-gray-100 text-gray-700'}`}>
                            {mapping.database_table}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-gray-500 text-xs font-mono max-w-[200px] truncate" title={mapping.source_file || 'Unknown'}>
                        {mapping.source_file ? mapping.source_file.split('/').pop() : 'Unknown'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {editingId === mapping.id ? (
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => saveEdit(mapping.id)} className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded"><Check className="w-4 h-4" /></button>
                            <button onClick={cancelEdit} className="p-1.5 text-gray-400 hover:bg-gray-100 rounded"><X className="w-4 h-4" /></button>
                          </div>
                        ) : (
                          <button onClick={() => startEdit(mapping)} className="p-1.5 text-blue-600 hover:bg-blue-50 rounded inline-flex items-center gap-1 text-xs font-medium">
                            <Pencil className="w-3.5 h-3.5" /> Edit
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default SemanticMappingsPage;
