import React, { useState } from 'react';
import { useAdmin } from '../../context/AdminContext';
import { apiFetch } from '../../utils/api';

interface FirstReportStepProps {
  semanticMappings: any[];
  onSuccess: () => void;
}

export const FirstReportStep: React.FC<FirstReportStepProps> = ({ semanticMappings, onSuccess }) => {
  const { clientId, apiKey } = useAdmin();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const createFirstReport = async () => {
    setLoading(true);
    setError('');
    
    // Filter to valid mappings only
    const validMappings = semanticMappings.filter(m => m.label && m.table_name && m.column_name);

    if (validMappings.length === 0) {
      setError('No valid data mappings found. Please go back to Step 3.');
      setLoading(false);
      return;
    }

    // 1. Look for a table with a currency/number column
    // Refined regex: exclude things like tax_number or id
    const isValueColumn = (colName: string) => /amount|total|price|cost|revenue|value/i.test(colName) && !/number|id|code/i.test(colName);
    
    const amountCol = validMappings.find(m => m.data_format === 'currency' && isValueColumn(m.column_name)) || 
                      validMappings.find(m => m.data_format === 'number' && isValueColumn(m.column_name)) ||
                      validMappings.find(m => m.data_format === 'currency') ||
                      validMappings.find(m => m.data_format === 'number');
    
    const targetMapping = amountCol || validMappings[0];
    const targetTable = targetMapping.table_name;
    const targetLabel = targetMapping.label;
    
    // Only SUM if it's a numeric column, otherwise COUNT
    const isNumeric = targetMapping.data_format === 'currency' || targetMapping.data_format === 'number';
    const funcName = isNumeric ? 'SUM' : 'COUNT';
    const aggLabel = isNumeric ? 'Total Value' : `Total ${targetLabel}s`;
    
    const reportName = `Initial ${targetTable.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())} Summary`;

    const builderDefinition = {
      base_table: targetTable,
      columns: [targetLabel], // Use the semantic label, not column name
      aggregations: [
        { column: targetLabel, function: funcName, label: aggLabel }
      ],
      filters: []
    };

    console.log('Generating First Report Request:', builderDefinition);

    try {
      const response = await apiFetch('/api/v2/builder/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey || ''
        },
        body: JSON.stringify({
          client_id: clientId,
          report_name: reportName,
          builder_definition: builderDefinition
        })
      });

      if (response.ok) {
        // Mark onboarding as complete in backend
        await apiFetch(`/api/clients/${clientId}/onboarding/complete`, {
          method: 'POST',
        });
        onSuccess();
      } else {
        const data = await response.json();
        setError(data.detail || 'Failed to create view');
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
        <h3 className="text-blue-800 font-semibold">Step 5: Create your First Data View</h3>
        <p className="text-blue-600 text-sm">You're almost there! Click the button below to generate your first automated report. You'll be able to ask Amoeba AI about this data immediately after.</p>
      </div>

      <div className="flex flex-col items-center justify-center py-12 border-2 border-dashed rounded-xl bg-gray-50">
        <div className="bg-white p-6 rounded-lg shadow-sm border mb-6 text-center max-w-sm">
          <div className="text-4xl mb-4">📊</div>
          <h4 className="font-bold text-gray-900 mb-2">Ready to Launch!</h4>
          <p className="text-gray-600 text-sm">
            We will create an initial summary view for you. You can add more later in the Data View Builder.
          </p>
        </div>

        {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

        <button
          onClick={createFirstReport}
          disabled={loading}
          className="bg-blue-600 text-white px-10 py-4 rounded-xl font-bold text-lg hover:bg-blue-700 shadow-lg transform hover:-translate-y-1 transition disabled:opacity-50"
        >
          {loading ? 'Generating Data View...' : '🚀 Create My First View'}
        </button>
      </div>
    </div>
  );
};
