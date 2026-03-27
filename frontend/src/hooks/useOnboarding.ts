import { useState, useEffect } from 'react';

export interface OnboardingData {
  clientId?: number;
  apiKey?: string;
  dbConnected?: boolean;
  selectedTables?: string[];
  semanticMappings?: any[];
  relationshipsEnabled?: boolean;
  firstReportCreated?: boolean;
}

export const useOnboarding = () => {
  const [currentStep, setCurrentStep] = useState<number>(() => {
    const saved = localStorage.getItem('amoeba_onboarding_step');
    return saved ? parseInt(saved, 10) : 1;
  });

  const [onboardingData, setOnboardingData] = useState<OnboardingData>(() => {
    const saved = localStorage.getItem('amoeba_onboarding_data');
    return saved ? JSON.parse(saved) : {};
  });

  useEffect(() => {
    localStorage.setItem('amoeba_onboarding_step', currentStep.toString());
  }, [currentStep]);

  useEffect(() => {
    localStorage.setItem('amoeba_onboarding_data', JSON.stringify(onboardingData));
  }, [onboardingData]);

  const nextStep = () => setCurrentStep((prev) => Math.min(prev + 1, 5));
  const prevStep = () => setCurrentStep((prev) => Math.max(prev - 1, 1));
  
  const updateData = (newData: Partial<OnboardingData>) => {
    setOnboardingData((prev) => ({ ...prev, ...newData }));
  };

  const resetOnboarding = () => {
    setCurrentStep(1);
    setOnboardingData({});
    localStorage.removeItem('amoeba_onboarding_step');
    localStorage.removeItem('amoeba_onboarding_data');
  };

  return {
    currentStep,
    setCurrentStep,
    onboardingData,
    updateData,
    nextStep,
    prevStep,
    resetOnboarding
  };
};
