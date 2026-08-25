import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';
import { apiFetch } from '../../utils/api';
import { Search, Link2, ToggleLeft, ToggleRight, Loader2, AlertTriangle } from 'lucide-react';

interface RelationshipStepProps {
  onSuccess: () => void;
}

export const RelationshipStep: React.FC<RelationshipStepProps> = ({ onSuccess }) => {
  const { apiKey } = useAdmin();
  const [relationships, setRelationships] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchRelationships();
  }, []);

  const fetchRelationships = async (sync = false) => {
    if (sync) setSyncing(true);
    else setLoading(true);
    
    setError('');
    try {
      const url = sync ? '/api/v2/relationships?sync=true' : '/api/v2/relationships';
      const response = await apiFetch(url, {
        headers: { 'X-API-Key': apiKey || '' }
      });
      const data = await response.json();
      if (Array.isArray(data)) {
        setRelationships(data);
      } else {
        setError('Failed to fetch connections');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
      setSyncing(false);
    }
  };

  const toggleRelationship = async (relId: number, currentStatus: boolean) => {
    setRelationships(prev =>
      prev.map(r => r.id === relId ? { ...r, is_enabled: !currentStatus } : r)
    );
    try {
      const response = await apiFetch(`/api/v2/relationships/${relId}/toggle`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey || ''
        },
        body: JSON.stringify({ is_enabled: !currentStatus })
      });
      if (!response.ok) throw new Error('Failed to toggle');
    } catch (err) {
      console.error('Failed to toggle connection', err);
      setRelationships(prev =>
        prev.map(r => r.id === relId ? { ...r, is_enabled: currentStatus } : r)
      );
    }
  };

  const handleBulkAction = async (action: 'enable_all' | 'disable_all') => {
    try {
      setRelationships(prev => prev.map(r => ({ ...r, is_enabled: action === 'enable_all' })));
      const response = await apiFetch('/api/v2/relationships/bulk-update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey || ''
        },
        body: JSON.stringify({ action })
      });
      if (!response.ok) throw new Error('Bulk action failed');
    } catch (err) {
      console.error('Failed to perform bulk action', err);
      setError('Bulk action failed');
      await fetchRelationships();
    }
  };

  const filteredRels = relationships.filter(rel =>
    [rel.parent_table, rel.child_table, rel.parent_column, rel.child_column]
      .some(s => s.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const enabledCount = relationships.filter(r => r.is_enabled).length;

  return (
    <div className="flex flex-col gap-4" style={{ height: '460px' }}>

      {/* Header */}
      <div className="flex justify-between items-start shrink-0">
        <div>
          <h3 className="text-lg font-bold text-gray-900">Enable Data Connections</h3>
          <p className="text-xs text-gray-400 mt-0.5">We've discovered how your tables link together. Enable the ones you want to use for multi-table analysis.</p>
        </div>
        <button 
          onClick={() => { fetchRelationships(true); }} 
          disabled={syncing || loading}
          className="text-[10px] font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1 uppercase tracking-wider"
        >
          {syncing ? <Loader2 size={10} className="animate-spin" /> : <Link2 size={10} />}
          Refresh Discovery
        </button>
      </div>

      {/* Search + bulk actions */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search connections..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-400 bg-gray-50 focus:bg-white transition-all"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>
        <button
          onClick={() => handleBulkAction('enable_all')}
          disabled={loading || syncing}
          className="text-xs font-bold bg-emerald-50 text-emerald-700 px-3 py-2 rounded-xl border border-emerald-100 hover:bg-emerald-100 transition whitespace-nowrap"
        >
          Enable All
        </button>
        <button
          onClick={() => handleBulkAction('disable_all')}
          disabled={loading || syncing}
          className="text-xs font-bold bg-gray-50 text-gray-600 px-3 py-2 rounded-xl border border-gray-200 hover:bg-gray-100 transition whitespace-nowrap"
        >
          Disable All
        </button>
      </div>

      {/* Status or Syncing */}
      {syncing ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3">
          <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center animate-pulse">
            <Link2 size={24} />
          </div>
          <div className="text-center">
            <p className="text-sm font-bold text-gray-700">Analyzing Schema...</p>
            <p className="text-[10px] text-gray-400">Finding foreign keys and inferring links.</p>
          </div>
        </div>
      ) : (
        <>
          {/* Stats */}
          {!loading && relationships.length > 0 && (
            <div className="text-xs text-gray-400 font-medium shrink-0 -mt-2">
              {enabledCount} of {relationships.length} connections enabled
              {searchTerm && ` · showing ${filteredRels.length} results`}
            </div>
          )}

          {/* Connection list */}
          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3">
              <Loader2 className="animate-spin text-blue-500" size={32} />
              <p className="text-sm text-gray-400">Loading discovery results...</p>
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2">
              <AlertTriangle size={20} className="text-red-400" />
              <p className="text-red-500 text-sm">{error}</p>
              <button onClick={() => { fetchRelationships(); }} className="text-xs text-blue-600 underline">Retry</button>
            </div>
          ) : relationships.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-gray-100 rounded-2xl gap-4">
              <div className="w-16 h-16 bg-gray-50 text-gray-300 rounded-full flex items-center justify-center">
                <Link2 size={32} />
              </div>
              <div>
                <p className="text-gray-600 font-bold">No connections discovered yet.</p>
                <p className="text-xs text-gray-400 max-w-[200px] mx-auto mt-1">Run a fresh scan to find how your tables link together.</p>
              </div>
              <button 
                onClick={() => { fetchRelationships(true); }} 
                className="bg-blue-600 text-white px-8 py-3 rounded-xl text-sm font-bold shadow-lg shadow-blue-100 hover:bg-blue-700 transition-all flex items-center gap-2"
              >
                <Link2 size={16} /> Discover Connections
              </button>
              <button 
                onClick={onSuccess} 
                className="text-[10px] font-bold text-gray-400 hover:text-gray-600 uppercase tracking-widest"
              >
                Skip for now →
              </button>
            </div>
          ) : filteredRels.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center gap-2">
              <Search size={20} className="text-gray-300" />
              <p className="text-xs text-gray-400 font-bold uppercase tracking-widest">No match for "{searchTerm}"</p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto min-h-0 space-y-2 pb-2">
              {filteredRels.map(rel => (
                <div
                  key={rel.id}
                  onClick={() => toggleRelationship(rel.id, rel.is_enabled)}
                  className={`flex items-center justify-between px-4 py-3 rounded-xl border-2 cursor-pointer transition-all group ${
                    rel.is_enabled
                      ? 'bg-emerald-50/50 border-emerald-200 hover:border-emerald-300'
                      : 'bg-white border-gray-100 hover:border-gray-200'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Link2 size={14} className={rel.is_enabled ? 'text-emerald-500 shrink-0' : 'text-gray-300 shrink-0'} />
                    <div className="min-w-0">
                      <div className="font-semibold text-sm text-gray-800 truncate">
                        {rel.child_table.replace(/_/g, ' ')}
                        <span className="text-gray-400 font-normal"> belongs to </span>
                        {rel.parent_table.replace(/_/g, ' ')}
                      </div>
                      <div className="text-[10px] font-mono text-gray-400 truncate">
                        {rel.child_table}.{rel.child_column} → {rel.parent_table}.{rel.parent_column}
                      </div>
                    </div>
                  </div>
                  <div className="shrink-0 ml-4">
                    {rel.is_enabled
                      ? <ToggleRight size={24} className="text-emerald-500" />
                      : <ToggleLeft size={24} className="text-gray-300" />
                    }
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Footer */}
          {relationships.length > 0 && (
            <div className="flex items-center justify-between shrink-0 pt-1 border-t border-gray-100">
              <p className="text-[11px] text-gray-400">💡 Click any row to toggle a connection.</p>
              <button
                onClick={onSuccess}
                className="bg-blue-600 text-white px-6 py-2.5 rounded-xl font-bold text-sm hover:bg-blue-700 transition-all shadow-md shadow-blue-100"
              >
                Done with Connections →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
