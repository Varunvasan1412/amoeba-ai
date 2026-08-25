import { Link } from "react-router-dom";
import { 
  Rocket, 
  FileText,
  Map,
  Cpu,
  ArrowRight,
  Database,
  LayoutTemplate,
  Settings,
  PlayCircle,
  Activity,
  Shield,
  Archive,
  Users,
  Building2,
  ShieldCheck
} from "lucide-react";
import { useAdmin } from "../context/AdminContext";
import { useAuth } from "../context/AuthContext";
import { useState, useEffect } from "react";
import { apiFetch } from "../utils/api";
import DocumentMetricsCard from "../components/admin/DocumentMetricsCard";
import RoleGuard from "../components/RoleGuard";

export default function AdminDashboard() {
  const { clientId } = useAdmin();
  const [onboardingCompleted, setOnboardingCompleted] = useState<boolean | null>(null);

  useEffect(() => {
    if (clientId) {
      fetchOnboardingStatus();
    }
  }, [clientId]);

  const fetchOnboardingStatus = async () => {
    try {
      const response = await apiFetch(`/api/clients/${clientId}/onboarding/status`);
      const data = await response.json();
      setOnboardingCompleted(data.onboarding_completed);
    } catch (err) {
      console.error("Failed to fetch onboarding status", err);
    }
  };


  const { user } = useAuth();

  const cards = [
    {
      title: "Setup Wizard",
      description: "Step-by-step guide to connect your ERP, map business names, and launch.",
      icon: Rocket,
      to: "/admin/wizard",
      color: "blue",
      highlight: !onboardingCompleted,
      permission: "access_wizard",
      featureKey: "feature_wizard_enabled"
    },
    {
      title: "Relationship Governance",
      description: "Govern how different data sources link together and manage join paths.",
      icon: Shield,
      to: "/admin/relationships",
      color: "red",
      permission: "access_relationships",
      featureKey: "feature_relationships_enabled"
    },
    {
      title: "Semantic Graph",
      description: "Map technical columns to easy-to-understand labels for the AI.",
      icon: Database,
      to: "/admin/semantic",
      color: "emerald",
      permission: "access_semantic",
      featureKey: "feature_semantic_enabled"
    },
    {
      title: "Reports & Views",
      description: "Build beautiful SQL-free reports and manage your saved data library.",
      icon: LayoutTemplate,
      to: "/admin/reports",
      color: "purple",
      permission: "access_reports",
      featureKey: "feature_reports_enabled"
    },
    {
      title: "Intelligent Routing",
      description: "Map conversational intents and modules to specific ERP tables.",
      icon: Map,
      to: "/admin/routes",
      color: "indigo",
      permission: "access_routing",
      featureKey: "feature_routing_enabled"
    },
    {
      title: "AI Infrastructure",
      description: "Switch between LLM providers (Gemini, OpenAI, Ollama) and configure model settings.",
      icon: Cpu,
      to: "/admin/ai-settings",
      color: "indigo",
      permission: "access_ai_settings",
      featureKey: "feature_ai_settings_enabled",
      platformOnly: true
    },

    {
      title: "System Health & Audit",
      description: "Unified dashboard for database integrity, document pipelines, and all system activity logs.",
      icon: Activity,
      to: "/admin/system-health",
      color: "rose",
      permission: "access_health",
      featureKey: "feature_health_enabled"
    },
    {
      title: "System Backups",
      description: "Comprehensive database protection suite. Manage automated schedules, manual dumps, and safety-validated restores.",
      icon: Archive,
      to: "/admin/backups",
      color: "teal",
      permission: "access_backups",
      featureKey: "feature_backups_enabled",
      platformOnly: true
    },
    {
      title: "Tenants & Companies",
      description: "Onboard new multi-tenant enterprise clients and manage company codes for secure isolation.",
      icon: Building2,
      to: "/admin/tenants",
      color: "blue",
      permission: "access_tenants",
      featureKey: "feature_tenants_enabled",
      platformOnly: true
    },
    {
      title: "System Access & RBAC",
      description: "Manage users, custom roles, and granular security permissions for the entire platform.",
      icon: Users,
      to: "/admin/security",
      color: "cyan",
      permission: "access_security",
      featureKey: "feature_security_enabled"
    },
    {
      title: "Login Activity",
      description: "Real-time audit trail of all authentication attempts with IP and user-agent tracking.",
      icon: ShieldCheck,
      to: "/admin/audit/login",
      color: "emerald",
      permission: "view_logs"
    }
  ];

  const { clients } = useAdmin();

  // Helper to reliably check if user is a platform admin
  const isPlatformAdmin = user?.role === 'SUPER_ADMIN' || (user as any)?.role_name === 'SUPER_ADMIN' || user?.is_platform_user;

  // Filter cards based on user permissions, tenant feature flags, and client context
  const filteredCards = cards.filter(card => {
    if (!user) return false;
    
    // Platform-only cards require platform admin status
    if (card.platformOnly) {
        return isPlatformAdmin;
    }

    // Logic for when NO client is selected
    if (!clientId) {
        // Only allow Setup Wizard, Security, and Login Activity for Platform Admins when no client is active
        const isGlobalTool = ["Setup Wizard", "System Access & RBAC", "Login Activity"].includes(card.title);
        if (isPlatformAdmin && isGlobalTool) return true;
        return false;
    }

    // Feature Toggle check (Skipped for platform admins so they always have access)
    if (!isPlatformAdmin && (card as any).featureKey) {
        const client = clients.find(c => c.id === clientId);
        if (client && client[(card as any).featureKey] === false) {
            return false;
        }
    }

    // If platform admin, they get access to everything once a client is selected
    if (isPlatformAdmin) return true;
    
    // Otherwise, check granular permissions
    if (!card.permission) return true;
    
    const required = Array.isArray(card.permission) ? card.permission : [card.permission];
    const userPerms = user.permissions || [];
    return required.some(p => userPerms.includes(p));
  });

  if (!clientId && !isPlatformAdmin) {
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

        {!clientId && (
            <div className="mb-6 bg-amber-50 border border-amber-200 p-4 rounded-xl flex items-center gap-3 text-amber-800 animate-in fade-in slide-in-from-top-4">
                <Settings className="text-amber-500" />
                <div>
                    <p className="font-bold">System Management Mode</p>
                    <p className="text-sm opacity-90">No active client selected. Showing platform-level management tools only.</p>
                </div>
            </div>
        )}


        {/* DOCUMENT SYSTEM HIGHLIGHT */}
        {clientId && (
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
                            <RoleGuard permission="upload_document">
                                <Link to="/admin/documents" className="bg-white/20 hover:bg-white/30 backdrop-blur-md px-4 py-2 rounded-lg text-sm font-bold transition-all border border-white/10 flex items-center gap-2">
                                    Manage Docs <ArrowRight size={14}/>
                                </Link>
                            </RoleGuard>
                            {isPlatformAdmin && (
                                <RoleGuard permission="configure_system">
                                    <Link to="/admin/settings/documents" className="bg-white/20 hover:bg-white/30 backdrop-blur-md px-4 py-2 rounded-lg text-sm font-bold transition-all border border-white/10 text-white no-underline">
                                        Quota Settings
                                    </Link>
                                </RoleGuard>
                            )}
                        </div>
                    </div>
                    {/* Decorative Icon */}
                    <FileText className="absolute -bottom-4 -right-4 w-40 h-40 text-white/5 -rotate-12" />
                </div>
            </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredCards.map((card: any) => (
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
