import { createContext, useContext, useState, type ReactNode } from "react";

interface AdminContextType {
  clientId: number | null;
  setClientId: (id: number | null) => void;
  apiKey: string | null;
  setApiKey: (key: string | null) => void;
  clientName: string;
  setClientName: (name: string) => void;
  clients: any[];
  refreshClients: () => Promise<void>;
}

const AdminContext = createContext<AdminContextType | undefined>(undefined);

export function AdminProvider({ children }: { children: ReactNode }) {
  // Initialize from localStorage if available (simple persistence)
  const [clientId, setClientIdState] = useState<number | null>(() => {
    const saved = localStorage.getItem("admin_clientId");
    return saved ? parseInt(saved) : null;
  });
  
  const [apiKey, setApiKeyState] = useState<string | null>(() => {
    return localStorage.getItem("admin_apiKey");
  });
  
  const [clientName, setClientNameState] = useState(() => {
    return localStorage.getItem("admin_clientName") || "";
  });

  const [clients, setClients] = useState<any[]>([]);

  const refreshClients = async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    try {
      const response = await fetch('http://localhost:8000/api/clients', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setClients(data.clients || []);
    } catch (err) {
      console.error('Failed to refresh clients in context', err);
    }
  };

  const setClientId = (id: number | null) => {
      setClientIdState(id);
      if (id) localStorage.setItem("admin_clientId", id.toString());
      else localStorage.removeItem("admin_clientId");
  };

  const setApiKey = (key: string | null) => {
      setApiKeyState(key);
      if (key) localStorage.setItem("admin_apiKey", key);
      else localStorage.removeItem("admin_apiKey");
  };

  const setClientName = (name: string) => {
      setClientNameState(name);
      localStorage.setItem("admin_clientName", name);
  };

  return (
    <AdminContext.Provider value={{ clientId, setClientId, apiKey, setApiKey, clientName, setClientName, clients, refreshClients }}>
      {children}
    </AdminContext.Provider>
  );
}

export function useAdmin() {
  const context = useContext(AdminContext);
  if (!context) throw new Error("useAdmin must be used within AdminProvider");
  return context;
}
