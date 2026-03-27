import { Link } from "react-router-dom";
import { 
  Database, 
  LayoutTemplate, 
  Settings, 
  PlayCircle, 
  Shield, 
  Rocket, 
  Map, 
  Cpu, 
  ArrowRight,
  FileText 
} from "lucide-react";
import { useAdmin } from "../context/AdminContext";
import { useState, useEffect } from "react";
import DocumentMetricsCard from "../components/admin/DocumentMetricsCard";

export default function AdminDashboard() {
  const { clientId } = useAdmin();
  const [onboardingCompleted, setOnboardingCompleted] = useState<boolean | null>(null);
  const [warnings, setWarnings] = useState<any[]>([]);

  useEffect(() => {
    if (clientId) {
      fetchOnboardingStatus();
      fetchValidationWarnings();
    }
  }, [clientId]);

  const fetchOnboardingStatus = async () => {
    try {
      const token = localStorage.getItem('token');
      const API_BASE = "/api";
      const response = await fetch(`${API_BASE}/clients/${clientId}/onboarding/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setOnboardingCompleted(data.onboarding_completed);
    } catch (err) {
      console.error("Failed to fetch onboarding status", err);
    }
  };

  const fetchValidationWarnings = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/fields?client_id=${clientId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setWarnings(data.warnings || []);
      }
    } catch (err) {
      console.error("Failed to fetch validation warnings", err);
    }
  };

  const cards = [
    {
      title: "Setup Wizard",
      description: "Step-by-step guide to connect your ERP, map business names, and launch.",
      icon: Rocket,
      to: "/admin/wizard",
      color: "blue",
      highlight: !onboardingCompleted
    },
    {
      title: "Relationship Governance",
      description: "Govern how different data sources link together and manage join paths.",
      icon: Shield,
      to: "/admin/relationships",
      color: "red"
    },
    {
      title: "Semantic Graph",
      description: "Map technical columns to easy-to-understand labels for the AI.",
      icon: Database,
      to: "/admin/semantic",
      color: "emerald"
    },
    {
      title: "Reports & Views",
      description: "Build beautiful SQL-free reports and manage your saved data library.",
      icon: LayoutTemplate,
      to: "/admin/reports",
      color: "purple"
    },
    {
      title: "Intelligent Routing",
      description: "Map conversational intents and modules to specific ERP tables.",
      icon: Map,
      to: "/admin/routes",
      color: "indigo"
    },
    {
      title: "AI Infrastructure",
      description: "Switch between LLM providers (Gemini, OpenAI, Ollama) and configure model settings.",
      icon: Cpu,
      to: "/admin/ai-settings",
      color: "indigo"
    },
    {
      title: "Document Management",
      description: "View, retry, and delete knowledge base documents and monitor status.",
      icon: FileText,
      to: "/admin/documents",
      color: "blue"
    },
    {
      title: "Document Settings",
      description: "Configure document quotas, storage limits, and upload constraints.",
      icon: Settings,
      to: "/admin/settings/documents",
      color: "slate"
    },
    {
      title: "Knowledge Sources",
      description: "Enable or disable ERP data, Documents, and Web Search for the AI.",
      icon: Database,
      to: "/admin/settings/sources",
      color: "emerald"
    }
  ];

  if (!clientId) {
      return (
          <div className="flex flex-col items-center justify-center h-[50vh] text-center">
              <div className="bg-white p-8 rounded-2xl shadow-xl max-w-md border border-gray-100">
                  <div className="w-16 h-16 bg-blue-100/50 text-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                      <Settings size={32} />
                  </div>
                  <h2 className="text-2xl font-bold text-gray-800 mb-2">Welcome to Amoeba Admin</h2>
                  <p className="text-gray-500 mb-6">
                      Please select or create a client to begin configuring your AI implementation.
                  </p>
                  {/* Link to Legacy Onboarding for now using query param or just a direct component render? 
                      Actually, for simplicity, we'll just show a message. 
                      Since the user didn't ask to migrate "Create Client" explicitly, 
                      I will assume they handle "active client" via some other flow OR 
                      I should provide a way to SET the client ID here. 
                  */}
                  <div className="text-sm bg-yellow-50 text-yellow-700 p-3 rounded">
                      ⚠️ No Active Client Context found. <br/>
                      (Use the legacy onboarding panel to create one if needed)
                  </div>
              </div>
          </div>
      );
  }

  return (
    <div>
        <h1 className="text-3xl font-bold text-gray-800 mb-2">Dashboard</h1>
        <p className="text-gray-500 mb-6">Manage your semantic layer and report configurations.</p>

        {/* CONFIGURATION WARNINGS SUMMARY */}
        {warnings.length > 0 && (
            <div className="mb-8 p-4 bg-amber-50 border border-amber-200 rounded-2xl shadow-sm flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-amber-100 text-amber-600 rounded-xl flex items-center justify-center">
                        <Shield size={20} />
                    </div>
                    <div>
                        <h2 className="text-sm font-bold text-amber-900">System Health Warning</h2>
                        <p className="text-xs text-amber-700">Detected {warnings.length} issues that may cause runtime errors.</p>
                    </div>
                </div>
                <Link to="/admin/health" className="bg-amber-600 text-white px-4 py-2 rounded-lg text-xs font-bold shadow-sm hover:bg-amber-700 transition-all flex items-center gap-2">
                    Review & Fix Now
                    <ArrowRight size={12} />
                </Link>
            </div>
        )}

        {/* DOCUMENT SYSTEM HIGHLIGHT */}
        <div className="mb-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
                <DocumentMetricsCard />
            </div>
            <div className="lg:col-span-2 bg-gradient-to-br from-blue-600 to-indigo-700 rounded-2xl p-8 text-white shadow-xl relative overflow-hidden">
                <div className="relative z-10 h-full flex flex-col">
                    <h2 className="text-2xl font-bold mb-2">Knowledge System Management</h2>
                    <p className="text-blue-100 text-sm mb-6 max-w-md">
                        Control your AI's brain. Manage uploaded files, set enterprise limits, and toggle data sources to ensure high-quality retrieval.
                    </p>
                    <div className="mt-auto flex flex-wrap gap-3">
                        <Link to="/admin/documents" className="bg-white/20 hover:bg-white/30 backdrop-blur-md px-4 py-2 rounded-lg text-sm font-bold transition-all border border-white/10 flex items-center gap-2">
                             Manage Docs <ArrowRight size={14}/>
                        </Link>
                        <Link to="/admin/settings/documents" className="bg-white/20 hover:bg-white/30 backdrop-blur-md px-4 py-2 rounded-lg text-sm font-bold transition-all border border-white/10">
                             Quota Settings
                        </Link>
                    </div>
                </div>
                {/* Decorative Icon */}
                <FileText className="absolute -bottom-4 -right-4 w-40 h-40 text-white/5 -rotate-12" />
            </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* System Health Card */}
            <Link 
                to="/admin/health"
                className={`block group relative ${warnings.length > 0 ? 'ring-2 ring-amber-500 rounded-2xl' : ''}`}
            >
                <div className="absolute inset-0 bg-white rounded-2xl shadow-md transition-transform group-hover:-translate-y-1 duration-300 pointer-events-none"></div>
                <div className={`relative bg-white p-6 rounded-2xl shadow-sm border ${warnings.length > 0 ? 'border-amber-500' : 'border-gray-100'} h-full flex flex-col items-start transition-all group-hover:shadow-xl group-hover:border-amber-200`}>
                    <div className={`
                        w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-colors
                        ${warnings.length > 0 ? 'bg-amber-50 text-amber-600' : 'bg-blue-50 text-blue-600'} group-hover:bg-amber-100
                    `}>
                        <Shield size={24} />
                    </div>
                    
                    <h3 className="text-xl font-bold text-gray-800 mb-2 group-hover:text-amber-700 transition-colors">
                        System Health
                    </h3>
                    <p className="text-gray-500 text-sm leading-relaxed">
                        Automated diagnostics to find and fix configuration mismatches.
                    </p>

                    <div className="mt-auto pt-6 flex items-center gap-2 text-sm font-medium text-amber-600 opacity-0 group-hover:opacity-100 transition-opacity transform translate-y-2 group-hover:translate-y-0">
                        <span>Check Status</span>
                        <PlayCircle size={14} />
                    </div>
                </div>
            </Link>

            {cards.map((card: any) => (
                <Link 
                    key={card.title} 
                    to={card.to}
                    className={`block group relative ${card.highlight ? 'ring-2 ring-blue-500 rounded-2xl animate-pulse' : ''}`}
                >
                    <div className="absolute inset-0 bg-white rounded-2xl shadow-md transition-transform group-hover:-translate-y-1 duration-300 pointer-events-none"></div>
                    <div className={`relative bg-white p-6 rounded-2xl shadow-sm border ${card.highlight ? 'border-blue-500' : 'border-gray-100'} h-full flex flex-col items-start transition-all group-hover:shadow-xl group-hover:border-${card.color}-200`}>
                        {card.highlight && (
                            <span className="absolute -top-3 -right-2 bg-blue-600 text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-lg uppercase tracking-wider">
                                Recommended
                            </span>
                        )}
                        <div className={`
                            w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-colors
                            bg-${card.color}-50 text-${card.color}-600 group-hover:bg-${card.color}-100
                        `}>
                            <card.icon size={24} />
                        </div>
                        
                        <h3 className="text-xl font-bold text-gray-800 mb-2 group-hover:text-blue-700 transition-colors">
                            {card.title}
                        </h3>
                        <p className="text-gray-500 text-sm leading-relaxed">
                            {card.description}
                        </p>

                        <div className={`mt-auto pt-6 flex items-center gap-2 text-sm font-medium text-${card.color}-600 opacity-0 group-hover:opacity-100 transition-opacity transform translate-y-2 group-hover:translate-y-0`}>
                            <span>Open Tool</span>
                            <PlayCircle size={14} />
                        </div>
                    </div>
                </Link>
            ))}
        </div>
    </div>
  );
}
