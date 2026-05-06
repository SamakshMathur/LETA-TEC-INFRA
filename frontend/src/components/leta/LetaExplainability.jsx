import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Info } from 'lucide-react';

const ExplainabilitySection = ({ title, children, isDark }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className={`border rounded-leta overflow-hidden mb-3 shadow-sm hover:shadow-md transition-shadow ${
       isDark ? 'border-leta-gray-200 bg-leta-gray-50' : 'border-leta-gray-200 bg-leta-white'
    }`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full px-4 py-3 flex items-center justify-between text-left transition-colors ${
           isDark ? 'bg-leta-gray-50 hover:bg-leta-white/10' : 'bg-leta-gray-50 hover:bg-leta-gray-100'
        }`}
      >
        <span className={`text-sm font-medium flex items-center gap-2 ${
           isDark ? 'text-leta-gray-200' : 'text-leta-gray-900'
        }`}>
          <Info size={14} className="text-sentinel-green" />
          {title}
        </span>
        <motion.div
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown size={16} className={isDark ? 'text-leta-gray-500' : 'text-leta-gray-600'} />
        </motion.div>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
          >
            <div className={`px-4 py-3 text-sm border-t ${
               isDark ? 'text-leta-gray-600 border-leta-gray-100 bg-transparent' : 'text-leta-gray-600 border-leta-gray-100 bg-leta-white'
            }`}>
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const LetaExplainability = ({ reasoning, isDark = false }) => {
  if (!reasoning) return null;

  return (
    <div className="mt-8">
      <h4 className="text-xs font-bold text-leta-gray-600 uppercase tracking-widest mb-4">Reasoning Engine</h4>
      <ExplainabilitySection title="Query Interpretation" isDark={isDark}>
        {reasoning.interpretation}
      </ExplainabilitySection>
      <ExplainabilitySection title="Statutory Provisions Considered" isDark={isDark}>
         <ul className="list-disc pl-4 space-y-1">
           {reasoning.provisions?.map((prov, i) => (
             <li key={i}>{prov}</li>
           ))}
         </ul>
      </ExplainabilitySection>
      <ExplainabilitySection title="Logical Deduction" isDark={isDark}>
        {reasoning.deduction}
      </ExplainabilitySection>
      <ExplainabilitySection title="Limitations" isDark={isDark}>
        {reasoning.limitations}
      </ExplainabilitySection>
    </div>
  );
};

export default LetaExplainability;
