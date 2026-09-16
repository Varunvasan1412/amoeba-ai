import { useState } from "react";
import LegacySemanticMapper from "./LegacySemanticMapper";
import AppConcepts from "./AppConcepts";

export default function SemanticMapper() {
  const [isAdvancedMode, setIsAdvancedMode] = useState(false);

  return (
    <div className="flex flex-col h-full relative">
      <div className="absolute top-4 right-6 z-10 flex items-center space-x-3 bg-white p-2 rounded-lg border border-slate-200 shadow-sm">
        <span className={`text-sm font-medium ${!isAdvancedMode ? 'text-indigo-600' : 'text-slate-500'}`}>Simple Mode</span>
        <button 
          onClick={() => setIsAdvancedMode(!isAdvancedMode)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${isAdvancedMode ? 'bg-amber-500' : 'bg-indigo-600'}`}
        >
          <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${isAdvancedMode ? 'translate-x-6' : 'translate-x-1'}`} />
        </button>
        <span className={`text-sm font-medium ${isAdvancedMode ? 'text-amber-600' : 'text-slate-500'}`}>Advanced Mode</span>
      </div>

      {isAdvancedMode ? (
        <LegacySemanticMapper />
      ) : (
        <AppConcepts />
      )}
    </div>
  );
}
