import { useState } from 'react';
import { HelpCircle, ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react';

interface TutorialBannerProps {
  title: string;
  description: string;
  bugFixes: string[];
}

export function TutorialBanner({ title, description, bugFixes }: TutorialBannerProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 mb-6 shadow-sm">
      <div 
        className="flex justify-between items-center cursor-pointer"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-3">
          <HelpCircle className="text-indigo-600 h-6 w-6" />
          <h3 className="font-semibold text-indigo-900 text-lg">Tutorial: {title}</h3>
        </div>
        <button className="text-indigo-500 hover:text-indigo-700 focus:outline-none">
          {isOpen ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
        </button>
      </div>

      {isOpen && (
        <div className="mt-4 text-indigo-800 border-t border-indigo-200 pt-4">
          <p className="mb-4 text-sm leading-relaxed font-medium">
            {description}
          </p>
          <div>
            <h4 className="font-bold text-sm mb-2 text-indigo-900 flex items-center gap-2">
              What bug fixes this menu offers:
            </h4>
            <ul className="space-y-2">
              {bugFixes.map((fix, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-indigo-500 mt-0.5 flex-shrink-0" />
                  <span>{fix}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
