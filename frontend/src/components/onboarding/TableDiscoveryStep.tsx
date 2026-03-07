import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';

interface TableDiscoveryStepProps {
  onSuccess: (tables: string[]) => void;
}

export const TableDiscoveryStep: React.FC<TableDiscoveryStepProps> = ({ onSuccess }) => {
  const { clientId } = useAdmin();
  const [tables, setTables] = useState<any[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchTables();
  }, []);

  const fetchTables = async () => {
    if (!clientId) return;
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`http://localhost:8000/api/clients/${clientId}/tables`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.tables) {
        setTables(data.tables);
        // Pre-select tables that sound important
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

  const handleSelectAll = () => {
    setSelectedTables(tables.map(t => t.name));
  };

  const handleDeselectAll = () => {
    setSelectedTables([]);
  };

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
        <h3 className="text-blue-800 font-semibold">Step 2: Choose Data Sources</h3>
        <p className="text-blue-600 text-sm">Select the tables you want Amoeba AI to analyze. We've highlighted some common ones for you.</p>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Scanning your database...</p>
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 text-red-600 rounded-lg border border-red-200">
          {error}
          <button onClick={fetchTables} className="block mt-2 underline">Retry</button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex justify-end gap-2 mb-2">
            <button
              onClick={handleSelectAll}
              className="text-xs font-semibold bg-green-50 text-green-700 px-3 py-1.5 rounded-lg border border-green-200 hover:bg-green-100 transition"
              disabled={loading || tables.length === 0}
            >
              Select All
            </button>
            <button
              onClick={handleDeselectAll}
              className="text-xs font-semibold bg-gray-50 text-gray-700 px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-100 transition"
              disabled={loading || tables.length === 0}
            >
              Deselect All
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 max-h-96 overflow-y-auto p-1">
            {tables.map(table => (
              <button
                key={table.name}
                onClick={() => toggleTable(table.name)}
                className={`p-3 rounded-lg border text-left transition ${
                  selectedTables.includes(table.name)
                    ? 'bg-blue-600 text-white border-blue-700'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-blue-300 hover:bg-blue-50'
                }`}
              >
                <div className="font-medium truncate">{table.name}</div>
                <div className={`text-xs ${selectedTables.includes(table.name) ? 'text-blue-100' : 'text-gray-400'}`}>
                  {table.columns?.length || 0} columns
                </div>
              </button>
            ))}
          </div>

          <div className="flex justify-between items-center bg-gray-50 p-4 rounded-lg">
            <span className="text-gray-600 text-sm">Selected {selectedTables.length} data sources</span>
            <button
              onClick={() => onSuccess(selectedTables)}
              disabled={selectedTables.length === 0}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
            >
              Confirm Selection
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
