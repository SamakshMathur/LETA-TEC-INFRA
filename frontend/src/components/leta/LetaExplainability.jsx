import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Info } from 'lucide-react';

const ExplainabilitySection = ({ title, children, isDark }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className={`border rounded-lg overflow-hidden mb-3 shadow-sm hover:shadow-md transition-shadow ${
       isDark ? 'border-white/10 bg-white/5' : 'border-gray-200 bg-white'
    }`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full px-4 py-3 flex items-center justify-between text-left transition-colors ${
           isDark ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-50 hover:bg-gray-100'
        }`}
      >
        <span className={`text-sm font-medium flex items-center gap-2 ${
           isDark ? 'text-gray-200' : 'text-sentinel-blue'
        }`}>
          <Info size={14} className="text-sentinel-green" />
          {title}
        </span>
        <motion.div
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown size={16} className={isDark ? 'text-gray-500' : 'text-gray-400'} />
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
               isDark ? 'text-gray-400 border-white/5 bg-transparent' : 'text-gray-600 border-gray-100 bg-white'
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
      <h4 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-4">Reasoning Engine</h4>
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
