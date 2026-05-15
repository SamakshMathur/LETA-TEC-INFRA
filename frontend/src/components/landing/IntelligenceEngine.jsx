import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Map, Award, BookOpen, FileCheck } from 'lucide-react';

const STEPS = [
  {
    id: 'query',
    icon: Search,
    label: 'User Query',
    tag: 'INPUT_STREAM',
    desc: 'The user enters a complex statutory or transaction-level question (e.g., input tax credit eligibility on custom construction, corporate restructuring notifications).',
    metrics: [
      { name: 'PARSER RATE', value: '1,200 tokens/sec' },
      { name: 'RESOLVER ENCODING', value: 'Vector-Hashed' },
    ],
  },
  {
    id: 'mapping',
    icon: Map,
    label: 'Statute Mapping',
    tag: 'HIERARCHICAL_SEARCH',
    desc: 'The core engine isolates target acts, sub-sections, notifications, and circulars across India’s direct and indirect tax codes.',
    metrics: [
      { name: 'MAPPING ACCURACY', value: '99.2%' },
      { name: 'ACT CODES INDEXED', value: '14 Million+' },
    ],
  },
  {
    id: 'caselaw',
    icon: BookOpen,
    label: 'Case Law Analysis',
    tag: 'CITATION_VERIFICATION',
    desc: 'Synthesizes thousands of high-level judicial decisions from High Courts, Supreme Court, and appellate authorities for current relevance.',
    metrics: [
      { name: 'CROSS REFERENCES', value: '540,000+' },
      { name: 'RETRIEVAL DEPTH', value: 'Cognitive Rank' },
    ],
  },
  {
    id: 'reasoning',
    icon: Award,
    label: 'AI Legal Reasoning',
    tag: 'LOGIC_ENGINE',
    desc: 'Evaluates contradictions between statutory wording, circular exceptions, and judicial outcomes using domain-specific legal reasoning chains.',
    metrics: [
      { name: 'LOGIC CHAINS', value: 'Multi-Path' },
      { name: 'BIAS FILTERING', value: 'Static-Shielded' },
    ],
  },
  {
    id: 'output',
    icon: FileCheck,
    label: 'Structured Output',
    tag: 'COMPLIANCE_RECON',
    desc: 'Generates a secure, highly-cited legal response containing statutory definitions, risk matrices, and actionable recommendations.',
    metrics: [
      { name: 'LATENCY', value: '2.3 seconds' },
      { name: 'CITATION RATE', value: '100% Verified' },
    ],
  },
];

