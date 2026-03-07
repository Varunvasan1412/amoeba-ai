import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';

interface RelationshipStepProps {
  onSuccess: () => void;
}

export const RelationshipStep: React.FC<RelationshipStepProps> = ({ onSuccess }) => {
  const { apiKey } = useAdmin();
  const [relationships, setRelationships] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchRelationships();
  }, []);

  const fetchRelationships = async () => {
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('http://localhost:8000/api/v2/relationships', {
        headers: { 
          'Authorization': `Bearer ${token}`,
          'X-API-Key': apiKey || ''
        }
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
    }
  };

  const toggleRelationship = async (relId: number, currentStatus: boolean) => {
    // Optimistic update
    setRelationships(prev => 
      prev.map(r => r.id === relId ? { ...r, is_enabled: !currentStatus } : r)
    );
    
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`http://localhost:8000/api/v2/relationships/${relId}/toggle`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-API-Key': apiKey || ''
        },
        body: JSON.stringify({ is_enabled: !currentStatus })
      });
      
      if (!response.ok) throw new Error('Failed to toggle');
      
    } catch (err) {
      console.error('Failed to toggle connection', err);
      // Revert on error
      setRelationships(prev => 
        prev.map(r => r.id === relId ? { ...r, is_enabled: currentStatus } : r)
      );
    }
  };

  const handleBulkAction = async (action: 'enable_all' | 'disable_all') => {
    // We don't set global loading=true here because we want the list to stay visible
    // while we perform the optimistic update.
    try {
      const token = localStorage.getItem('token');
      
      // Optimistic update - instant visual change
      setRelationships(prev => prev.map(r => ({ ...r, is_enabled: action === 'enable_all' })));
      
      const response = await fetch('http://localhost:8000/api/v2/relationships/bulk-update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'X-API-Key': apiKey || ''
        },
        body: JSON.stringify({ action: action })
      });
      
      if (!response.ok) {
        throw new Error('Bulk action failed');
      }
    } catch (err) {
      console.error('Failed to perform bulk action', err);
      setError('Bulk action failed');
      // On error, fetch from backend to revert to actual state
      await fetchRelationships();
    }
  };

  const getHumanReadable = (rel: any) => {
    const parent = rel.parent_table.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
    const child = rel.child_table.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
    return `${child} belongs to ${parent}`;
  };

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
        <h3 className="text-blue-800 font-semibold">Step 4: Enable Data Connections</h3>
        <p className="text-blue-600 text-sm">Amoeba AI has discovered how your data is connected. Enable these connections to allow multi-table analysis.</p>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Discovering connections...</p>
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 text-red-600 rounded-lg border border-red-200">
          {error}
          <button onClick={fetchRelationships} className="block mt-2 underline">Retry</button>
        </div>
      ) : relationships.length === 0 ? (
        <div className="text-center py-12 border-2 border-dashed rounded-lg text-gray-500">
          <p>No connections discovered yet. You can skip this step.</p>
          <button onClick={onSuccess} className="mt-4 bg-blue-600 text-white px-6 py-2 rounded-lg">Continue</button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex justify-end gap-2 mb-2">
            <button
              onClick={() => handleBulkAction('enable_all')}
              className="text-xs font-semibold bg-green-50 text-green-700 px-3 py-1.5 rounded-lg border border-green-200 hover:bg-green-100 transition"
              disabled={loading}
            >
              Enable All
            </button>
            <button
              onClick={() => handleBulkAction('disable_all')}
              className="text-xs font-semibold bg-gray-50 text-gray-700 px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-100 transition"
              disabled={loading}
            >
              Disable All
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {relationships.map(rel => (
              <div 
                key={rel.id}
                className="flex items-center justify-between p-4 bg-white border rounded-lg hover:shadow-sm transition"
              >
                <div>
                  <div className="font-medium text-gray-900">{getHumanReadable(rel)}</div>
                  <div className="text-xs text-gray-500">
                    {rel.child_table}.{rel.child_column} → {rel.parent_table}.{rel.parent_column}
                  </div>
                </div>
                <div className="flex items-center">
                  <span className={`mr-3 text-xs font-semibold px-2 py-1 rounded-full ${
                    rel.is_enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {rel.is_enabled ? 'Enabled' : 'Disabled'}
                  </span>
                  <button
                    onClick={() => toggleRelationship(rel.id, rel.is_enabled)}
                    className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                      rel.is_enabled ? 'bg-blue-600' : 'bg-gray-200'
                    }`}
                  >
                    <span
                      className={`inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                        rel.is_enabled ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={onSuccess}
            className="w-full mt-4 bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition"
          >
            I'm Done with Connections
          </button>
        </div>
      )}
    </div>
  );
};
