import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';
import { Plus, Trash2, Map, Layout, Table, Pencil, RefreshCcw, Search, Activity, Globe, Zap } from 'lucide-react';
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
  const [activeTab, setActiveTab] = useState<'map' | 'config'>('map');
  const [searchTerm, setSearchTerm] = useState("");
  
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
    setLoading(true);
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
        await fetchItems();
        setActiveTab('map');
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
    setActiveTab('config');
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

  const filteredItems = items.filter(item => 
    item.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.module.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.table_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-4 md:p-6 w-full max-w-[1400px] mx-auto min-h-screen flex flex-col">
      {/* Header */}
      <header className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white p-6 rounded-[32px] shadow-sm border border-gray-100">
        <div className="flex items-center gap-4">
          <div className="bg-gradient-to-br from-blue-600 to-indigo-700 p-3 rounded-2xl text-white shadow-xl shadow-blue-200">
             <Map size={28} />
          </div>
          <div>
              <h1 className="text-2xl font-black text-gray-900 tracking-tight">Intelligent Routing</h1>
              <p className="text-gray-500 text-xs font-medium">Map natural language intents to ERP modules and tables.</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
            <div className="relative group">
                <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                <input 
                    type="text"
                    placeholder="Search routes..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-11 pr-4 py-3 bg-gray-50 border border-transparent rounded-2xl text-sm focus:outline-none focus:bg-white focus:border-blue-100 focus:ring-4 focus:ring-blue-50 shadow-sm w-[200px] md:w-[250px] transition-all focus:md:w-[320px] font-bold"
                />
            </div>
            <button 
                onClick={fetchItems}
                className="p-3 text-gray-500 hover:bg-gray-100 rounded-2xl transition-all border border-gray-100 bg-white shadow-sm"
                title="Refresh Map"
            >
                <RefreshCcw size={20} className={loading ? "animate-spin" : ""} />
            </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="inline-flex bg-gray-100/50 p-1.5 rounded-2xl mb-8 self-start border border-gray-100 shadow-inner">
        <button 
            onClick={() => setActiveTab('map')}
            className={`px-8 py-3 rounded-xl text-sm font-black transition-all flex items-center gap-2 ${
                activeTab === 'map' ? 'bg-white text-blue-600 shadow-md ring-1 ring-gray-100' : 'text-gray-500 hover:text-gray-700'
            }`}
        >
            <Activity size={18} />
            ACTIVE MAP
            <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded-full ${activeTab === 'map' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'}`}>{items.length}</span>
        </button>
        <button 
            onClick={() => setActiveTab('config')}
            className={`px-8 py-3 rounded-xl text-sm font-black transition-all flex items-center gap-2 ${
                activeTab === 'config' ? 'bg-white text-blue-600 shadow-md ring-1 ring-gray-100' : 'text-gray-500 hover:text-gray-700'
            }`}
        >
            <Plus size={18} />
            {editingId ? 'EDIT CONFIG' : 'CONFIGURE NEW'}
            {editingId && <span className="ml-2 w-2 h-2 bg-orange-500 rounded-full animate-pulse" />}
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 bg-white rounded-[40px] shadow-2xl shadow-gray-200/50 border border-gray-100 overflow-hidden flex flex-col">
          {activeTab === 'map' ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse table-fixed">
                        <thead>
                            <tr className="bg-gray-50/50 border-b border-gray-100">
                                <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[15%]">Group</th>
                                <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[25%]">Page Name</th>
                                <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[25%]">System Path</th>
                                <th className="px-6 py-5 text-[10px] font-black text-gray-400 uppercase tracking-widest w-[20%]">Data Table</th>
                                <th className="px-6 py-5 text-right text-[10px] font-black text-gray-400 uppercase tracking-widest w-[15%]">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                            {loading && items.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="px-8 py-20 text-center">
                                        <div className="flex flex-col items-center gap-4">
                                            <div className="w-10 h-10 border-4 border-blue-100 border-t-blue-600 rounded-full animate-spin"></div>
                                            <p className="text-gray-400 font-medium">Synchronizing routing table...</p>
                                        </div>
                                    </td>
                                </tr>
                            ) : filteredItems.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="px-8 py-20 text-center">
                                        <div className="flex flex-col items-center gap-4 opacity-30">
                                            <Globe size={64} className="text-gray-300" />
                                            <p className="text-xl font-bold text-gray-400 font-black">No matching routes found</p>
                                        </div>
                                    </td>
                                </tr>
                            ) : (
                                filteredItems.map((item) => (
                                    <tr key={item.id} className="hover:bg-blue-50/20 transition-all group border-b border-gray-50 last:border-0 text-sm">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2">
                                                <div className="w-7 h-7 bg-blue-100/50 text-blue-700 rounded-lg flex items-center justify-center font-black text-[9px] shrink-0">
                                                    {item.module.substring(0, 2).toUpperCase()}
                                                </div>
                                                <span className="font-bold text-gray-500 truncate" title={item.module}>{item.module}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="text-gray-900 font-bold truncate block" title={item.label}>{item.label}</span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2 px-2 py-1 bg-gray-50 border border-gray-100 rounded-lg w-full">
                                                <Globe size={11} className="text-gray-400 shrink-0" />
                                                <span className="text-[10px] font-mono font-bold text-gray-400 truncate break-all">{item.path}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-2 text-indigo-600 bg-indigo-50/30 px-2 py-1 rounded-lg border border-indigo-100/50 w-full">
                                                <Table size={12} className="shrink-0" />
                                                <span className="font-mono text-[10px] font-black uppercase tracking-wider truncate">{item.table_name}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                <button 
                                                    onClick={() => startEdit(item)}
                                                    className="p-2 bg-white border border-blue-100 text-blue-600 hover:bg-blue-600 hover:text-white rounded-lg shadow-sm transition-all flex items-center gap-1 font-black text-[9px] shrink-0"
                                                    title="Edit configuration"
                                                >
                                                    <Pencil size={12} />
                                                    EDIT
                                                </button>
                                                <button 
                                                    onClick={() => item.id && deleteItem(item.id)}
                                                    className="p-2 bg-white border border-red-100 text-red-500 hover:bg-red-500 hover:text-white rounded-lg shadow-sm transition-all shrink-0"
                                                    title="Delete mapping"
                                                >
                                                    <Trash2 size={12} />
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
          ) : (
              <div className="flex-1 p-8 md:p-12 max-w-4xl mx-auto w-full overflow-y-auto">
                  <div className="mb-10 text-center">
                      <div className={`w-14 h-14 mx-auto mb-4 rounded-2xl flex items-center justify-center shadow-lg ${editingId ? 'bg-orange-100 text-orange-600 shadow-orange-100' : 'bg-blue-100 text-blue-600 shadow-blue-100'}`}>
                          {editingId ? <Pencil size={24} /> : <Zap size={24} fill="currentColor" />}
                      </div>
                      <h2 className="text-2xl font-black text-gray-900 tracking-tight">
                          {editingId ? 'Modify Current Settings' : 'Create New Shortcut'}
                      </h2>
                      <p className="text-gray-500 mt-2 font-medium text-sm">Tell the AI where your ERP pages live and where they store info.</p>
                  </div>

                  <form onSubmit={addItem} className="space-y-10">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-left">
                        <section className="space-y-3">
                            <label className="text-[11px] font-black text-blue-600 uppercase tracking-widest block px-1">1. Department / Group</label>
                            <p className="text-[10px] text-gray-400 italic px-1">Which section does this belong to? (e.g. Sales, HR)</p>
                            <div className="relative group">
                                <Layout size={18} className="absolute left-5 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-blue-500" />
                                <input
                                    type="text"
                                    placeholder="e.g. Sales"
                                    required
                                    className="w-full pl-14 pr-6 py-4 bg-gray-50 border-2 border-transparent rounded-[20px] focus:bg-white focus:border-blue-100 focus:ring-8 focus:ring-blue-50/50 outline-none transition-all font-bold text-gray-900"
                                    value={newItem.module}
                                    onChange={(e) => setNewItem({ ...newItem, module: e.target.value })}
                                />
                            </div>
                        </section>
                        <section className="space-y-3">
                            <label className="text-[11px] font-black text-blue-600 uppercase tracking-widest block px-1">2. Direct Action / Page Name</label>
                            <p className="text-[10px] text-gray-400 italic px-1">What will you ask the AI to find? (e.g. Create Lead)</p>
                            <div className="relative group">
                                <Search size={18} className="absolute left-5 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-blue-500" />
                                <input
                                    type="text"
                                    placeholder="e.g. Lead Creation"
                                    required
                                    className="w-full pl-14 pr-6 py-4 bg-gray-50 border-2 border-transparent rounded-[20px] focus:bg-white focus:border-blue-100 focus:ring-8 focus:ring-blue-50/50 outline-none transition-all font-bold text-gray-900"
                                    value={newItem.label}
                                    onChange={(e) => setNewItem({ ...newItem, label: e.target.value })}
                                />
                            </div>
                        </section>
                    </div>

                    <section className="space-y-4 text-left">
                        <div className="flex items-center justify-between px-1">
                            <label className="text-[11px] font-black text-blue-600 uppercase tracking-widest block">3. Target Page (Where to go)</label>
                        </div>
                        <div className="bg-gradient-to-br from-blue-50/30 to-indigo-50/30 p-6 rounded-[28px] border border-blue-100 space-y-4">
                            <div>
                                <p className="text-[10px] text-blue-400 font-bold uppercase mb-2 px-1">Option A: Select From System List</p>
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
                                    placeholder="Click to browse your ERP pages..."
                                />
                            </div>
                            
                            <div className="flex items-center gap-4 py-2">
                                <div className="h-px bg-blue-100 flex-1"></div>
                                <span className="text-[9px] font-black text-blue-200 uppercase tracking-widest">OR ENTER A CUSTOM URL</span>
                                <div className="h-px bg-blue-100 flex-1"></div>
                            </div>

                            <div>
                                <input
                                    type="text"
                                    placeholder="Paste URL here (e.g. /app/sales/new)"
                                    className="w-full px-6 py-4 bg-white border border-blue-100 rounded-[16px] shadow-sm outline-none focus:ring-8 focus:ring-blue-100/30 font-mono text-xs font-bold text-gray-500 placeholder:text-gray-300"
                                    value={newItem.path}
                                    onChange={(e) => setNewItem({ ...newItem, path: e.target.value })}
                                />
                            </div>
                        </div>
                    </section>

                    <section className="space-y-4 text-left">
                        <label className="text-[11px] font-black text-blue-600 uppercase tracking-widest block px-1">4. Data Source (Technical Table)</label>
                        <div className="bg-gray-50 p-6 rounded-[24px] border border-gray-100 border-dashed">
                             <p className="text-[10px] text-gray-500 mb-4 px-1 leading-relaxed">
                                <span className="font-black text-indigo-600">Why?</span> The AI uses this table to automatically read information from this page or save new data when you chat with it. Without this, the AI can't "see" what's on the screen.
                             </p>
                             <SearchableDropdown
                                options={tables.map((t) => ({ value: t.name, label: t.name }))}
                                value={newItem.table_name}
                                onChange={(val) => setNewItem({ ...newItem, table_name: val })}
                                placeholder="Search for technical table..."
                             />
                        </div>
                    </section>

                    <div className="flex flex-col md:flex-row gap-4 pt-6">
                        <button
                            type="button"
                            onClick={() => { setActiveTab('map'); setEditingId(null); setNewItem({label: '', module: '', table_name: '', path: ''}); }}
                            className="flex-1 px-8 py-5 border-2 border-gray-100 rounded-[24px] font-black text-gray-400 hover:bg-gray-50 hover:text-gray-600 hover:border-gray-200 transition-all text-sm"
                        >
                            DISCARD CHANGES
                        </button>
                        <button
                            type="submit"
                            className={`flex-[2] py-5 rounded-[24px] font-black text-lg transition-all shadow-2xl flex items-center justify-center gap-3 ${
                                editingId ? 'bg-orange-600 hover:bg-orange-700 shadow-orange-100' : 'bg-blue-600 hover:bg-blue-700 shadow-blue-200 shadow shadow-xl'
                            } text-white active:scale-[0.98]`}
                        >
                            {editingId ? <Pencil size={20} /> : <Zap size={20} fill="currentColor" />}
                            {editingId ? 'SAVE UPDATES' : 'SAVE ROUTE'}
                        </button>
                    </div>
                  </form>
              </div>
          )}
      </div>
    </div>
  );
};

export default RouteMap;
