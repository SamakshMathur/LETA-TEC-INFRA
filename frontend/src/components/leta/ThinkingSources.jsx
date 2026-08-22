import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import SourceCard from './SourceCard';

const ThinkingSources = ({ sources = [], isCollapsedInitial = false, onDocumentClick, status: externalStatus, isStreaming = false, completedSteps = [] }) => {
  const [isCollapsed, setIsCollapsed] = useState(isCollapsedInitial);

  const isSearching = !sources || sources.length === 0;
  const isDone = !isStreaming && !isSearching;

  if (isSearching && !externalStatus && !isStreaming) return null;

  return (
    <div className="w-full mb-6">
      {/* Completed steps trail */}
      {completedSteps.length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 mb-3 px-1">
          {completedSteps.map((step, i) => (
            <span key={i} className="flex items-center gap-1 text-[9px] font-mono uppercase tracking-widest" style={{ color: 'rgba(34,197,94,0.55)' }}>
              <CheckCircle2 size={9} style={{ color: 'rgba(34,197,94,0.55)' }} />
              {step}
            </span>
          ))}
        </div>
      )}
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-5 h-5">
            {isDone ? (
              <CheckCircle2 size={13} style={{ color: '#22C55E' }} />
            ) : isSearching ? (
              <Search size={13} className="animate-pulse" style={{ color: '#67E8F9' }} />
            ) : (
              <CheckCircle2 size={13} style={{ color: '#22C55E' }} />
            )}
            {isStreaming && (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
                className="absolute inset-0 border border-dashed rounded-full"
                style={{ borderColor: 'rgba(103,232,249,0.25)' }}
              />
            )}
          </div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em]" style={{ color: isDone ? 'rgba(34,197,94,0.7)' : '#94A3B8' }}>
            {isDone ? `${sources.length} sources retrieved` : (externalStatus || 'Retrieving Statutory Evidence...')}
          </span>
        </div>

        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="transition-colors"
          style={{ color: '#475569' }}
          onMouseEnter={e => { e.currentTarget.style.color = '#CBD5E1'; }}
          onMouseLeave={e => { e.currentTarget.style.color = '#475569'; }}
        >
          {isCollapsed ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
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
              {isSearching
                ? [1, 2, 3, 4].map(i => (
                    <div
                      key={`sk-${i}`}
                      className="flex flex-col p-3 rounded-xl"
                      style={{ background: 'rgba(103,232,249,0.04)', border: '1px solid rgba(103,232,249,0.1)' }}
                    >
                      <div className="w-7 h-7 rounded-lg mb-2 animate-pulse" style={{ background: 'rgba(103,232,249,0.1)' }} />
                      <div className="w-full h-3 rounded mb-2 animate-pulse" style={{ background: 'rgba(103,232,249,0.08)' }} />
                      <div className="w-2/3 h-2 rounded animate-pulse" style={{ background: 'rgba(103,232,249,0.06)' }} />
                    </div>
                  ))
                : sources.map((src, idx) => (
                    <SourceCard key={`${src.title}-${idx}`} source={src} index={idx} onClick={onDocumentClick} />
                  ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {!isCollapsed && !isSearching && (
        <div className="mt-3 flex items-center gap-2 px-1">
          <CheckCircle2 size={11} style={{ color: '#22C55E' }} />
          <span className="text-[9px] font-mono uppercase tracking-widest" style={{ color: 'rgba(34,197,94,0.5)' }}>
            {sources.length} SOURCES VERIFIED AND ANCHORED
          </span>
        </div>
      )}
    </div>
  );
};

export default ThinkingSources;
