import { useState, useEffect } from "react";
import { useAdmin } from "../../context/AdminContext";
import { apiFetch } from "../../utils/api";
import { 
  Database, 
  FileText, 
  Globe, 
  Save, 
  Check,
  AlertCircle,
  ToggleRight
} from "lucide-react";

export default function SourceSettingsPage() {
  const { clientId, clients, refreshClients } = useAdmin();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [sources, setSources] = useState({
    erp: true,
    documents: true,
    web: false
  });

  useEffect(() => {
    if (clientId && clients.length > 0) {
      const client = clients.find(c => c.id === clientId);
      if (client) {
        setSources({
          erp: client.erp_enabled ?? true,
          documents: client.documents_enabled ?? true,
          web: client.web_enabled ?? false
        });
      }
    }
  }, [clientId, clients]);

  const handleToggle = (key: keyof typeof sources) => {
    setSources(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      const res = await apiFetch(`/api/clients/${clientId}/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(sources)
      });

      if (!res.ok) throw new Error("Failed to save source settings");
      
      await refreshClients();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const SourceToggle = ({ 
    label, 
    description, 
    value, 
    icon: Icon, 
    onToggle 
  }: { 
    label: string, 
    description: string, 
    value: boolean, 
    icon: any, 
    onToggle: () => void 
  }) => (
    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-transparent hover:border-blue-100 transition-all">
      <div className="flex items-start gap-4">
        <div className={`mt-1 w-10 h-10 rounded-lg flex items-center justify-center ${value ? "bg-blue-100 text-blue-600" : "bg-gray-100 text-gray-400"}`}>
          <Icon size={20} />
        </div>
        <div>
          <h3 className="font-bold text-gray-800">{label}</h3>
          <p className="text-xs text-gray-500 max-w-sm">{description}</p>
        </div>
      </div>
      <button 
        onClick={onToggle}
        className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors focus:outline-none ${value ? "bg-blue-600" : "bg-gray-300"}`}
      >
        <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${value ? "translate-x-6" : "translate-x-1"}`} />
      </button>
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center">
            <ToggleRight size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Knowledge Sources</h1>
            <p className="text-sm text-gray-500">Configure which data streams the AI can retrieve from.</p>
          </div>
        </div>

        <div className="space-y-4">
          <SourceToggle 
            label="ERP Knowledge"
            description="Allows retrieval of structured data from your ERP system (e.g., Leads, Sales, Customers)."
            value={sources.erp}
            icon={Database}
            onToggle={() => handleToggle("erp")}
          />

          <SourceToggle 
            label="Document Knowledge"
            description="Allows retrieval of unstructured data from uploaded PDFs, DOCX, and TXT files."
            value={sources.documents}
            icon={FileText}
            onToggle={() => handleToggle("documents")}
          />

          <SourceToggle 
            label="Web Search Knowledge"
            description="Allows the AI to perform external web searches for real-time information (e.g., market trends, news)."
            value={sources.web}
            icon={Globe}
            onToggle={() => handleToggle("web")}
          />
        </div>

        <div className="mt-8 pt-6 border-t border-gray-50 flex items-center justify-between">
          <div className="flex-1">
            {error && <p className="text-sm text-red-600 flex items-center gap-1 font-medium"><AlertCircle size={14}/> {error}</p>}
            {success && <p className="text-sm text-green-600 flex items-center gap-1 font-medium"><Check size={14}/> Knowledge source settings saved</p>}
          </div>
          
          <button 
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-600 text-white px-6 py-3 rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 shadow-lg shadow-blue-200 transition-all flex items-center gap-2"
          >
            <Save size={18} />
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 p-4 rounded-xl flex items-start gap-3">
        <AlertCircle className="text-blue-600 mt-0.5" size={18} />
        <div className="text-sm text-blue-800">
          <strong>Pro-Tip:</strong> Disabling a source prevents retrieval during chat operations, but historical data remains stored in your vector database for future reactivation.
        </div>
      </div>
    </div>
  );
}
