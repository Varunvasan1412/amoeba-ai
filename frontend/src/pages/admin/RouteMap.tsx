import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';
import { Plus, Trash2, Map, Layout, Table, Pencil, X } from 'lucide-react';
import { SearchableDropdown } from '../../components/admin/SearchableDropdown';
import { apiFetch } from '../../utils/api';

interface NavigationItem {
  id?: number;
  label: string;
  module: string;
  table_name: string;
  path: string;
  client_id: number;
}

const RouteMap: React.FC = () => {
  const { clientId } = useAdmin();
  const [items, setItems] = useState<NavigationItem[]>([]);
  const [tables, setTables] = useState<any[]>([]);
  const [sitemap, setSitemap] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [newItem, setNewItem] = useState({
    label: '',
    module: '',
    table_name: '',
    path: ''
  });
  const [editingId, setEditingId] = useState<number | null>(null);

  useEffect(() => {
    if (clientId) {
      fetchItems();
      fetchTables();
      fetchSitemap();
    }
  }, [clientId]);

  const fetchItems = async () => {
    try {
      const res = await apiFetch(`/navigation?client_id=${clientId}`);
      const data = await res.json();
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch navigation items', err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchSitemap = async () => {
    try {
      const res = await apiFetch(`/sitemap-data?client_id=${clientId}`);
      const data = await res.json();
      setSitemap(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to fetch sitemap', err);
    }
  };

  const fetchTables = async () => {
    if (!clientId) return;
    try {
      const res = await apiFetch(`/clients/${clientId}/tables`);
      const data = await res.json();
      setTables(Array.isArray(data.tables) ? data.tables : []);
    } catch (err) {
      console.error('Failed to fetch tables', err);
      setTables([]);
    }
  };

  const normalizePath = (p: string) => {
    if (!p) return '';
    try {
      // If it's a full URL, we extract just the path
      if (p.startsWith('http')) {
        const url = new URL(p);
        return url.pathname;
      }
      return p;
    } catch (e) {
      return p;
    }
  };

  const addItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientId) return;

    const finalPath = normalizePath(newItem.path.trim() !== '' 
      ? newItem.path 
      : `/${newItem.module.toLowerCase()}/${newItem.label.toLowerCase().replace(/\s+/g, '-')}`);

    try {
      const url = editingId ? `/navigation/${editingId}` : `/navigation`;
      const method = editingId ? 'PUT' : 'POST';

      const res = await apiFetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...newItem,
          id: editingId || undefined,
          client_id: clientId,
          path: finalPath
        })
      });

      if (res.ok) {
        setNewItem({ label: '', module: '', table_name: '', path: '' });
        setEditingId(null);
        fetchItems();
      }
    } catch (err) {
      console.error('Failed to save navigation item', err);
    }
  };

  const startEdit = (item: NavigationItem) => {
    setEditingId(item.id || null);
    setNewItem({
      label: item.label,
      module: item.module,
      table_name: item.table_name,
      path: item.path
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const deleteItem = async (id: number) => {
    if (!confirm('Are you sure you want to delete this route mapping?')) return;
    try {
      const res = await apiFetch(`/navigation/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) fetchItems();
    } catch (err) {
      console.error('Failed to delete navigation item', err);
    }
  };

  if (!clientId) return <div className="p-8 text-center text-gray-500 font-black uppercase tracking-widest text-xs">Please select a client first.</div>;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <div className="bg-blue-600 p-2.5 rounded-xl text-white shadow-lg shadow-blue-200">
           <Map size={24} />
        </div>
        <div>
            <h1 className="text-2xl font-bold text-gray-900">Route Context Map</h1>
            <p className="text-gray-500 text-sm">Map user intents to specific ERP tables and modules.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Form Column */}
        <div className="lg:col-span-1">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <h3 className="text-lg font-semibold mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {editingId ? <Pencil size={18} className="text-orange-600" /> : <Plus size={18} className="text-blue-600" />}
                    {editingId ? 'Edit Route' : 'Add New Route'}
                </div>
                {editingId && (
                    <button 
                        onClick={() => { setEditingId(null); setNewItem({ label: '', module: '', table_name: '', path: '' }); }}
                        className="text-gray-400 hover:text-gray-600 p-1 hover:bg-gray-100 rounded-lg transition-all"
                        title="Cancel editing"
                    >
                        <X size={16} />
                    </button>
                )}
            </h3>
            <form onSubmit={addItem} className="space-y-5">
              <div>
                <label className="block text-xs font-black text-indigo-600 uppercase tracking-widest mb-1">1. Business Module</label>
                <p className="text-[10px] text-slate-400 mb-2 italic">The broad category (e.g. Sales, HR, CRM, Finance)</p>
                <input
                  type="text"
                  placeholder="e.g. CRM"
                  required
                  className="w-full border-gray-200 bg-gray-50 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                  value={newItem.module}
                  onChange={(e) => setNewItem({ ...newItem, module: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs font-black text-blue-600 uppercase tracking-widest mb-1">2. Friendly Page Name</label>
                <p className="text-[10px] text-slate-400 mb-2 italic">The name users use in chat (e.g. Employee List, Contact Creation)</p>
                <input
                  type="text"
                  placeholder="e.g. Contact List"
                  required
                  className="w-full border-gray-200 bg-gray-50 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                  value={newItem.label}
                  onChange={(e) => setNewItem({ ...newItem, label: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs font-black text-green-600 uppercase tracking-widest mb-1">3. ERP Page / URL</label>
                <p className="text-[10px] text-slate-400 mb-2 italic">Select an existing system page or type a custom path</p>
                <div className="space-y-2">
                  <SearchableDropdown
                    options={sitemap.map((s) => ({ value: s.path, label: `${s.module ? s.module + ' > ' : ''}${s.label}` }))}
                    value={newItem.path}
                    onChange={(val) => {
                      const selected = sitemap.find(s => s.path === val);
                      setNewItem(prev => ({
                        ...prev,
                        path: val,
                        module: prev.module || (selected?.module || ''),
                        label: prev.label || (selected?.label || '')
                      }));
                    }}
                    placeholder="Search system pages..."
                  />
                  <input
                    type="text"
                    placeholder="...or type custom path (e.g. /my/custom/url)"
                    className="w-full border-gray-200 bg-gray-50 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-100 outline-none transition-all"
                    value={newItem.path}
                    onChange={(e) => setNewItem({ ...newItem, path: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-black text-purple-600 uppercase tracking-widest mb-1">4. Underlying Database Table</label>
                <p className="text-[10px] text-slate-400 mb-2 italic">The technical table where this page saves its data</p>
                <SearchableDropdown
                  options={tables.map((t) => ({ value: t.name, label: t.name }))}
                  value={newItem.table_name}
                  onChange={(val) => setNewItem({ ...newItem, table_name: val })}
                  placeholder="Search technical tables..."
                />
              </div>
              <button
                type="submit"
                className={`w-full ${editingId ? 'bg-orange-600 hover:bg-orange-700 shadow-orange-100' : 'bg-blue-600 hover:bg-blue-700 shadow-blue-100'} text-white py-3 rounded-xl font-bold transition-all shadow-lg flex items-center justify-center gap-2 mt-2`}
              >
                {editingId ? <Pencil size={18} /> : <Plus size={18} />}
                {editingId ? 'Update Route Context' : 'Save Route Context'}
              </button>
            </form>
          </div>
        </div>

        {/* List Column */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-visible">
             <div className="p-6 border-b border-gray-50">
                <h3 className="text-lg font-semibold">Active Route Map</h3>
             </div>
             <div className="overflow-x-auto">
                <table className="w-full">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Module</th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Page Name</th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">Mapped Path</th>
                            <th className="px-6 py-4 text-left text-xs font-bold text-gray-400 uppercase tracking-wider">ERP Table</th>
                            <th className="px-6 py-4 text-right text-xs font-bold text-gray-400 uppercase tracking-wider">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                        {loading ? (
                            <tr><td colSpan={4} className="px-6 py-10 text-center text-gray-400">Loading context map...</td></tr>
                        ) : items.length === 0 ? (
                            <tr><td colSpan={4} className="px-6 py-10 text-center text-gray-400">No routes mapped yet.</td></tr>
                        ) : (
                            items.map((item) => (
                                <tr key={item.id} className="hover:bg-gray-50 transition-colors group">
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2">
                                            <div className="p-1.5 bg-purple-50 text-purple-600 rounded-lg">
                                                <Layout size={14} />
                                            </div>
                                            <span className="font-semibold text-gray-700">{item.module}</span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className="text-gray-600 font-medium">{item.label}</span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="text-[10px] font-mono text-gray-400 break-all max-w-[200px]" title={item.path}>
                                            {item.path}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-2 text-gray-500 font-mono text-xs">
                                            <Table size={12} />
                                            {item.table_name}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex items-center justify-end gap-1">
                                            <button 
                                                onClick={() => startEdit(item)}
                                                className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-all"
                                                title="Edit route mapping"
                                            >
                                                <Pencil size={16} />
                                            </button>
                                            <button 
                                                onClick={() => item.id && deleteItem(item.id)}
                                                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all"
                                                title="Delete route mapping"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RouteMap;
