// @ts-nocheck
import { useState, useEffect } from "react";
import { useAdmin } from "../context/AdminContext";
import { Sparkles, Plus, Check, ArrowRight, Loader2, Link2, Filter, Search, Database } from "lucide-react";
import { apiFetch } from "../utils/api";

interface Concept {
  id?: number;
  ui_label: string;
  database_table: string;
  default_filter?: string;
}

export default function AppConcepts() {
  const { clientId, apiKey } = useAdmin();
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [loading, setLoading] = useState(false);
  const [learning, setLearning] = useState(false);
  
  // Wizard State
  const [isWizardOpen, setIsWizardOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [newConcept, setNewConcept] = useState<Concept>({ ui_label: "", database_table: "" });
  
  // Real tables from database
  const [allTables, setAllTables] = useState<{name: string, columns: string[]}[]>([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const [tableSearch, setTableSearch] = useState("");
  
  const [conditionField, setConditionField] = useState("");
  const [conditionValue, setConditionValue] = useState("");

  const API_BASE = import.meta.env.VITE_API_URL || "";

  useEffect(() => {
    fetchConcepts();
  }, [clientId]);

  // Fetch real tables from the client's connected database
  useEffect(() => {
    if (!clientId) return;
    setLoadingTables(true);
    apiFetch(`${API_BASE}/clients/${clientId}/tables`.replace(/\/\//g, '/').replace(':/', '://'), {
      headers: { "X-API-Key": apiKey || "" }
    })
    .then(res => res.ok ? res.json() : { tables: [] })
    .then(data => setAllTables(data.tables || []))
    .catch(err => console.error("Failed to fetch tables:", err))
    .finally(() => setLoadingTables(false));
  }, [clientId]);

  const fetchConcepts = async () => {
    if (!clientId) return;
    setLoading(true);
    try {
      const res = await apiFetch(`${API_BASE}/v2/semantic/mappings?client_id=${clientId}`, {
        headers: { "X-API-Key": apiKey || "" }
      });
      if (res.ok) {
        setConcepts(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const learnFromApp = async () => {
    setLearning(true);
    try {
      const res = await apiFetch(`${API_BASE}/v2/semantic/discover`, {
        method: "POST",
        headers: { "X-API-Key": apiKey || "" }
      });
      const data = await res.json();
      if (data.suggested_concepts && data.suggested_concepts.length > 0) {
        alert(`Found ${data.suggested_concepts.length} concepts! (e.g. ${data.suggested_concepts[0].concept_name})`);
      }
    } catch (e) {
      console.error(e);
    }
    setLearning(false);
  };

  const handleNextStep = () => {
    if (step === 1) {
      // Pre-fill search with the concept name to help user find matching table
      setTableSearch(newConcept.ui_label.toLowerCase());
    }
    setStep(step + 1);
  };

  const handleSaveConcept = async () => {
    let finalConcept = { ...newConcept };
    if (conditionField && conditionValue) {
      finalConcept.default_filter = `${conditionField} = '${conditionValue}'`;
    }

    try {
      await apiFetch(`${API_BASE}/v2/semantic/mapping`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": apiKey || "" },
        body: JSON.stringify({
          client_id: clientId,
          ui_label: finalConcept.ui_label,
          database_table: finalConcept.database_table,
          default_filter: finalConcept.default_filter
        })
      });
      setIsWizardOpen(false);
      setStep(1);
      fetchConcepts();
    } catch (e) {
      console.error(e);
    }
  };

  // Sort tables: exact/partial matches first, then alphabetical
  const getSortedTables = () => {
    const search = tableSearch.toLowerCase().trim();
    if (!search) return allTables;
    
    const exact = allTables.filter(t => t.name.toLowerCase() === search);
    const startsWith = allTables.filter(t => t.name.toLowerCase().startsWith(search) && t.name.toLowerCase() !== search);
    const contains = allTables.filter(t => t.name.toLowerCase().includes(search) && !t.name.toLowerCase().startsWith(search));
    const rest = allTables.filter(t => !t.name.toLowerCase().includes(search));
    return [...exact, ...startsWith, ...contains, ...rest];
  };

  // Already-mapped table names for filtering
  const mappedTableNames = new Set(concepts.map(c => c.database_table));

  if (isWizardOpen) {
    const filteredTables = getSortedTables().filter(t => !mappedTableNames.has(t.name));
    
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-slate-800">Teach Amoeba</h2>
          <div className="flex items-center space-x-2 mt-4 text-sm text-slate-500">
            <span className={step >= 1 ? "text-indigo-600 font-bold" : ""}>1. Name</span>
            <span>→</span>
            <span className={step >= 2 ? "text-indigo-600 font-bold" : ""}>2. Data Source</span>
            <span>→</span>
            <span className={step >= 3 ? "text-indigo-600 font-bold" : ""}>3. Rules</span>
            <span>→</span>
            <span className={step >= 4 ? "text-indigo-600 font-bold" : ""}>4. Summary</span>
          </div>
        </div>

        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          {step === 1 && (
            <div className="space-y-4">
              <h3 className="text-lg font-medium">What do you call this in your application?</h3>
              <input 
                type="text" 
                placeholder="e.g. Vendor, City, Quotation" 
                className="w-full p-3 border border-slate-300 rounded-lg"
                value={newConcept.ui_label}
                onChange={e => setNewConcept({...newConcept, ui_label: e.target.value})}
              />
              <button onClick={handleNextStep} disabled={!newConcept.ui_label.trim()} className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50">Continue</button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h3 className="text-lg font-medium">Which database table stores "{newConcept.ui_label}" data?</h3>
              <p className="text-sm text-slate-500">Select the real table from your connected database.</p>
              
              {/* Search bar */}
              <div className="relative">
                <Search className="absolute left-3 top-3 w-4 h-4 text-slate-400" />
                <input 
                  type="text"
                  placeholder="Search tables..."
                  className="w-full pl-10 p-3 border border-slate-300 rounded-lg"
                  value={tableSearch}
                  onChange={e => setTableSearch(e.target.value)}
                />
              </div>

              {loadingTables ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
                  <span className="ml-2 text-slate-500">Loading tables from your database...</span>
                </div>
              ) : filteredTables.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <Database className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                  <p>No matching tables found. Make sure your database is connected.</p>
                </div>
              ) : (
                <div className="max-h-64 overflow-y-auto space-y-2 border border-slate-200 rounded-lg p-2">
                  {filteredTables.map(table => (
                    <div 
                      key={table.name} 
                      className={`p-3 border rounded-lg cursor-pointer transition-all ${
                        newConcept.database_table === table.name 
                          ? 'border-indigo-600 bg-indigo-50 shadow-sm' 
                          : 'border-slate-200 hover:border-indigo-300 hover:bg-slate-50'
                      }`} 
                      onClick={() => setNewConcept({...newConcept, database_table: table.name})}
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-semibold text-slate-800">{table.name}</div>
                        <span className="text-xs text-slate-400">{table.columns?.length || 0} columns</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex space-x-3">
                <button onClick={() => setStep(1)} className="text-slate-500 hover:text-slate-700 px-4 py-2">Back</button>
                <button onClick={handleNextStep} disabled={!newConcept.database_table} className="bg-indigo-600 text-white px-6 py-2 rounded-lg disabled:opacity-50">Continue</button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <h3 className="text-lg font-medium">When should Amoeba consider something a "{newConcept.ui_label}"?</h3>
              <div className="p-4 border border-slate-200 rounded-lg bg-slate-50 space-y-4">
                <div className="flex items-center space-x-2">
                  <input type="radio" name="rule" defaultChecked />
                  <span>Only use information where...</span>
                </div>
                <div className="flex space-x-2 pl-6">
                  <input type="text" placeholder="Field (e.g. type)" className="p-2 border rounded" value={conditionField} onChange={e=>setConditionField(e.target.value)} />
                  <span className="p-2 text-slate-500">is exactly</span>
                  <input type="text" placeholder="Value (e.g. quotation)" className="p-2 border rounded" value={conditionValue} onChange={e=>setConditionValue(e.target.value)} />
                </div>
              </div>
              <button onClick={handleNextStep} className="bg-indigo-600 text-white px-6 py-2 rounded-lg">Continue</button>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-6">
              <h3 className="text-xl font-bold text-slate-800">Concept Summary: {newConcept.ui_label}</h3>
              <div className="space-y-3">
                <div className="flex items-center text-green-700">
                  <Check className="w-5 h-5 mr-2" /> Information Source Confirmed
                </div>
                {conditionField && (
                  <div className="flex items-center text-green-700">
                    <Filter className="w-5 h-5 mr-2" /> Only where {conditionField} is '{conditionValue}'
                  </div>
                )}
              </div>
              <div className="flex space-x-3 pt-4">
                <button onClick={handleSaveConcept} className="bg-indigo-600 text-white px-6 py-2 rounded-lg flex items-center">
                  <Check className="w-4 h-4 mr-2" /> Save Concept
                </button>
                <button onClick={() => setIsWizardOpen(false)} className="text-slate-500 hover:text-slate-700 px-4 py-2">Cancel</button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 h-full bg-slate-50">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-800 tracking-tight">App Concepts</h1>
          <p className="text-slate-500 mt-1">Teach Amoeba the terminology used in your application.</p>
        </div>
        <div className="flex space-x-3 pr-40">
          <button 
            onClick={learnFromApp}
            disabled={learning}
            className="flex items-center bg-indigo-50 text-indigo-700 px-4 py-2 rounded-lg hover:bg-indigo-100 font-medium transition-colors border border-indigo-200"
          >
            {learning ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
            Learn From My App
          </button>
          <button 
            onClick={() => { setIsWizardOpen(true); setStep(1); setNewConcept({ui_label: "", database_table: ""}); setConditionField(""); setConditionValue(""); }}
            className="flex items-center bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 shadow-sm font-medium transition-all"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Concept
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-12"><Loader2 className="w-8 h-8 animate-spin text-indigo-600" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {concepts.map((concept, i) => (
            <div key={i} className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <h3 className="text-lg font-bold text-slate-800">{concept.ui_label}</h3>
              <div className="mt-4 space-y-2 text-sm text-slate-600">
                <div className="flex items-center">
                  <Database className="w-4 h-4 mr-2 text-slate-400" /> Source mapped internally
                </div>
                {concept.default_filter && (
                  <div className="flex items-center">
                    <Filter className="w-4 h-4 mr-2 text-slate-400" /> Filter rules applied
                  </div>
                )}
                <div className="flex items-center">
                  <Link2 className="w-4 h-4 mr-2 text-slate-400" /> Configured connections
                </div>
              </div>
              <button className="mt-6 text-indigo-600 font-medium text-sm hover:text-indigo-800">Edit Concept</button>
            </div>
          ))}
          
          {concepts.length === 0 && !loading && (
            <div className="col-span-3 text-center py-16 bg-white rounded-xl border border-dashed border-slate-300">
              <Sparkles className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <h3 className="text-lg font-medium text-slate-900">No Concepts Taught Yet</h3>
              <p className="text-slate-500 mt-1 max-w-sm mx-auto">Click "Learn From My App" to have Amoeba automatically discover your business concepts.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
