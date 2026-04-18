import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Brain, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import SourceCard from './SourceCard';

const ThinkingSources = ({ sources = [], isCollapsedInitial = false, onDocumentClick }) => {
  const [isCollapsed, setIsCollapsed] = useState(isCollapsedInitial);
  const [status, setStatus] = useState('searching');

  useEffect(() => {
    if (sources.length > 0) {
      const timer = setTimeout(() => setStatus('thinking'), 1500);
      return () => clearTimeout(timer);
    }
  }, [sources]);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="w-full mb-6 animate-in fade-in slide-in-from-top-4 duration-700">
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-5 h-5">
             {status === 'searching' ? (
               <Search size={14} className="text-sentinel-blue animate-pulse" />
             ) : (
               <Brain size={14} className="text-sentinel-green animate-bounce" />
             )}
             <motion.div 
               animate={{ rotate: 360 }}
               transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
               className="absolute inset-0 border border-dashed border-sentinel-green/20 rounded-full"
             />
          </div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-gray-400">
            {status === 'searching' ? 'Retrieving Statutory Evidence...' : 'Synthesizing Legal Position...'}
          </span>
        </div>
        
        <button 
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="text-gray-600 hover:text-gray-300 transition-colors"
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
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {sources.map((src, idx) => (
                <SourceCard 
                  key={`${src.title}-${idx}`} 
                  source={src} 
                  index={idx}
                  onClick={onDocumentClick}
                />
              ))}
            </div>
          )}
        </AnimatePresence>
        
        {!isCollapsed && (
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
