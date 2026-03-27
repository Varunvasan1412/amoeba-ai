import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';
import { Table, Check, Loader2, AlertTriangle, Pencil, RotateCcw } from 'lucide-react';
import { SearchableDropdown } from '../admin/SearchableDropdown';

interface SemanticSuggestionStepProps {
  selectedTables: string[];
  onSuccess: (mappings: any[]) => void;
  initialMappings?: any[];
}

export const SemanticSuggestionStep: React.FC<SemanticSuggestionStepProps> = ({ selectedTables, onSuccess, initialMappings }) => {
  const { clientId, apiKey } = useAdmin();
  const [mappings, setMappings] = useState<any[]>(initialMappings || []);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [activeTable, setActiveTable] = useState<string>('');
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  useEffect(() => {
    generateSuggestions();
  }, [selectedTables, clientId, apiKey]);

  const generateSuggestions = async () => {
    if (!clientId) return;
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      // Fetch table definitions
      const response = await fetch(`/api/clients/${clientId}/tables`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();

      // Fetch existing semantic metadata to avoid overwriting user changes
      let existingMetadata: any[] = [];
      try {
        const semanticResponse = await fetch(`/api/v2/semantic/schema`, {
          headers: { 
            'Authorization': `Bearer ${token}`,
            'X-API-Key': apiKey || ''
          }
        });
        if (semanticResponse.ok) {
          existingMetadata = await semanticResponse.json();
        }
      } catch (e) {
        console.error('Failed to fetch existing semantic metadata', e);
      }

      const allTables = data.tables || [];
      const filtered = allTables.filter((t: any) =>
        selectedTables.length === 0 || selectedTables.includes(t.name)
      );

      const suggestions: any[] = [];
      filtered.forEach((table: any) => {
        table.columns.forEach((col: string) => {
          // 1. Priority: Existing Metadata from Backend
          const existing = existingMetadata.find(m => 
            m.table_name === table.name && m.column_name === col
          );

          if (existing) {
            suggestions.push({
              table_name: table.name,
              column_name: col,
              label: existing.label,
              original_label: existing.label,
              data_format: (existing.data_format || 'text').toLowerCase(),
              is_default_date: existing.is_default_date,
              is_pii: existing.is_pii
            });
            return;
          }

          // 2. Secondary: Initial Mappings from Props (local state)
          const localMatch = initialMappings?.find(m => 
            m.table_name === table.name && m.column_name === col
          );

          if (localMatch) {
            suggestions.push({ ...localMatch });
            return;
          }

          // 3. Fallback: Heuristics
          let label = col.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
          let data_format = 'text';
          let is_default_date = false;

          if (col.toLowerCase().endsWith('_id')) {
            label = label.replace(/\sId$/, ' Identifier');
          } else if (/amount|total|price|cost/i.test(col) || (/tax/i.test(col) && !/number|id|code/i.test(col))) {
            data_format = 'currency';
          } else if (/date|created_at|updated_at|timestamp/i.test(col)) {
            data_format = 'date';
            is_default_date = /order_date|created_at/i.test(col);
          } else if (/name|title|label/i.test(col)) {
            label = label + ' Name';
          }

          suggestions.push({
            table_name: table.name,
            column_name: col,
            label,
            original_label: label,
            data_format,
            is_default_date,
            is_pii: /email|phone|address|ssn/i.test(col)
          });
        });
      });

      setMappings(suggestions);
      if (filtered.length > 0 && !activeTable) setActiveTable(filtered[0].name);
    } catch (err) {
      setError('Failed to generate suggestions. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateLabel = (index: number, newLabel: string) => {
    const updated = [...mappings];
    updated[index] = { ...updated[index], label: newLabel };
    setMappings(updated);
  };

  const handleUpdateType = (index: number, newType: string) => {
    const updated = [...mappings];
    updated[index] = { ...updated[index], data_format: newType };
    setMappings(updated);
  };

  const handleReset = (index: number) => {
    const updated = [...mappings];
    updated[index] = { ...updated[index], label: updated[index].original_label };
    setMappings(updated);
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/v2/semantic/columns', {
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
      setSaving(false);
    }
  };

  const tableNames = Array.from(new Set(mappings.map(m => m.table_name)));
  const tableOptions = tableNames.map(t => ({ value: t, label: t }));

  const activeMappings = mappings
    .map((m, idx) => ({ ...m, _idx: idx }))
    .filter(m => m.table_name === activeTable);

  const modifiedCount = mappings.filter(m => m.label !== m.original_label).length;

  if (loading && mappings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-72 gap-4">
        <Loader2 className="animate-spin text-blue-500" size={36} />
        <p className="text-gray-500 font-medium text-sm">Generating smart name suggestions...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4" style={{ height: '460px' }}>

      {/* Header row */}
      <div className="flex items-end justify-between shrink-0">
        <div>
          <h3 className="text-lg font-bold text-gray-900">Give Your Data a Business Voice</h3>
          <p className="text-xs text-gray-400 mt-0.5">Pick a table and click any name to rename it.</p>
        </div>
        <div className="flex gap-4 text-xs font-bold text-gray-400 bg-gray-50 px-3 py-1.5 rounded-xl border border-gray-100">
          <span>{tableNames.length} Tables</span>
          <span>·</span>
          <span>{mappings.length} Columns</span>
          {modifiedCount > 0 && <><span>·</span><span className="text-purple-600">{modifiedCount} edited</span></>}
        </div>
      </div>

      {/* Searchable Table Selector replacing sidebar */}
      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-100 flex items-center gap-4 shrink-0 shadow-sm">
        <div className="flex items-center gap-2 text-slate-500 text-xs font-bold uppercase tracking-wider whitespace-nowrap">
          <Table size={14} className="text-blue-500" />
          Active Table:
        </div>
        <div className="flex-1 max-w-sm">
          <SearchableDropdown
            options={tableOptions}
            value={activeTable}
            onChange={val => { setActiveTable(val); setEditingIdx(null); }}
            placeholder="Select a table to edit..."
          />
        </div>
        {activeTable && (
          <div className="bg-white px-3 py-1.5 rounded-lg border border-slate-200 text-[10px] font-bold text-slate-400">
            {activeMappings.length} columns in this table
          </div>
        )}
      </div>

      {/* Column editor panel */}
      <div className="flex border border-gray-200 rounded-2xl overflow-hidden bg-white shadow-sm flex-1 min-h-0">
        <div className="flex-1 flex flex-col overflow-hidden">
          {activeTable ? (
            <>
              {/* Column header */}
              <div className="grid px-6 py-2 bg-gray-50 border-b border-gray-100 text-[10px] font-bold text-gray-400 uppercase tracking-widest shrink-0" style={{ gridTemplateColumns: '10rem 1fr 8rem 2rem' }}>
                <span>Raw Column</span>
                <span>Business Name (Click to edit)</span>
                <span>Data Type</span>
                <span></span>
              </div>

              <div className="flex-1 overflow-y-auto min-h-0 divide-y divide-gray-50">
                {activeMappings.map((m) => {
                  const isEditing = editingIdx === m._idx;
                  const isModified = m.label !== m.original_label;
                  return (
                    <div
                      key={m._idx}
                      className={`px-6 py-2.5 flex items-center gap-3 group hover:bg-blue-50/30 transition-all ${isEditing ? 'bg-indigo-50/60' : ''}`}
                      style={{ display: 'grid', gridTemplateColumns: '10rem 1fr 8rem 2rem', alignItems: 'center', gap: '1rem' }}
                    >
                      {/* Raw column name */}
                      <div className="min-w-0">
                        <div className="font-mono text-[11px] text-gray-400 truncate" title={m.column_name}>{m.column_name}</div>
                        {m.is_pii && (
                          <span className="text-[9px] font-bold bg-red-50 text-red-500 px-1.5 py-0.5 rounded-full border border-red-100">
                            🔒 PII
                          </span>
                        )}
                      </div>

                      {/* Label inline editor */}
                      <div className="min-w-0">
                        {isEditing ? (
                          <input
                            autoFocus
                            type="text"
                            value={editValue}
                            className="w-full border-2 border-indigo-400 rounded-lg px-2 py-1.5 text-sm font-bold text-gray-800 focus:outline-none"
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={() => { handleUpdateLabel(m._idx, editValue.trim() || m.label); setEditingIdx(null); }}
                            onKeyDown={e => {
                              if (e.key === 'Enter') { handleUpdateLabel(m._idx, editValue.trim() || m.label); setEditingIdx(null); }
                              if (e.key === 'Escape') setEditingIdx(null);
                            }}
                          />
                        ) : (
                          <button
                            className="flex items-center gap-1.5 text-left w-full group/btn"
                            onClick={() => { setEditValue(m.label); setEditingIdx(m._idx); }}
                          >
                            <span className={`text-sm font-semibold truncate ${isModified ? 'text-purple-700' : 'text-gray-800'}`}>
                              {m.label}
                            </span>
                            <Pencil size={10} className="text-gray-300 opacity-0 group-hover/btn:opacity-100 shrink-0 transition-opacity" />
                          </button>
                        )}
                      </div>

                      {/* Data Type dropdown (non-searchable) */}
                      <div>
                        <select
                          className={`text-[10px] font-bold px-2 py-1 rounded-lg border focus:outline-none focus:ring-1 focus:ring-blue-400 ${
                            m.data_format === 'currency' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' :
                            m.data_format === 'date' ? 'bg-blue-50 text-blue-600 border-blue-100' :
                            'bg-gray-50 text-gray-500 border-gray-100'
                          }`}
                          value={m.data_format}
                          onChange={(e) => handleUpdateType(m._idx, e.target.value)}
                        >
                          <option value="text">TEXT</option>
                          <option value="currency">CURRENCY</option>
                          <option value="date">DATE</option>
                          <option value="number">NUMBER</option>
                          <option value="percent">PERCENT</option>
                          <option value="boolean">BOOLEAN</option>
                        </select>
                      </div>

                      {/* Reset */}
                      <div className="flex justify-center">
                        {isModified && (
                          <button onClick={() => handleReset(m._idx)} title="Reset" className="text-gray-300 hover:text-gray-500 transition-colors">
                            <RotateCcw size={12} />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-300 gap-2">
              <Table size={48} className="opacity-10" />
              <p className="text-sm font-bold uppercase tracking-widest">Select a table to start editing</p>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between shrink-0">
        <div>
          {error && (
            <div className="flex items-center gap-2 text-red-500 text-xs">
              <AlertTriangle size={12} /> {error}
            </div>
          )}
          {!error && <p className="text-[11px] text-gray-400">💡 Changes are saved when you click accept below. Purple labels indicate manual edits.</p>}
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-blue-600 text-white px-8 py-3 rounded-xl font-bold text-sm flex items-center gap-2 hover:bg-blue-700 disabled:opacity-50 shadow-md shadow-blue-100 transition-all hover:-translate-y-0.5"
        >
          {saving ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}
          {saving ? 'Saving...' : 'Accept All & Continue →'}
        </button>
      </div>
    </div>
  );
};
