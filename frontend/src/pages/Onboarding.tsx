import React, { useState } from 'react';

// Scaffold for Phase 3 Amoeba Onboarding Experience

export const Onboarding: React.FC = () => {
    const [step, setStep] = useState<number>(1);
    const [mode, setMode] = useState<'simple' | 'advanced'>('simple');
    const [proposals, setProposals] = useState<any[]>([]);

    const renderStep1Connect = () => (
        <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Step 1: Connect Your Application</h2>
            <div className="flex gap-4 mb-6">
                <button 
                    className={`px-4 py-2 rounded ${mode === 'simple' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                    onClick={() => setMode('simple')}
                >Simple Mode</button>
                <button 
                    className={`px-4 py-2 rounded ${mode === 'advanced' ? 'bg-blue-600 text-white' : 'bg-gray-200'}`}
                    onClick={() => setMode('advanced')}
                >Advanced Mode</button>
            </div>
            
            {mode === 'simple' ? (
                <div>
                    <p className="mb-4">Select an application connector to safely connect your system without database credentials.</p>
                    <button className="bg-gray-100 p-4 border rounded shadow w-full text-left font-bold">Connect via API Agent</button>
                </div>
            ) : (
                <div>
                    <p className="mb-4 text-red-600">Advanced Mode: Enter raw database credentials.</p>
                    <input type="text" placeholder="Database URL" className="w-full border p-2 rounded mb-4" />
                </div>
            )}
            
            <button className="mt-6 bg-green-600 text-white px-6 py-2 rounded" onClick={() => setStep(2)}>Next: Discover Concepts</button>
        </div>
    );

    const renderStep2Discover = () => (
        <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Step 2: Amoeba is Learning</h2>
            <div className="animate-pulse flex space-x-4">
                <div className="flex-1 space-y-4 py-1">
                    <div className="h-4 bg-gray-400 rounded w-3/4"></div>
                    <div className="space-y-2">
                        <div className="h-4 bg-gray-400 rounded"></div>
                        <div className="h-4 bg-gray-400 rounded w-5/6"></div>
                    </div>
                </div>
            </div>
            <p className="mt-4 text-gray-500">Discovering tables, filtering metadata, generating business concepts...</p>
            <button className="mt-6 bg-blue-600 text-white px-6 py-2 rounded" onClick={() => setStep(3)}>Simulate Completion</button>
        </div>
    );

    const renderStep3Approve = () => (
        <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Step 3: Discover Business Concepts</h2>
            <p className="mb-4">Amoeba discovered these concepts. Check the ones you want to expose.</p>
            <div className="space-y-2">
                <label className="flex items-center gap-2"><input type="checkbox" defaultChecked /> Quotation {mode === 'advanced' && <span className="text-gray-400 text-sm">(sales_quotation_tbl)</span>}</label>
                <label className="flex items-center gap-2"><input type="checkbox" defaultChecked /> Customer {mode === 'advanced' && <span className="text-gray-400 text-sm">(crm_customer)</span>}</label>
            </div>
            <button className="mt-6 bg-green-600 text-white px-6 py-2 rounded" onClick={() => setStep(4)}>Next: Configure Concept</button>
        </div>
    );

    const renderStep4Teach = () => (
        <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Step 4: Teach Concept (Quotation)</h2>
            <div className="bg-gray-50 border p-4 rounded mb-6">
                <p className="font-bold">Amoeba thinks:</p>
                <p className="mb-4">Quote → Quotation {mode === 'advanced' && <span className="text-gray-400 text-sm">{'{ "table": "sales_quotation_tbl" }'}</span>}</p>
                
                <p className="font-bold">Alternative terms (Synonyms):</p>
                <div className="flex gap-2 mb-4">
                    <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">Quote</span>
                    <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">Sales Quote</span>
                </div>
                
                <p className="font-bold">Relationship:</p>
                <p className="mb-4 italic">Quotation belongs to Customer</p>
                
                <div className="flex gap-4 mt-4">
                    <button className="bg-blue-600 text-white px-4 py-2 rounded">Accept</button>
                    <button className="bg-gray-200 px-4 py-2 rounded">Edit</button>
                </div>
            </div>
            
            <button className="mt-6 bg-green-600 text-white px-6 py-2 rounded" onClick={() => setStep(5)}>Next: Test in Sandbox</button>
        </div>
    );

    const renderStep5Sandbox = () => (
        <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Step 5: Sandbox Testing</h2>
            <div className="border rounded p-4 h-64 overflow-y-auto bg-gray-50 mb-4">
                <div className="bg-blue-100 p-2 rounded w-1/2 mb-2">User: Show me all Quotes.</div>
                <div className="bg-white border p-2 rounded w-1/2 ml-auto mb-2">
                    <p className="font-bold text-sm">What Amoeba Understood:</p>
                    <p className="text-sm">Intent: Read</p>
                    <p className="text-sm">Target: Quotation</p>
                    {mode === 'advanced' && <pre className="text-xs bg-gray-100 p-2 mt-2">SELECT * FROM sales_quotation_tbl</pre>}
                </div>
            </div>
            <button className="mt-6 bg-green-600 text-white px-6 py-2 rounded" onClick={() => setStep(6)}>Next: Activation</button>
        </div>
    );

    const renderStep6Activation = () => (
        <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Step 6: Activation</h2>
            <div className="mb-6 p-4 border rounded bg-gray-50">
                <label className="flex items-center gap-2 font-bold"><input type="checkbox" /> Enable Assistant Mode (Read-Only)</label>
                <p className="text-sm text-gray-600 ml-6">Allow users to ask questions about Quotations and Customers.</p>
            </div>
            <div className="mb-6 p-4 border rounded bg-red-50 border-red-200">
                <label className="flex items-center gap-2 font-bold text-red-700"><input type="checkbox" /> Enable Operations Mode (Create/Update/Delete)</label>
                <p className="text-sm text-gray-600 ml-6">Explicitly allow Amoeba to modify records.</p>
            </div>
            
            <button className="mt-6 bg-blue-600 text-white px-6 py-2 rounded">Complete Onboarding</button>
        </div>
    );

    return (
        <div className="max-w-4xl mx-auto my-10 bg-white rounded shadow min-h-[500px]">
            {step === 1 && renderStep1Connect()}
            {step === 2 && renderStep2Discover()}
            {step === 3 && renderStep3Approve()}
            {step === 4 && renderStep4Teach()}
            {step === 5 && renderStep5Sandbox()}
            {step === 6 && renderStep6Activation()}
        </div>
    );
};
