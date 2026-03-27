import { useState, useEffect } from "react";
import { useAdmin } from "../context/AdminContext";
import { 
    Cpu, Save, Loader2, Check, AlertTriangle, 
    Sparkles, Zap, Shield, Bot, Terminal, Info
} from "lucide-react";
import { apiFetch } from "../utils/api";
import { SearchableDropdown } from "../components/admin/SearchableDropdown";

interface AISettingsData {
    provider: string;
    model: string;
    temperature: number;
    max_tokens: number;
}

export default function AISettings() {
    const { clientId, apiKey } = useAdmin();
    const [settings, setSettings] = useState<AISettingsData | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState<{type: "success" | "error", text: string} | null>(null);

    const API_BASE = import.meta.env.VITE_API_URL || "";

    const showMessage = (type: "success" | "error", text: string) => {
        setMessage({ type, text });
        setTimeout(() => setMessage(null), 4000);
    };

    useEffect(() => {
        if (!clientId) return;
        const fetchSettings = async () => {
            setLoading(true);
            try {
                const res = await apiFetch(`${API_BASE}/ai-settings/${clientId}`.replace(/\/\//g, '/').replace(':/', '://'), {
                    headers: { "X-API-Key": apiKey || "" }
                });
                if (res.ok) {
                    const data = await res.json();
                    setSettings(data);
                }
            } catch (err) {
                console.error("Failed to fetch AI settings:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchSettings();
    }, [clientId, apiKey]);

    const handleSave = async () => {
        if (!clientId || !settings) return;
        setSaving(true);
        try {
            const res = await apiFetch(`${API_BASE}/ai-settings/${clientId}`.replace(/\/\//g, '/').replace(':/', '://'), {
                method: "PUT",
                headers: { "Content-Type": "application/json", "X-API-Key": apiKey || "" },
                body: JSON.stringify(settings)
            });
            if (res.ok) {
                showMessage("success", "AI Brain updated successfully!");
            } else {
                throw new Error("Failed to update settings");
            }
        } catch (err: any) {
            showMessage("error", err.message);
        } finally {
            setSaving(false);
        }
    };

    if (!clientId) return <div className="p-8 text-center text-gray-500 font-bold uppercase tracking-widest text-xs">Please select a client from the dashboard.</div>;

    const providers = [
        { id: 'gemini', name: 'Google Gemini', icon: <Sparkles className="text-blue-500"/>, models: ['gemini-2.0-flash-lite', 'gemini-1.5-pro'] },
        { id: 'openai', name: 'OpenAI GPT', icon: <Zap className="text-emerald-500"/>, models: ['gpt-4-turbo', 'gpt-3.5-turbo'] },
        { id: 'ollama', name: 'Local Ollama', icon: <Terminal className="text-orange-500"/>, models: ['llama3:latest', 'llama3.2:latest', 'mistral', 'phi3'] },
    ];

    return (
        <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="p-6 border-b border-gray-100 flex justify-between items-center bg-slate-50/50">
                    <div>
                        <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
                            <Cpu size={20} className="text-indigo-600"/> AI Infrastructure Settings
                        </h2>
                        <p className="text-sm text-gray-500 mt-1">Configure the primary LLM brain and operational parameters for this client.</p>
                    </div>
                    {message && (
                        <div className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${message.type === "success" ? "bg-green-50 text-green-700 border border-green-100" : "bg-red-50 text-red-700 border border-red-100"}`}>
                            {message.type === "success" ? <Check size={16}/> : <AlertTriangle size={16}/>}
                            {message.text}
                        </div>
                    )}
                </div>

                <div className="p-8">
                    {loading ? (
                        <div className="py-20 flex flex-col items-center justify-center space-y-4">
                            <Loader2 className="animate-spin text-indigo-600" size={40} />
                            <p className="text-xs font-black text-slate-400 uppercase tracking-widest">Loading Brain Config...</p>
                        </div>
                    ) : settings && (
                        <div className="max-w-4xl space-y-10">
                            {/* Provider Selection */}
                            <section className="space-y-4">
                                <h3 className="text-sm font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                    <Shield size={14}/> 1. Choose Provider
                                </h3>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    {providers.map(p => (
                                        <button
                                            key={p.id}
                                            onClick={() => setSettings({...settings, provider: p.id, model: p.models[0]})}
                                            className={`p-5 rounded-2xl border-2 text-left transition-all ${
                                                settings.provider === p.id 
                                                ? 'border-indigo-600 bg-indigo-50/50 ring-4 ring-indigo-50' 
                                                : 'border-slate-100 hover:border-slate-200 bg-white'
                                            }`}
                                        >
                                            <div className="mb-3">{p.icon}</div>
                                            <div className="font-bold text-slate-800">{p.name}</div>
                                            <div className="text-[10px] text-slate-400 uppercase mt-1 font-black">
                                                {p.id === 'ollama' ? 'Local Compute' : 'Cloud API'}
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </section>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                {/* Model Selection */}
                                <section className="space-y-4">
                                    <h3 className="text-sm font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                        <Bot size={14}/> 2. Select Model
                                    </h3>
                                    <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100">
                                        <SearchableDropdown
                                            options={[
                                                ...(providers.find(p => p.id === settings.provider)?.models.map(m => ({ value: m, label: m })) || []),
                                                ...(settings.provider === 'ollama' ? [{ value: 'llama3', label: 'llama3' }] : [])
                                            ]}
                                            value={settings.model}
                                            onChange={val => setSettings({ ...settings, model: val })}
                                            placeholder="Select model..."
                                        />
                                        <p className="text-[10px] text-slate-400 mt-3 italic">
                                            Switching models will immediately affect response quality and token usage.
                                        </p>
                                    </div>
                                </section>

                                {/* Performance Parameters */}
                                <section className="space-y-4">
                                    <h3 className="text-sm font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                        <Terminal size={14}/> 3. Response Style
                                    </h3>
                                    <div className="bg-slate-50 p-6 rounded-2xl border border-slate-100 space-y-6">
                                        <div>
                                            <div className="flex justify-between mb-2">
                                                <label className="text-xs font-bold text-slate-600 flex items-center gap-1">
                                                    Creativity Level
                                                    <div className="group relative">
                                                        <Info size={12} className="text-slate-400 cursor-help" />
                                                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-gray-900 text-white text-[10px] rounded shadow-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
                                                            Lower values make the AI more factual and consistent. Higher values make it more conversational but less predictable.
                                                        </div>
                                                    </div>
                                                </label>
                                                <span className={`text-[10px] font-black px-2 py-0.5 rounded-full uppercase ${
                                                    settings.temperature <= 0.3 ? 'bg-blue-100 text-blue-700' :
                                                    settings.temperature <= 0.7 ? 'bg-indigo-100 text-indigo-700' :
                                                    'bg-purple-100 text-purple-700'
                                                }`}>
                                                    {settings.temperature <= 0.3 ? 'Precise' : 
                                                     settings.temperature <= 0.7 ? 'Balanced' : 'Creative'}
                                                </span>
                                            </div>
                                            <input 
                                                type="range" min="0" max="1" step="0.1"
                                                className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                                                value={settings.temperature}
                                                onChange={e => setSettings({...settings, temperature: parseFloat(e.target.value)})}
                                            />
                                            <div className="flex justify-between mt-2 text-[9px] font-bold text-slate-400 uppercase tracking-tighter">
                                                <span>Factual</span>
                                                <span>Standard</span>
                                                <span>Creative</span>
                                            </div>
                                        </div>
                                        <div>
                                            <label className="text-xs font-bold text-slate-600 block mb-2">Memory Limit (Max Tokens)</label>
                                            <input 
                                                type="number"
                                                className="w-full bg-white border border-slate-200 p-3 rounded-xl font-bold text-slate-700 outline-none"
                                                value={settings.max_tokens}
                                                onChange={e => setSettings({...settings, max_tokens: parseInt(e.target.value)})}
                                            />
                                            <p className="text-[10px] text-slate-400 mt-2 italic">How much information the AI can process/generate at once.</p>
                                        </div>
                                    </div>
                                </section>
                            </div>

                            <div className="pt-6 border-t border-slate-100 flex justify-end">
                                <button
                                    onClick={handleSave}
                                    disabled={saving}
                                    className="bg-indigo-600 text-white px-10 py-4 rounded-2xl font-black text-sm flex items-center gap-2 hover:bg-indigo-700 transition-all shadow-xl shadow-indigo-100 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50"
                                >
                                    {saving ? <Loader2 className="animate-spin" size={18}/> : <Save size={18}/>}
                                    {saving ? "UPDATING BRAIN..." : "SAVE AI SETTINGS"}
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
