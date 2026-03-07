import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';

interface SemanticSuggestionStepProps {
  selectedTables: string[];
  onSuccess: (mappings: any[]) => void;
}

export const SemanticSuggestionStep: React.FC<SemanticSuggestionStepProps> = ({ selectedTables, onSuccess }) => {
  const { clientId, apiKey } = useAdmin();
  const [mappings, setMappings] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    generateSuggestions();
  }, [selectedTables]);

  const generateSuggestions = async () => {
    if (!clientId) return;
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`http://localhost:8000/api/clients/${clientId}/tables`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      
      const allTables = data.tables || [];
      const filtered = allTables.filter((t: any) => selectedTables.includes(t.name));
      
      const suggestions: any[] = [];
      
      filtered.forEach((table: any) => {
        table.columns.forEach((col: string) => {
          // Rule-based suggestion
          let label = col.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
          let data_format = "text";
          let is_default_date = false;

          if (col.toLowerCase().endsWith('_id')) {
            label = label.replace('Id', 'Identifier');
          } else if (/amount|total|price|cost/i.test(col) || (/tax/i.test(col) && !/number|id|code/i.test(col))) {
            data_format = "currency";
          } else if (/date|created_at|updated_at|timestamp/i.test(col)) {
            data_format = "date";
            is_default_date = /order_date|created_at/i.test(col);
          } else if (/name|title|label/i.test(col)) {
            label = label.replace('Name', 'Business Name');
          }

          suggestions.push({
            table_name: table.name,
            column_name: col,
            label: label,
            data_format: data_format,
            is_default_date: is_default_date,
            is_pii: /email|phone|address|ssn/i.test(col)
          });
        });
      });
      
      setMappings(suggestions);
    } catch (err) {
      setError('Failed to generate suggestions');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateLabel = (index: number, newLabel: string) => {
    const updated = [...mappings];
    updated[index].label = newLabel;
    setMappings(updated);
  };

  const handleSave = async () => {
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('http://localhost:8000/api/v2/semantic/columns', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-API-Key': apiKey || ''
        },
        body: JSON.stringify({ mappings })
      });
      
      if (response.ok) {
        onSuccess(mappings);
      } else {
        const data = await response.json();
        setError(data.detail || 'Failed to save business names');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
        <h3 className="text-blue-800 font-semibold">Step 3: Business Names</h3>
        <p className="text-blue-600 text-sm">Amoeba AI has suggested business names for your columns. Review and edit them so everyone understands the data.</p>
      </div>

      {loading && mappings.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Generating suggestions...</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="max-h-96 overflow-y-auto border rounded-lg">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Table</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Column</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Business Name</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {mappings.map((m, idx) => (
                  <tr key={`${m.table_name}-${m.column_name}`}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{m.table_name}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">{m.column_name}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <input
                        type="text"
                        className="border rounded px-2 py-1 w-full text-sm"
                        value={m.label}
                        onChange={(e) => handleUpdateLabel(idx, e.target.value)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <div className="flex justify-end gap-3">
            <button
              onClick={handleSave}
              disabled={loading}
              className="bg-blue-600 text-white px-8 py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Saving...' : 'Accept All & Continue'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
