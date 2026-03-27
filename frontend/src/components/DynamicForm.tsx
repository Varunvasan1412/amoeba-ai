import React, { useState } from 'react';
import { SearchableDropdown } from './admin/SearchableDropdown';

interface FormField {
  field: string;
  label: string;
  type: string;
  storage_type?: string; // string | integer | float | boolean | date
  required?: boolean;
  options?: { value: any; label: string }[];
  initial_value?: any;
}

interface DynamicFormProps {
  fields: FormField[];
  onSubmit: (data: any) => void;
  onCancel: () => void;
  title?: string;
  darkMode?: boolean;
}

const DynamicForm: React.FC<DynamicFormProps> = ({ fields, onSubmit, onCancel, title, darkMode }) => {
  const [formData, setFormData] = useState<any>(() => {
    const initial: any = {};
    fields.forEach(f => {
      if (f.initial_value !== undefined) initial[f.field] = f.initial_value;
    });
    return initial;
  });

  const handleChange = (field: string, value: any) => {
    setFormData((prev: any) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // PERFORM TYPE CASTING BEFORE SUBMIT
    const castedData: any = {};
    fields.forEach(f => {
      const val = formData[f.field];
      if (val === undefined || val === null || val === "") {
          castedData[f.field] = null;
          return;
      }

      switch (f.storage_type) {
          case 'integer':
              castedData[f.field] = parseInt(val, 10);
              break;
          case 'float':
              castedData[f.field] = parseFloat(val);
              break;
          case 'boolean':
              castedData[f.field] = val === 'true' || val === true;
              break;
          default:
              castedData[f.field] = val;
      }
    });

    onSubmit(castedData);
  };

  return (
    <div className={`${darkMode ? 'bg-gray-800 border-gray-700 shadow-xl' : 'bg-white border-gray-200 shadow-md'} p-4 rounded-lg border my-2 transition-colors`}>
      {title && <h3 className={`text-lg font-semibold mb-3 ${darkMode ? 'text-gray-100' : 'text-gray-800'}`}>{title}</h3>}
      <form onSubmit={handleSubmit} className="space-y-4">
        {fields.map((f) => (
          <div key={f.field} className="flex flex-col">
            <label className={`text-sm font-medium mb-1 ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
              {f.label} {f.required && <span className="text-red-500">*</span>}
            </label>
            
            {f.type === 'textarea' ? (
              <textarea
                className={`border rounded px-3 py-2 text-sm outline-none h-24 transition-all ${darkMode ? 'bg-gray-700 border-gray-600 text-white focus:ring-blue-900/50 focus:border-blue-500' : 'bg-white border-gray-300 text-gray-900 focus:ring-blue-500/20 focus:border-blue-500'}`}
                required={f.required}
                value={formData[f.field] || ''}
                onChange={(e) => handleChange(f.field, e.target.value)}
              />
            ) : f.type === 'dropdown' ? (
              <SearchableDropdown
                options={f.options || []}
                value={formData[f.field] || ''}
                onChange={(val: any) => handleChange(f.field, val)}
                placeholder={`Select ${f.label}`}
                className="w-full"
                theme={darkMode ? 'dark' : 'light'}
              />
            ) : (
              <input
                type={f.type === 'currency' ? 'number' : f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}
                step={f.type === 'currency' ? '0.01' : '1'}
                className={`border rounded px-3 py-2 text-sm outline-none transition-all ${darkMode ? 'bg-gray-700 border-gray-600 text-white focus:ring-blue-900/50 focus:border-blue-500' : 'bg-white border-gray-300 text-gray-900 focus:ring-blue-500/20 focus:border-blue-500'}`}
                required={f.required}
                value={formData[f.field] || ''}
                onChange={(e) => handleChange(f.field, e.target.value)}
              />
            )}
          </div>
        ))}
        
        <div className="flex space-x-2 pt-2">
          <button
            type="submit"
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            Submit
          </button>
          <button
            type="button"
            onClick={onCancel}
            className={`px-4 py-2 rounded text-sm font-medium transition-colors ${darkMode ? 'bg-gray-700 text-gray-300 hover:bg-gray-600' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
};

export default DynamicForm;
