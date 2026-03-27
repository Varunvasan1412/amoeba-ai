import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useOnboarding } from '../../hooks/useOnboarding';
import { DatabaseStep } from '../../components/onboarding/DatabaseStep';
import { TableDiscoveryStep } from '../../components/onboarding/TableDiscoveryStep';
import { SemanticSuggestionStep } from '../../components/onboarding/SemanticSuggestionStep';
import { RelationshipStep } from '../../components/onboarding/RelationshipStep';
import { FirstReportStep } from '../../components/onboarding/FirstReportStep';

const OnboardingWizard: React.FC = () => {
  const navigate = useNavigate();
  const { currentStep, nextStep, prevStep, onboardingData, updateData, resetOnboarding } = useOnboarding();

  const steps = [
    { title: 'Connect Data', description: 'Connect your ERP' },
    { title: 'Select Data', description: 'Choose source tables' },
    { title: 'Name Data', description: 'Business terminology' },
    { title: 'Connections', description: 'Link data together' },
    { title: 'Launch', description: 'Create first view' }
  ];

  const handleStepComplete = (data: any) => {
    updateData(data);
    nextStep();
  };

  const handleFinish = () => {
    resetOnboarding();
    navigate('/admin');
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      {/* Header */}
      <div className="mb-10 text-center">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Amoeba AI Setup Wizard</h1>
        <p className="text-gray-600">Let's get your business data ready for intelligent analysis in a few simple steps.</p>
      </div>

      {/* Progress Tracker */}
      <div className="mb-12">
        <div className="flex justify-between relative">
          {/* Progress Line */}
          <div className="absolute top-5 left-0 w-full h-0.5 bg-gray-200 -z-10"></div>
          <div 
            className="absolute top-5 left-0 h-0.5 bg-blue-600 transition-all duration-500 -z-10"
            style={{ width: `${((currentStep - 1) / (steps.length - 1)) * 100}%` }}
          ></div>

          {steps.map((step, idx) => {
            const stepNum = idx + 1;
            const isCompleted = currentStep > stepNum;
            const isActive = currentStep === stepNum;

            return (
              <div key={idx} className="flex flex-col items-center flex-1">
                <div 
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-bold border-2 transition-colors duration-300 ${
                    isCompleted ? 'bg-blue-600 border-blue-600 text-white' : 
                    isActive ? 'bg-white border-blue-600 text-blue-600 shadow-md' : 
                    'bg-white border-gray-300 text-gray-400'
                  }`}
                >
                  {isCompleted ? '✓' : stepNum}
                </div>
                <div className="mt-3 text-center">
                  <div className={`text-xs font-bold uppercase ${isActive ? 'text-blue-600' : 'text-gray-500'}`}>
                    {step.title}
                  </div>
                  <div className="text-[10px] text-gray-400 hidden md:block">
                    {step.description}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Wizard Card */}
      <div className="bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden min-h-[500px] flex flex-col">
        <div className="p-8 flex-1">
          {currentStep === 1 && (
            <DatabaseStep 
              onSuccess={(clientId, apiKey) => handleStepComplete({ clientId, apiKey, dbConnected: true })} 
            />
          )}
          {currentStep === 2 && (
            <TableDiscoveryStep 
              onSuccess={(tables) => handleStepComplete({ selectedTables: tables })} 
            />
          )}
          {currentStep === 3 && (
            <SemanticSuggestionStep 
              selectedTables={onboardingData.selectedTables || []} 
              initialMappings={onboardingData.semanticMappings}
              onSuccess={(mappings) => handleStepComplete({ semanticMappings: mappings })} 
            />
          )}
          {currentStep === 4 && (
            <RelationshipStep 
              onSuccess={() => handleStepComplete({ relationshipsEnabled: true })} 
            />
          )}
          {currentStep === 5 && (
            <FirstReportStep 
              semanticMappings={onboardingData.semanticMappings || []} 
              onSuccess={() => handleFinish()} 
            />
          )}
        </div>

        {/* Navigation Buttons (Bottom) */}
        <div className="bg-gray-50 p-6 flex justify-between items-center border-t">
          {currentStep > 1 ? (
            <button
              onClick={prevStep}
              className="text-gray-600 hover:text-gray-900 font-medium px-4 py-2"
            >
              ← Back
            </button>
          ) : (
            <div></div>
          )}
          <div className="text-gray-400 text-sm font-medium">
            Step {currentStep} of 5
          </div>
          <button
             onClick={handleFinish}
             className="text-blue-600 hover:text-blue-800 text-sm font-medium"
          >
            Skip Wizard
          </button>
        </div>
      </div>
    </div>
  );
};

export default OnboardingWizard;
