import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';
import { Search, Database, Check, Loader2 } from 'lucide-react';

interface TableDiscoveryStepProps {
  onSuccess: (tables: string[]) => void;
}

export const TableDiscoveryStep: React.FC<TableDiscoveryStepProps> = ({ onSuccess }) => {
  const { clientId } = useAdmin();
  const [tables, setTables] = useState<any[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchTables();
  }, []);

  const fetchTables = async () => {
    if (!clientId) return;
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/clients/${clientId}/tables`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.tables) {
        setTables(data.tables);
        const important = data.tables
          .filter((t: any) => /sales|orders|invoice|customer|product|item|user|lead/i.test(t.name))
          .map((t: any) => t.name);
        setSelectedTables(important);
      } else {
        setError(data.detail || 'Failed to discover tables');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const toggleTable = (name: string) => {
    setSelectedTables(prev =>
      prev.includes(name) ? prev.filter(t => t !== name) : [...prev, name]
    );
  };

  const filteredTables = tables.filter(t =>
    t.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-4" style={{ height: '460px' }}>

      {/* Header */}
      <div className="shrink-0">
        <h3 className="text-lg font-bold text-gray-900">Choose Your Data Sources</h3>
        <p className="text-xs text-gray-400 mt-0.5">Select the tables you want Amoeba AI to analyze. We've pre-ticked the important ones.</p>
      </div>

      {/* Searchbar + Bulk Buttons */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search tables..."
            className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-xl focus:outline-none focus:border-blue-400 bg-gray-50 focus:bg-white transition-all"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>
        <button
          onClick={() => setSelectedTables(tables.map(t => t.name))}
          className="text-xs font-bold bg-blue-50 text-blue-700 px-3 py-2 rounded-xl border border-blue-100 hover:bg-blue-100 transition whitespace-nowrap"
          disabled={loading}
        >
          Select All
        </button>
        <button
          onClick={() => setSelectedTables([])}
          className="text-xs font-bold bg-gray-50 text-gray-600 px-3 py-2 rounded-xl border border-gray-200 hover:bg-gray-100 transition whitespace-nowrap"
          disabled={loading}
        >
          Clear
        </button>
      </div>

      {/* Table grid */}
      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3">
          <Loader2 className="animate-spin text-blue-500" size={32} />
          <p className="text-sm text-gray-400">Scanning your database...</p>
        </div>
      ) : error ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center gap-2">
          <p className="text-red-500 text-sm">{error}</p>
          <button onClick={fetchTables} className="text-xs text-blue-600 underline">Retry</button>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto min-h-0">
          {filteredTables.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 gap-2">
              <Search size={24} className="opacity-30" />
              <p className="text-xs font-bold uppercase tracking-widest">No tables match "{searchTerm}"</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5 pb-2">
              {filteredTables.map(table => {
                const isSelected = selectedTables.includes(table.name);
                return (
                  <button
                    key={table.name}
                    onClick={() => toggleTable(table.name)}
                    className={`p-3 rounded-xl border-2 text-left transition-all relative ${
                      isSelected
                        ? 'bg-blue-600 text-white border-blue-600 shadow-md shadow-blue-100'
                        : 'bg-white text-gray-700 border-gray-100 hover:border-blue-200 hover:bg-blue-50/30'
                    }`}
                  >
                    <Database size={12} className={`mb-1.5 ${isSelected ? 'text-blue-200' : 'text-gray-400'}`} />
                    <div className="font-semibold text-xs truncate">{table.name}</div>
                    <div className={`text-[10px] mt-0.5 ${isSelected ? 'text-blue-200' : 'text-gray-400'}`}>
                      {table.columns?.length || 0} columns
                    </div>
                    {isSelected && (
                      <div className="absolute top-2 right-2">
                        <Check size={12} className="text-blue-200" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between shrink-0 pt-1 border-t border-gray-100">
        <span className="text-xs text-gray-400 font-medium">
          {selectedTables.length} of {tables.length} tables selected
        </span>
        <button
          onClick={() => onSuccess(selectedTables)}
          disabled={selectedTables.length === 0}
          className="bg-blue-600 text-white px-6 py-2.5 rounded-xl font-bold text-sm hover:bg-blue-700 disabled:opacity-50 transition-all shadow-md shadow-blue-100"
        >
          Confirm Selection →
        </button>
      </div>
    </div>
  );
};
