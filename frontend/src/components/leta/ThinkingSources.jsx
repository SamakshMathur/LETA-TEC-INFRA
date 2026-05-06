import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Brain, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import SourceCard from './SourceCard';

const ThinkingSources = ({ sources = [], isCollapsedInitial = false, onDocumentClick, status: externalStatus }) => {
  const [isCollapsed, setIsCollapsed] = useState(isCollapsedInitial);
  const [internalStatus, setInternalStatus] = useState('Initializing Statutory Analyzer...');

  const status = externalStatus || internalStatus;

  const isSearching = !sources || sources.length === 0;

  if (isSearching && !status) return null;

  return (
    <div className="w-full mb-6 animate-in fade-in slide-in-from-top-4 duration-700">
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-5 h-5">
             {isSearching ? (
               <Search size={14} className="text-leta-gray-900 animate-pulse" />
             ) : (
               <div className="relative">
                 <CheckCircle2 size={14} className="text-sentinel-green" />
                 <motion.div 
                    initial={{ scale: 1 }}
                    animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    className="absolute inset-0 bg-sentinel-green rounded-full"
                 />
               </div>
             )}
             <motion.div 
               animate={{ rotate: 360 }}
               transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
               className="absolute inset-0 border border-dashed border-sentinel-green/20 rounded-full"
             />
          </div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-leta-gray-600">
            {status || (isSearching ? 'Retrieving Statutory Evidence...' : 'Synthesizing Legal Position...')}
          </span>
        </div>
        
        <button 
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="text-leta-gray-600 hover:text-leta-gray-300 transition-colors"
        >
          {isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </button>
      </div>

      <AnimatePresence>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {isSearching ? (
                // SKELETON CARDS while searching
                [1, 2, 3, 4].map((i) => (
                  <div key={`skeleton-${i}`} className="flex flex-col p-3 bg-[#0A1622]/40 border border-leta-gray-100 rounded-leta">
                    <div className="flex items-start justify-between mb-2">
                       <div className="w-7 h-7 bg-leta-gray-50 rounded-leta animate-pulse" />
                    </div>
                    <div className="w-full h-3 bg-leta-gray-50 rounded-leta mb-2 animate-pulse" />
                    <div className="w-2/3 h-2 bg-leta-gray-50 rounded-leta animate-pulse" />
                  </div>
                ))
              ) : (
                sources.map((src, idx) => (
                  <SourceCard 
                    key={`${src.title}-${idx}`} 
                    source={src} 
                    index={idx}
                    onClick={onDocumentClick}
                  />
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
        
        {!isCollapsed && !isSearching && (
          <div className="mt-4 flex items-center gap-2 px-1">
            <CheckCircle2 size={12} className="text-sentinel-green" />
            <span className="text-[9px] font-mono text-sentinel-green/60 uppercase tracking-widest">
                {sources.length} SOURCES VERIFIED AND ANCHORED
            </span>
          </div>
        )}
      </div>
  );
};

export default ThinkingSources;
