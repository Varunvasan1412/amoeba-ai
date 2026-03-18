import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import { useAdmin } from "../context/AdminContext";
import { useAuth } from "../context/AuthContext";
import { LayoutDashboard, LogOut } from "lucide-react";
import { apiFetch } from "../utils/api";
import { SearchableDropdown } from "./admin/SearchableDropdown";

export default function AdminLayout() {
    const { clientId, setClientId, setApiKey, setClientName, clients, refreshClients } = useAdmin();
    const { logout, user, token } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();
  
      const [loading, setLoading] = useState(false);
  
      useEffect(() => {
          const init = async () => {
              setLoading(true);
              await refreshClients();
              setLoading(false);
          };
          init();
      }, [token]);
  
      const handleClientChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
          const id = parseInt(e.target.value);
          const client = clients.find(c => c.id === id);
          if (client) {
              setClientId(client.id);
              setApiKey(client.api_key);
              setClientName(client.client_name);
          }
      };

      const handleLogout = () => {
          logout();
          navigate("/login");
      };
      
    return (
      <div className="min-h-screen bg-gray-50 font-sans text-gray-800 flex flex-col">
        {/* Header */}
        <div className="bg-slate-900 text-white p-4 px-8 flex justify-between items-center shadow-lg z-10">
            <div className="flex items-center gap-4">
                <Link to="/admin" className="text-xl font-bold flex items-center gap-2 hover:text-blue-400 transition-colors">
                    <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center font-mono">A</div>
                    Amoeba Admin
                </Link>
                <span className="text-slate-500 text-sm hidden md:inline">|</span>
                <span className="text-slate-400 text-sm hidden md:inline">v2.0 Control Panel</span>
            </div>
  
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                  <span className="text-slate-400 text-sm hidden sm:inline">Active Client:</span>
                  <SearchableDropdown
                      theme="dark"
                      className="min-w-[180px]"
                      options={clients.map(c => ({ value: c.id, label: c.client_name }))}
                      value={clientId}
                      onChange={(id) => {
                          const client = clients.find(c => c.id === id);
                          if (client) {
                              setClientId(client.id);
                              setApiKey(client.api_key);
                              setClientName(client.client_name);
                          }
                      }}
                      disabled={loading}
                      placeholder="-- Select Client --"
                  />
                  {loading && <span className="text-xs text-slate-500 animate-pulse">Loading...</span>}
              </div>

              <div className="h-6 w-px bg-slate-700 mx-2"></div>

              <div className="flex items-center gap-3">
                  <span className="text-slate-300 text-sm font-medium">{user?.username}</span>
                  <button 
                    onClick={handleLogout}
                    className="p-2 hover:bg-slate-800 rounded-full text-slate-400 hover:text-red-400 transition-all flex items-center gap-1 text-sm"
                    title="Logout"
                  >
                    <LogOut size={18} />
                  </button>
              </div>
            </div>
        </div>

      {/* Breadcrumbs / Sub-nav (Optional) */}
      {location.pathname !== "/admin" && (
          <div className="bg-white border-b border-gray-200 px-8 py-3 flex items-center gap-2 text-sm text-gray-500">
              <Link to="/admin" className="hover:text-blue-600 flex items-center gap-1">
                <LayoutDashboard size={14}/> Dashboard
              </Link>
              <span>/</span>
              <span className="text-gray-800 font-medium capitalize">
                {location.pathname.split("/").pop()}
              </span>
          </div>
      )}

      {/* Content Area */}
      <div className="flex-1 p-8 overflow-y-auto">
          <div className="max-w-6xl mx-auto">
               <Outlet />
          </div>
      </div>
    </div>
  );
}
