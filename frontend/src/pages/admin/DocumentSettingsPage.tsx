import { useState, useEffect } from "react";
import { useAdmin } from "../../context/AdminContext";
import { apiFetch } from "../../utils/api";
import { 
  Shield,
  Save, 
  AlertCircle,
  Hash,
  HardDrive,
  FileUp,
  Check
} from "lucide-react";

export default function DocumentSettingsPage() {
  const { clientId, clients, refreshClients } = useAdmin();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [quotas, setQuotas] = useState({
    max_documents: 500,
    max_storage_mb: 2048,
    max_document_size_mb: 50
  });

  useEffect(() => {
    if (clientId && clients.length > 0) {
      const client = clients.find(c => c.id === clientId);
      if (client) {
        setQuotas({
          max_documents: client.max_documents ?? 500,
          max_storage_mb: client.max_storage_mb ?? 2048,
          max_document_size_mb: client.max_document_size_mb ?? 50
        });
      }
    }
  }, [clientId, clients]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (quotas.max_documents <= 0 || quotas.max_storage_mb <= 0 || quotas.max_document_size_mb <= 0) {
      setError("All values must be positive numbers");
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      const res = await apiFetch(`/api/clients/${clientId}/quota`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(quotas)
      });

      if (!res.ok) throw new Error("Failed to save quotas");
      
      await refreshClients();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(true);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center">
            <Shield size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Document Quotas</h1>
            <p className="text-sm text-gray-500">Configure operational limits for this client.</p>
          </div>
        </div>

        <form onSubmit={handleSave} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-bold text-gray-700 flex items-center gap-2">
                <Hash size={14} className="text-gray-400" />
                Max Documents
              </label>
              <input 
                type="number"
                value={quotas.max_documents}
                onChange={e => setQuotas({...quotas, max_documents: parseInt(e.target.value)})}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              />
              <p className="text-[10px] text-gray-400">Total number of files allowed in the system.</p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-bold text-gray-700 flex items-center gap-2">
                <HardDrive size={14} className="text-gray-400" />
                Total Storage (MB)
              </label>
              <input 
                type="number"
                value={quotas.max_storage_mb}
                onChange={e => setQuotas({...quotas, max_storage_mb: parseInt(e.target.value)})}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              />
              <p className="text-[10px] text-gray-400">Total aggregate size of all uploaded files.</p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-bold text-gray-700 flex items-center gap-2">
                <FileUp size={14} className="text-gray-400" />
                Max File Size (MB)
              </label>
              <input 
                type="number"
                value={quotas.max_document_size_mb}
                onChange={e => setQuotas({...quotas, max_document_size_mb: parseInt(e.target.value)})}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl outline-none focus:ring-2 focus:ring-blue-500 transition-all"
              />
              <p className="text-[10px] text-gray-400">Limit for a single document upload.</p>
            </div>
          </div>

          <div className="pt-4 border-t border-gray-50 flex items-center justify-between">
            <div className="flex-1">
              {error && <p className="text-sm text-red-600 flex items-center gap-1 font-medium"><AlertCircle size={14}/> {error}</p>}
              {success && <p className="text-sm text-green-600 flex items-center gap-1 font-medium"><Check size={14}/> Document settings updated successfully</p>}
            </div>
            
            <button 
              type="submit"
              disabled={saving}
              className="bg-blue-600 text-white px-6 py-3 rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 shadow-lg shadow-blue-200 transition-all flex items-center gap-2"
            >
              <Save size={18} />
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>

      <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl flex items-start gap-3">
        <AlertCircle className="text-amber-600 mt-0.5" size={18} />
        <div className="text-sm text-amber-800">
          <strong>Note:</strong> Quota changes take effect immediately. If a client is already over quota, they will be blocked from uploading new files but existing files will remain accessible.
        </div>
      </div>
    </div>
  );
}
