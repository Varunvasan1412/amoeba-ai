import React, { useState, useRef, useEffect } from 'react';
import { Search, ChevronDown } from 'lucide-react';

interface Option {
  value: any;
  label: string;
}

interface SearchableDropdownProps {
  options: Option[];
  value: any;
  onChange: (value: any) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  theme?: 'light' | 'dark';
}

export const SearchableDropdown: React.FC<SearchableDropdownProps> = ({
  options,
  value,
  onChange,
  placeholder = "Select option...",
  className = "",
  disabled = false,
  theme = 'light'
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const filteredOptions = options.filter(opt =>
    String(opt.label || "").toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Reset search term ONLY when the dropdown opens/closes
  useEffect(() => {
    if (isOpen) setSearchTerm("");
  }, [isOpen]);

  // Reset active index when search term changes
  useEffect(() => {
    setActiveIndex(-1);
  }, [searchTerm]);

  // Handle auto-scroll when activeIndex changes
  useEffect(() => {
    if (activeIndex >= 0 && listRef.current) {
      const activeElement = listRef.current.children[activeIndex] as HTMLElement;
      if (activeElement) {
        activeElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [activeIndex]);

  const selectedOption = options.find(opt => opt.value === value);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;

    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter') {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex(prev => (prev < filteredOptions.length - 1 ? prev + 1 : 0));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex(prev => (prev > 0 ? prev - 1 : filteredOptions.length - 1));
        break;
      case 'Enter':
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < filteredOptions.length) {
          onChange(filteredOptions[activeIndex].value);
          setIsOpen(false);
        } else if (filteredOptions.length > 0 && activeIndex === -1) {
            // Pick the first one if none focused
            onChange(filteredOptions[0].value);
            setIsOpen(false);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        break;
      case 'Tab':
        setIsOpen(false);
        break;
    }
  };

  const isDark = theme === 'dark';

  return (
    <div 
      className={`relative ${className}`} 
      ref={containerRef} 
      onKeyDown={handleKeyDown}
      style={{ zIndex: isOpen ? 9999 : 1 }}
    >
      <div
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={`flex items-center justify-between p-2.5 border rounded-xl cursor-pointer transition-all shadow-sm ${
          disabled ? (isDark ? 'bg-slate-800 opacity-50' : 'bg-gray-50 opacity-60') + ' cursor-not-allowed' : 
          isDark ? 'bg-slate-800 border-slate-700 hover:border-slate-500' : 'bg-white border-slate-200 hover:border-indigo-400'
        } ${isOpen ? (isDark ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-indigo-500 ring-2 ring-indigo-100') : ''}`}
      >
        <span className={`text-sm truncate pr-2 ${!selectedOption ? (isDark ? 'text-slate-500' : 'text-gray-400') : (isDark ? 'text-white font-bold' : 'text-slate-700 font-bold')}`}>
          {selectedOption ? selectedOption.label : placeholder}
        </span>

        <ChevronDown size={14} className={`${isDark ? 'text-slate-500' : 'text-slate-400'} shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </div>

      {isOpen && (
        <div className={`absolute left-0 right-0 z-[9999] mt-2 border-2 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.2)] overflow-hidden min-w-[200px] ${
            isDark ? 'bg-slate-900 border-slate-700' : 'bg-white border-slate-200'
        }`}>
          <div className={`p-3 border-b-2 ${isDark ? 'border-slate-800 bg-slate-800' : 'border-slate-100 bg-slate-50'}`}>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
              <input
                ref={inputRef}
                autoFocus
                type="text"
                placeholder="Search..."
                className={`w-full pl-10 pr-3 py-2.5 rounded-xl text-sm outline-none transition-all border-2 ${
                    isDark ? 'bg-slate-900 border-slate-700 text-white focus:border-blue-500' : 'bg-white border-slate-200 text-slate-700 focus:border-indigo-500'
                }`}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onClick={(e) => e.stopPropagation()}
              />
            </div>
          </div>
          
          <div 
            ref={listRef}
            className={`max-h-72 overflow-y-auto overflow-x-hidden custom-scrollbar ${isDark ? 'bg-slate-900' : 'bg-white'}`}
          >
            {filteredOptions.length > 0 ? (
              filteredOptions.map((opt, idx) => (
                <div
                  key={`${String(opt.value)}-${idx}`}
                  className={`px-5 py-3 text-sm cursor-pointer transition-all flex items-center justify-between border-b last:border-0 ${
                    isDark ? 'border-slate-800/50' : 'border-slate-50'
                  } ${
                    idx === activeIndex
                        ? (isDark ? 'bg-blue-600/40 text-white ring-2 ring-blue-500 ring-inset' : 'bg-indigo-50/50 text-indigo-900 ring-2 ring-indigo-400 ring-inset')
                        : opt.value === value 
                            ? (isDark ? 'bg-blue-600/20 text-blue-400 font-black' : 'bg-indigo-50 text-indigo-700 font-black') 
                            : (isDark ? 'text-slate-300 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-50')
                  }`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onChange(opt.value);
                    setIsOpen(false);
                  }}
                  onMouseEnter={() => setActiveIndex(idx)}
                >
                  <span className="truncate pr-4">{opt.label}</span>
                  {opt.value === value && <Check size={16} className={isDark ? "text-blue-400" : "text-indigo-600"} />}
                </div>
              ))
            ) : (
              <div className={`px-6 py-12 text-center flex flex-col items-center justify-center gap-2 ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                <Search size={24} className="opacity-20 mb-1" />
                <span className="text-xs font-bold uppercase tracking-widest">
                    {options.length === 0 ? "Empty List" : "No Match Found"}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const Check = ({ size, className }: { size: number, className?: string }) => (
    <svg 
        width={size} 
        height={size} 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="currentColor" 
        strokeWidth="3" 
        strokeLinecap="round" 
        strokeLinejoin="round" 
        className={className}
    >
        <polyline points="20 6 9 17 4 12" />
    </svg>
);
