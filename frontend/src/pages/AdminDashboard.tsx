import { Link } from "react-router-dom";
import { Database, FileText, LayoutTemplate, Settings, PlayCircle, Shield, Rocket } from "lucide-react";
import { useAdmin } from "../context/AdminContext";
import { useState, useEffect } from "react";

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
      const token = localStorage.getItem('token');
      const response = await fetch(`http://localhost:8000/api/clients/${clientId}/onboarding/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setOnboardingCompleted(data.onboarding_completed);
    } catch (err) {
      console.error("Failed to fetch onboarding status", err);
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
      title: "Business Names",
      description: "Map technical columns to easy-to-understand labels for the AI.",
      icon: Database,
      to: "/admin/semantic",
      color: "emerald"
    },
    {
      title: "Report Builder",
      description: "Create automated reports and custom SQL-free views.",
      icon: LayoutTemplate,
      to: "/admin/builder",
      color: "purple"
    },
    {
      title: "Saved Views",
      description: "Access and manage your library of registered data reports.",
      icon: FileText,
      to: "/admin/reports",
      color: "blue"
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
        <p className="text-gray-500 mb-8">Manage your semantic layer and report configurations.</p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
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