const IntelligenceEngine = () => {
  const [activeStep, setActiveStep] = useState(0);

  // Auto cycle steps slowly to feel organic and computational
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStep(prev => (prev + 1) % STEPS.length);
    }, 4500);
    return () => clearInterval(timer);
  }, []);

  return (
    <section className="py-[80px] relative overflow-hidden bg-[#000000]">


      <div className="max-w-[1600px] mx-auto px-10 lg:px-20 relative z-10">
        
        {/* Section Header */}
        <div className="mb-20 text-center lg:text-left">
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#67E8F9] mb-3">
            Operational Architecture
          </p>
          <h2 className="font-display font-bold text-3xl md:text-5xl text-white uppercase tracking-tight">
            Statutory Intelligence Engine
          </h2>
          <p className="font-body text-[#A1AAB8] text-base md:text-lg max-w-xl mt-4 leading-relaxed font-light">
            Visually tracking LETA's high-fidelity reasoning, contextual cross-referencing, and structural statutory mapping pipelines.
          </p>
        </div>

        {/* The Pipeline Visualizer */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          
          {/* Horizontally Expanding Stepper Container (Left/Main Columns) */}
          <div className="lg:col-span-8 space-y-6">
            <div className="relative flex flex-col md:flex-row justify-between items-center gap-6 p-8 rounded-leta bg-[#10141B] border border-white/[0.04]">
              
              {/* Connected Line Backdrop */}
              <div className="absolute top-[50%] left-10 right-10 h-[1.5px] bg-white/[0.04] hidden md:block pointer-events-none" />
              
              {/* Dynamic filled connector line */}
              <div 
                className="absolute top-[50%] left-10 h-[1.5px] bg-[#67E8F9]/30 hidden md:block transition-all duration-1000 pointer-events-none"
                style={{ width: `${(activeStep / (STEPS.length - 1)) * 82}%` }}
              />

              {STEPS.map((step, index) => {
                const IconComponent = step.icon;
                const isActive = index === activeStep;
                const isPassed = index < activeStep;

                return (
                  <button
                    key={step.id}
                    onClick={() => setActiveStep(index)}
                    className="relative z-10 flex flex-col items-center group focus:outline-none w-full md:w-auto"
                  >
                    {/* Circle Indicator */}
                    <div
                      className={`w-14 h-14 rounded-xl flex items-center justify-center transition-all duration-500 border ${
                        isActive
                          ? 'bg-[#151922] border-[#67E8F9] text-[#67E8F9] shadow-[0_0_20px_rgba(103,232,249,0.15)] scale-110'
                          : isPassed
                          ? 'bg-[#10141B] border-[#67E8F9]/50 text-[#67E8F9]/80'
                          : 'bg-[#000000] border-white/[0.05] text-[#6B7280]'
                      } group-hover:border-[#67E8F9]/80`}
                    >
                      <IconComponent size={20} className="transition-transform duration-300 group-hover:scale-105" />
                    </div>

                    {/* Step label */}
                    <span
                      className={`mt-3 font-mono text-[10px] uppercase tracking-wider font-bold transition-all duration-300 ${
                        isActive ? 'text-white' : 'text-[#6B7280]'
                      }`}
                    >
                      {step.label}
                    </span>

                    {/* Stage code tag */}
                    <span className="font-mono text-[8px] opacity-40 text-[#6B7280] uppercase tracking-widest mt-1">
                      0{index + 1} // {step.tag}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Detailed Stage Content display with Framer Motion transitions */}
            <div className="min-h-[220px]">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeStep}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.4 }}
                  className="p-8 rounded-leta bg-[#151922] border border-white/[0.04] grid grid-cols-1 md:grid-cols-12 gap-8 items-center"
                >
                  <div className="md:col-span-8 space-y-4">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs uppercase text-[#67E8F9] tracking-widest font-bold">
                        STAGE 0{activeStep + 1} // {STEPS[activeStep].tag}
                      </span>
                    </div>
                    <h3 className="font-display font-bold text-2xl text-white">
                      {STEPS[activeStep].label}
                    </h3>
                    <p className="font-body text-[#A1AAB8] text-sm leading-relaxed font-light">
                      {STEPS[activeStep].desc}
                    </p>
                  </div>

                  <div className="md:col-span-4 p-5 rounded-xl bg-[#0F131A] border border-white/[0.03] space-y-4">
                    <p className="font-mono text-[9px] uppercase tracking-wider text-[#6B7280]">
                      System Telemetry
                    </p>
                    <div className="space-y-3">
                      {STEPS[activeStep].metrics.map((m, i) => (
                        <div key={i} className="flex justify-between items-center border-b border-white/[0.03] pb-2 last:border-0 last:pb-0">
                          <span className="font-mono text-[9px] text-[#6B7280] tracking-wide">{m.name}</span>
                          <span className="font-mono text-xs font-bold text-[#67E8F9]">{m.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          {/* Right Column (Aesthetics terminal illustration) */}
          <div className="lg:col-span-4 p-8 rounded-leta bg-[#10141B] border border-white/[0.04] flex flex-col justify-between min-h-[360px]">
            <div className="space-y-4">
              <div className="flex justify-between items-center border-b border-white/[0.03] pb-4">
                <span className="font-mono text-[10px] tracking-widest text-[#6B7280] uppercase font-bold">
                  Active_Trace_Engine
                </span>
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              </div>

              <div className="font-mono text-[11px] text-[#A1AAB8] space-y-3">
                <p>&gt; Ingesting regulatory inputs...</p>
                <p>&gt; Indexing matching statutory roots...</p>
                <div className="pl-4 border-l border-[#67E8F9]/20 space-y-1">
                  <p className="text-[#67E8F9]">[NODE_MAPPING] Match found on § 17(5)</p>
                  <p className="text-[#67E8F9]">[CIRCULAR_SYNC] Sync circular 177/2022</p>
                  <p className="text-[#67E8F9]">[AAR_VERIFICATION] Verified with current rulings</p>
                </div>
                <p>&gt; Processing legal logical chains...</p>
              </div>
            </div>

            <div className="pt-6 border-t border-white/[0.03] flex items-center justify-between">
              <span className="font-mono text-[9px] text-[#6B7280]">LATENCY METRIC</span>
              <span className="font-mono text-sm font-bold text-[#67E8F9]">2.3s AVG</span>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
};

export default IntelligenceEngine;
