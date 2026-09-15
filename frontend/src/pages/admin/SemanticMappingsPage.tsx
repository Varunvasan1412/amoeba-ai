import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';
import { Table, Pencil, Check, X, AlertTriangle, RefreshCcw, Search, Database, Trash2, Plus } from 'lucide-react';
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

  // New mapping form state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newTable, setNewTable] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  const deleteMapping = async (id: number) => {
    if (!window.confirm("Are you sure you want to delete this mapping?")) return;
    try {
      const res = await apiFetch(`/v2/semantic/mappings/${id}?client_id=${clientId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        setMappings(mappings.filter(m => m.id !== id));
      }
    } catch (err) {
      console.error('Failed to delete mapping', err);
    }
  };

  const purgeAllMappings = async () => {
    if (!window.confirm("⚠️ Are you sure you want to PURGE ALL mappings for this client?\n\nThis will completely wipe all 2,600+ auto-crawled tables, ensuring Strict Manual Mapping starts 100% clean.")) return;
    setLoading(true);
    try {
      const res = await apiFetch(`/v2/semantic/mappings/purge?client_id=${clientId}`, {
        method: 'POST'
      });
      if (res.ok) {
        setMappings([]);
      }
    } catch (err) {
      console.error('Failed to purge mappings', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateMapping = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLabel.trim() || !newTable.trim()) return;
    setIsSubmitting(true);
    try {
      const res = await apiFetch(`/v2/semantic/mappings?client_id=${clientId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ui_label: newLabel.trim(),
          database_table: newTable.trim()
        })
      });
      if (res.ok) {
        const created = await res.json();
        setMappings([created, ...mappings]);
        setNewLabel("");
        setNewTable("");
        setShowAddModal(false);
      }
    } catch (err) {
      console.error('Failed to create mapping', err);
    } finally {
      setIsSubmitting(false);
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
            Map UI screens to their correct primary database table. In Strict Mode, only mapped tables are accessible.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" /> Add Mapping
          </button>
          <button 
            onClick={fetchMappings}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 font-medium transition-colors"
          >
            <RefreshCcw className="w-4 h-4" /> Refresh
          </button>
          <button 
            onClick={purgeAllMappings}
            className="flex items-center gap-2 px-4 py-2 bg-red-50 border border-red-200 text-red-600 rounded-lg hover:bg-red-100 font-medium transition-colors"
            title="Purge all auto-discovered mappings to start fresh"
          >
            <Trash2 className="w-4 h-4" /> Purge All
          </button>
        </div>
      </div>

      {showAddModal && (
        <div className="bg-white p-6 rounded-xl border border-blue-200 shadow-md">
          <h2 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
            <Plus className="w-5 h-5 text-blue-600" /> Add Custom Manual Mapping
          </h2>
          <form onSubmit={handleCreateMapping} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-gray-600 uppercase mb-1">UI Label / Screen Name</label>
              <input 
                type="text" 
                placeholder="e.g. Quotation, Quotation List, Sales Order"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-600 uppercase mb-1">Target DB Table</label>
              <input 
                type="text" 
                placeholder="e.g. enquiry_header, quotation_header"
                value={newTable}
                onChange={(e) => setNewTable(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                required
              />
            </div>
            <div className="md:col-span-2 flex justify-end gap-2 pt-2">
              <button 
                type="button" 
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm font-medium"
              >
                Cancel
              </button>
              <button 
                type="submit" 
                disabled={isSubmitting}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {isSubmitting ? "Adding..." : "Save Mapping"}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200 bg-gray-50/50 flex items-center justify-between">
          <div className="relative max-w-md w-full">
            <Search className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
            <input 
              type="text" 
              placeholder="Search UI Label or Table Name..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm"
            />
          </div>
          <div className="text-xs font-bold text-gray-500">
            Total Mappings: {mappings.length}
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
                  <th className="px-6 py-4 font-medium">Origin</th>
                  <th className="px-6 py-4 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredMappings.length === 0 ? (
                  <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-400">No mappings found. In Strict Mode, unmapped tables will be blocked.</td></tr>
                ) : (
                  filteredMappings.map(mapping => (
                    <tr key={mapping.id} className={`hover:bg-gray-50/50 transition-colors ${mapping.is_doubtful ? 'bg-amber-50/20' : ''}`}>
                      <td className="px-6 py-4 w-12">
                        {mapping.is_doubtful ? (
                          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-amber-100 text-amber-600" title="Doubtful mapping (guessed from URL)">
                            <AlertTriangle className="w-4 h-4" />
                          </div>
                        ) : (
                          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-emerald-100 text-emerald-600" title="Verified manual mapping">
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
                      <td className="px-6 py-4 text-gray-500 text-xs font-mono max-w-[200px] truncate" title={mapping.source_file || 'manual'}>
                        {mapping.source_file ? mapping.source_file.split('/').pop() : 'manual'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {editingId === mapping.id ? (
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => saveEdit(mapping.id)} className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded" title="Save"><Check className="w-4 h-4" /></button>
                            <button onClick={cancelEdit} className="p-1.5 text-gray-400 hover:bg-gray-100 rounded" title="Cancel"><X className="w-4 h-4" /></button>
                          </div>
                        ) : (
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => startEdit(mapping)} className="p-1.5 text-blue-600 hover:bg-blue-50 rounded inline-flex items-center gap-1 text-xs font-medium">
                              <Pencil className="w-3.5 h-3.5" /> Edit
                            </button>
                            <button onClick={() => deleteMapping(mapping.id)} className="p-1.5 text-red-500 hover:bg-red-50 rounded inline-flex items-center gap-1 text-xs font-medium" title="Delete mapping">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
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
