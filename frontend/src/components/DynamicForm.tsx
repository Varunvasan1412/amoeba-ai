import React, { useState } from 'react';

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
}

const DynamicForm: React.FC<DynamicFormProps> = ({ fields, onSubmit, onCancel, title }) => {
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
    <div className="bg-white p-4 rounded-lg shadow-md border border-gray-200 my-2">
      {title && <h3 className="text-lg font-semibold mb-3 text-gray-800">{title}</h3>}
      <form onSubmit={handleSubmit} className="space-y-4">
        {fields.map((f) => (
          <div key={f.field} className="flex flex-col">
            <label className="text-sm font-medium text-gray-700 mb-1">
              {f.label} {f.required && <span className="text-red-500">*</span>}
            </label>
            
            {f.type === 'textarea' ? (
              <textarea
                className="border rounded px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none h-24"
                required={f.required}
                value={formData[f.field] || ''}
                onChange={(e) => handleChange(f.field, e.target.value)}
              />
            ) : f.type === 'dropdown' ? (
              <select
                className="border rounded px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                required={f.required}
                value={formData[f.field] || ''}
                onChange={(e) => handleChange(f.field, e.target.value)}
              >
                <option value="">Select {f.label}</option>
                {f.options?.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={f.type === 'currency' ? 'number' : f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}
                step={f.type === 'currency' ? '0.01' : '1'}
                className="border rounded px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
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
            className="bg-gray-200 text-gray-700 px-4 py-2 rounded text-sm font-medium hover:bg-gray-300 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
};

export default DynamicForm;
