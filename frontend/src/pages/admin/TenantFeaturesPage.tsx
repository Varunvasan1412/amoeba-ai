import { useState, useEffect } from 'react';
import { apiFetch } from '../../utils/api';
import { useAdmin } from '../../context/AdminContext';
import { 
  Rocket, 
  Shield, 
  Database, 
  LayoutTemplate, 
  Map,
  Check,
  AlertCircle,
  Save,
  Cpu,
  Activity,
  Archive,
  Building2,
  Users
} from 'lucide-react';

interface FeatureToggle {
  key: string;
  label: string;
  description: string;
  icon: any;
  color: string;
}

export default function TenantFeaturesPage() {
  const { clientId, refreshClients, clients } = useAdmin();
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  const [features, setFeatures] = useState({
    feature_wizard_enabled: true,
    feature_relationships_enabled: true,
    feature_semantic_enabled: true,
    feature_reports_enabled: true,
    feature_routing_enabled: true,
    feature_ai_settings_enabled: true,
    feature_health_enabled: true,
    feature_backups_enabled: true,
    feature_tenants_enabled: true,
    feature_security_enabled: true,
    schema_rag_enabled: false
  });

  useEffect(() => {
    if (clientId && clients.length > 0) {
      const currentClient = clients.find(c => c.id === clientId);
      if (currentClient) {
        setFeatures({
          feature_wizard_enabled: currentClient.feature_wizard_enabled ?? true,
          feature_relationships_enabled: currentClient.feature_relationships_enabled ?? true,
          feature_semantic_enabled: currentClient.feature_semantic_enabled ?? true,
          feature_reports_enabled: currentClient.feature_reports_enabled ?? true,
          feature_routing_enabled: currentClient.feature_routing_enabled ?? true,
          feature_ai_settings_enabled: currentClient.feature_ai_settings_enabled ?? true,
          feature_health_enabled: currentClient.feature_health_enabled ?? true,
          feature_backups_enabled: currentClient.feature_backups_enabled ?? true,
          feature_tenants_enabled: currentClient.feature_tenants_enabled ?? true,
          feature_security_enabled: currentClient.feature_security_enabled ?? true,
          schema_rag_enabled: currentClient.schema_rag_enabled ?? false
        });
      }
    }
  }, [clientId, clients]);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await apiFetch(`/api/clients/${clientId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(features)
      });
      
      if (res.ok) {
        setMessage({ type: 'success', text: 'Tenant features updated successfully' });
        await refreshClients(); // Update global context
        setTimeout(() => setMessage(null), 3000);
      } else {
        const errData = await res.json();
        setMessage({ type: 'error', text: errData.detail || 'Failed to save changes' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Network error occurred' });
    } finally {
      setSaving(false);
    }
  };

  const toggleFeature = (key: string) => {
    setFeatures(prev => ({
      ...prev,
      [key]: !prev[key as keyof typeof prev]
    }));
  };

  const featureList: FeatureToggle[] = [
    {
      key: 'feature_wizard_enabled',
      label: 'Setup Wizard',
      description: 'The step-by-step onboarding guide for initial configuration.',
      icon: Rocket,
      color: 'blue'
    },
    {
      key: 'feature_relationships_enabled',
      label: 'Relationship Governance',
      description: 'Tool for managing database join paths and link integrity.',
      icon: Shield,
      color: 'red'
    },
    {
      key: 'feature_semantic_enabled',
      label: 'Semantic Graph',
      description: 'Mapping technical columns to human-readable AI labels.',
      icon: Database,
      color: 'emerald'
    },
    {
      key: 'feature_reports_enabled',
      label: 'Reports & Views',
      description: 'Self-service SQL-free report building and data library.',
      icon: LayoutTemplate,
      color: 'purple'
    },
    {
      key: 'feature_routing_enabled',
      label: 'Intelligent Routing',
      description: 'Mapping conversational intents to specific ERP logic.',
      icon: Map,
      color: 'indigo'
    },
    {
      key: 'feature_ai_settings_enabled',
      label: 'AI Infrastructure',
      description: 'Manage LLM providers (Gemini, OpenAI, Ollama) and model settings.',
      icon: Cpu,
      color: 'indigo'
    },
    {
      key: 'feature_health_enabled',
      label: 'System Health',
      description: 'Monitor database integrity, document pipelines, and audit logs.',
      icon: Activity,
      color: 'rose'
    },
    {
      key: 'feature_backups_enabled',
      label: 'System Backups',
      description: 'Manage automated database backups and safety-validated restores.',
      icon: Archive,
      color: 'teal'
    },
    {
      key: 'feature_tenants_enabled',
      label: 'Tenants & Companies',
      description: 'Onboard and manage multi-tenant enterprise clients.',
      icon: Building2,
      color: 'blue'
    },
    {
      key: 'feature_security_enabled',
      label: 'Access & RBAC',
      description: 'Manage users, custom roles, and security permissions.',
      icon: Users,
      color: 'cyan'
    },
    {
      key: 'schema_rag_enabled',
      label: 'AI Schema RAG Engine',
      description: 'Enable dynamic LLM SQL generation based on live synced schemas instead of hardcoded rules.',
      icon: Database,
      color: 'emerald'
    }
  ];

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Tenant Feature Controls</h1>
          <p className="text-slate-500">Decide which dashboard tiles are visible to this client.</p>
        </div>
        <button 
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all shadow-lg shadow-blue-200 font-bold disabled:opacity-50 active:scale-95"
        >
          {saving ? 'Saving...' : <><Save size={18} /> Save Configuration</>}
        </button>
      </div>

      {message && (
        <div className={`p-4 rounded-xl flex items-center gap-3 animate-in fade-in slide-in-from-top-2 duration-300 ${message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {message.type === 'success' ? <Check size={20} /> : <AlertCircle size={20} />}
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {featureList.map((f) => (
          <div 
            key={f.key}
            className={`p-6 rounded-2xl border transition-all flex items-start gap-4 ${
              features[f.key as keyof typeof features] 
                ? 'bg-white border-slate-200 shadow-sm' 
                : 'bg-slate-50/50 border-slate-100 opacity-60 grayscale-[0.5]'
            }`}
          >
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 bg-${f.color}-50 text-${f.color}-600`}>
              <f.icon size={24} />
            </div>
            
            <div className="flex-1">
              <div className="flex justify-between items-start mb-1">
                <h3 className="font-bold text-slate-900">{f.label}</h3>
                <button
                  onClick={() => toggleFeature(f.key)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                    features[f.key as keyof typeof features] ? 'bg-blue-600' : 'bg-slate-300'
                  }`}
                >
                  <span
                    className={`${
                      features[f.key as keyof typeof features] ? 'translate-x-6' : 'translate-x-1'
                    } inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
                  />
                </button>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">{f.description}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="p-6 bg-blue-50 border border-blue-100 rounded-3xl">
        <div className="flex gap-4">
          <div className="w-10 h-10 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center shrink-0">
            <Shield size={20} />
          </div>
          <div>
            <h4 className="font-bold text-blue-900 mb-1">Platform Governance Notice</h4>
            <p className="text-sm text-blue-700/80 leading-relaxed">
              These toggles only affect the **Dashboard visibility** for the tenant's users. Platform owners will always see all administrative tools regardless of these settings to ensure you can always maintain the system.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
