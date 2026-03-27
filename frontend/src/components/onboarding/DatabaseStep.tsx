import React, { useState, useEffect } from 'react';
import { useAdmin } from '../../context/AdminContext';
import { Copy, CheckCircle, AlertTriangle, ArrowRight, ShieldCheck } from 'lucide-react';

interface DatabaseStepProps {
  onSuccess: (clientId: number, apiKey: string) => void;
}

export const DatabaseStep: React.FC<DatabaseStepProps> = ({ onSuccess }) => {
  const { setClientId, setApiKey, setClientName, clients, refreshClients } = useAdmin();
  const [clientNameInput, setClientNameInput] = useState('');
  const [localClientId, setLocalClientId] = useState<number | null>(null);
  const [localApiKey, setLocalApiKey] = useState<string | null>(null);
  
  const [dbConfig, setDbConfig] = useState(() => {
    const saved = localStorage.getItem('wizard_dbConfig');
    return saved ? JSON.parse(saved) : {
      db_type: 'postgresql',
      host: 'localhost',
      port: 5432,
      database: '',
      username: '',
      password: ''
    };
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mode, setMode] = useState<'select' | 'create'>('create');
  const [isEditable, setIsEditable] = useState(true);
  const [isVerified, setIsVerified] = useState(false);

  useEffect(() => {
    localStorage.setItem('wizard_dbConfig', JSON.stringify(dbConfig));
  }, [dbConfig]);

  useEffect(() => {
    refreshClients();
  }, []);

  const handleCreateClient = async () => {
    if (!clientNameInput.trim()) return;
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/clients/setup-db', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ client_name: clientNameInput })
      });
      const data = await response.json();
      if (data.status === 'success') {
        const { client_id, api_key } = data.data;
        setLocalClientId(client_id);
        setLocalApiKey(api_key);
        setClientId(client_id);
        setApiKey(api_key);
        setClientName(clientNameInput);
        
        await refreshClients();
        setMode('select'); 
      } else {
        setError(data.detail || 'Failed to create client');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const handleConnectDb = async () => {
    if (!localClientId) return;
    setLoading(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`/api/clients/${localClientId}/database`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(dbConfig)
      });
      const data = await response.json();
      if (data.status === 'success') {
        setIsVerified(true);
        setIsEditable(false);
      } else {
        setError(data.detail || 'Connection failed');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    if (localClientId) {
        onSuccess(localClientId, localApiKey || '');
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 p-6 rounded-xl border border-blue-100 flex justify-between items-center shadow-sm">
        <div>
          <h3 className="text-blue-900 font-bold text-lg">New ERP Onboarding</h3>
          <p className="text-blue-700 text-sm">Register and connect a fresh client database.</p>
        </div>
        <div className="flex flex-col items-end gap-2">
            <span className="text-[10px] font-bold text-blue-400 uppercase tracking-wider">Wizard Mode</span>
            {!isVerified && (
                <div className="flex bg-blue-100 p-1 rounded-lg">
                    <button 
                        onClick={() => {
                            setMode('create');
                            setLocalClientId(null);
                        }}
                        className={`px-3 py-1 text-xs font-bold rounded-md transition ${mode === 'create' && !localClientId ? 'bg-white text-blue-600 shadow-sm' : 'text-blue-500'}`}
                    >
                        New ERP
                    </button>
                    <button 
                        onClick={() => setMode('select')}
                        className={`px-3 py-1 text-xs font-bold rounded-md transition ${mode === 'select' || localClientId ? 'bg-white text-blue-600 shadow-sm' : 'text-blue-500'}`}
                    >
                        Modify Existing
                    </button>
                </div>
            )}
        </div>
      </div>

      {!localClientId ? (
        <div className="space-y-4">
          {mode === 'create' ? (
            <div className="bg-white p-10 rounded-2xl border-2 border-dashed border-gray-200 text-center space-y-6 shadow-sm">
              <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
              </div>
              <div>
                <h4 className="text-xl font-bold text-gray-800">Register New Client</h4>
                <p className="text-gray-500 text-sm">Enter the business name of the ERP you want to connect.</p>
              </div>
              <div className="max-w-md mx-auto space-y-4">
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="e.g. Thermosen Production"
                    className="flex-1 border-2 border-gray-100 p-4 rounded-xl focus:border-blue-500 outline-none transition text-lg"
                    value={clientNameInput}
                    onChange={(e) => setClientNameInput(e.target.value)}
                  />
                  <button
                    onClick={handleCreateClient}
                    disabled={loading || !clientNameInput.trim()}
                    className="bg-blue-600 text-white px-8 py-4 rounded-xl font-bold hover:bg-blue-700 disabled:opacity-50 transition shadow-lg shadow-blue-200"
                  >
                    {loading ? '...' : 'Register'}
                  </button>
                </div>
                {error && mode === 'create' && !localClientId && (
                  <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm font-medium border border-red-100 animate-in fade-in zoom-in-95 duration-200">
                    {error}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white p-8 rounded-2xl border border-gray-200 space-y-4 shadow-sm">
              <h4 className="font-bold text-gray-800">Choose Company to Modify</h4>
              <select 
                className="w-full border-2 border-gray-100 p-4 rounded-xl focus:border-blue-500 outline-none transition bg-gray-50 text-lg"
                onChange={(e) => {
                  const id = parseInt(e.target.value);
                  const c = clients.find(client => client.id === id);
                  if (c) {
                    setLocalClientId(c.id);
                    setLocalApiKey(c.api_key);
                    setClientId(c.id);
                    setApiKey(c.api_key);
                    setClientName(c.client_name);
                  }
                }}
                value={localClientId || ''}
              >
                <option value="">-- Select an existing company --</option>
                {clients.map(c => (
                  <option key={c.id} value={c.id}>{c.client_name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="flex justify-between items-center bg-gray-50 p-4 rounded-xl border border-gray-200">
            <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-green-100 text-green-600 rounded-full flex items-center justify-center font-bold">
                    {clients.find(c => c.id === localClientId)?.client_name.charAt(0)}
                </div>
                <div>
                    <p className="text-[10px] text-gray-400 font-bold uppercase tracking-tighter">Onboarding</p>
                    <span className="font-bold text-gray-800">{clients.find(c => c.id === localClientId)?.client_name}</span>
                </div>
            </div>
            {!isVerified && (
                <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 font-medium">Edit Fields</span>
                    <button 
                        onClick={() => setIsEditable(!isEditable)}
                        className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                        isEditable ? 'bg-blue-600' : 'bg-gray-300'
                        }`}
                    >
                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                            isEditable ? 'translate-x-4' : 'translate-x-0'
                        }`} />
                    </button>
                </div>
                <button onClick={() => {
                    setLocalClientId(null);
                    setMode('create');
                }} className="text-blue-600 text-sm font-bold hover:underline">Start New Registration</button>
                </div>
            )}
            {isVerified && (
                <div className="flex items-center gap-2 text-green-600 font-bold text-sm">
                    <CheckCircle size={16}/> Connected
                </div>
            )}
          </div>

          {localApiKey && (
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-xl animate-in fade-in slide-in-from-top-2 duration-300">
                  <div className="flex justify-between items-center mb-2">
                    <h4 className="text-xs font-bold text-yellow-800 uppercase flex items-center gap-1">
                        <ShieldCheck size={14}/> Widget API Key
                    </h4>
                    <span className="text-[10px] text-yellow-600 bg-yellow-100 px-2 py-0.5 rounded-full font-bold">New</span>
                  </div>
                  <div className="flex gap-2">
                    <code className="flex-1 bg-white border border-yellow-200 p-2.5 rounded-lg text-xs font-mono text-yellow-900 break-all">
                        {localApiKey}
                    </code>
                    <button 
                        onClick={() => {
                            navigator.clipboard.writeText(localApiKey);
                            // Simple feedback could be added here
                        }}
                        className="bg-white border border-yellow-200 p-2.5 rounded-lg text-yellow-700 hover:bg-yellow-100 transition shadow-sm"
                        title="Copy to clipboard"
                    >
                        <Copy size={16}/>
                    </button>
                  </div>
                  <p className="text-[10px] text-yellow-600 mt-2 italic">
                    Copy this key to your chat widget configuration. It will not be shown again after this session.
                  </p>
              </div>
          )}
          
          <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-xs font-bold text-gray-400 uppercase mb-1">Database Type</label>
                  <select 
                    className="w-full border-2 border-gray-100 p-3 rounded-lg disabled:bg-gray-50 disabled:text-gray-500 outline-none focus:border-blue-500 transition"
                    value={dbConfig.db_type}
                    onChange={(e) => setDbConfig({...dbConfig, db_type: e.target.value})}
                    disabled={!isEditable}
                  >
                    <option value="postgresql">PostgreSQL</option>
                    <option value="mysql">MySQL</option>
                    <option value="sqlite">SQLite</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase mb-1">Host</label>
                  <input 
                    type="text" 
                    className="w-full border-2 border-gray-100 p-3 rounded-lg disabled:bg-gray-50 disabled:text-gray-500 outline-none focus:border-blue-500 transition"
                    value={dbConfig.host}
                    onChange={(e) => setDbConfig({...dbConfig, host: e.target.value})}
                    disabled={!isEditable}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase mb-1">Port</label>
                  <input 
                    type="number" 
                    className="w-full border-2 border-gray-100 p-3 rounded-lg disabled:bg-gray-50 disabled:text-gray-500 outline-none focus:border-blue-500 transition"
                    value={dbConfig.port}
                    onChange={(e) => setDbConfig({...dbConfig, port: parseInt(e.target.value)})}
                    disabled={!isEditable}
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-bold text-gray-400 uppercase mb-1">Database Name</label>
                  <input 
                    type="text" 
                    className="w-full border-2 border-gray-100 p-3 rounded-lg disabled:bg-gray-50 disabled:text-gray-500 outline-none focus:border-blue-500 transition"
                    value={dbConfig.database}
                    onChange={(e) => setDbConfig({...dbConfig, database: e.target.value})}
                    disabled={!isEditable}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase mb-1">Username</label>
                  <input 
                    type="text" 
                    className="w-full border-2 border-gray-100 p-3 rounded-lg disabled:bg-gray-50 disabled:text-gray-500 outline-none focus:border-blue-500 transition"
                    value={dbConfig.username}
                    onChange={(e) => setDbConfig({...dbConfig, username: e.target.value})}
                    disabled={!isEditable}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-400 uppercase mb-1">Password</label>
                  <input 
                    type="password" 
                    className="w-full border-2 border-gray-100 p-3 rounded-lg disabled:bg-gray-50 disabled:text-gray-500 outline-none focus:border-blue-500 transition"
                    value={dbConfig.password}
                    onChange={(e) => setDbConfig({...dbConfig, password: e.target.value})}
                    disabled={!isEditable}
                  />
                </div>
              </div>

              {error && <div className="p-3 bg-red-50 text-red-600 rounded-lg text-sm font-medium border border-red-100 flex items-center gap-2"><AlertTriangle size={16}/> {error}</div>}

              {!isVerified ? (
                <button
                    onClick={handleConnectDb}
                    disabled={loading || !isEditable}
                    className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold hover:bg-blue-700 transition disabled:opacity-50 shadow-lg shadow-blue-100"
                >
                    {loading ? 'Verifying Connection...' : 'Connect ERP Database →'}
                </button>
              ) : (
                <button
                    onClick={handleNext}
                    className="w-full bg-green-600 text-white py-4 rounded-xl font-bold hover:bg-green-700 transition flex items-center justify-center gap-2 shadow-lg shadow-green-100"
                >
                    Connection Verified! Continue to Table Selection <ArrowRight size={20}/>
                </button>
              )}
          </div>
        </div>
      )}
    </div>
  );
};
