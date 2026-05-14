import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, FileEdit, FileText, FolderOpen, FileOutput, ArrowRight } from 'lucide-react';

const steps = [
  {
    id: 'query',
    title: "Ask a Legal Query",
    desc: "Use Leta to enter your question in natural language. The AI returns detailed responses backed by verified statutory content with source links.",
    icon: MessageSquare,
    status: 'active'
  },
  {
    id: 'draft',
    title: "Draft a Response",
    desc: "Upload or input a legal notice. The platform validates it, breaks it down into issues, and generates a strategic, structured reply.",
    icon: FileEdit,
    status: 'coming_soon'
  },
  {
    id: 'explore',
    title: "Understand & Explore Documents",
    desc: "Need to review complex files? Upload documents to generate structured insights, ask context-specific questions, and isolate key issues.",
    icon: FileText,
    status: 'active'
  },
  {
    id: 'library',
    title: "Organise with My Library",
    desc: "All your queries, drafts, and uploaded documents are automatically stored and indexed for instant retrieval.",
    icon: FolderOpen,
    status: 'coming_soon'
  },
  {
    id: 'word',
    title: "Finalise in MS Word",
    desc: "Access Sentinel tools directly. Insert answers, draft content, or citations into your document without formatting loss.",
    icon: FileOutput,
    status: 'active'
  }
];

const HowItWorks = () => {
  const [activeStep, setActiveStep] = useState(steps[0].id);

  return (
    <section className="relative py-[140px] overflow-hidden border-t border-white/[0.05]">
      {/* Background Ambience */}
      <div className="absolute top-0 right-0 w-1/2 h-full bg-white/[0.01] blur-[120px] rounded-full pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <motion.div
           initial={{ opacity: 0, y: 20 }}
           whileInView={{ opacity: 1, y: 0 }}
           viewport={{ once: true }}
           className="mb-16"
        >
          <span className="text-[10px] font-mono text-[#67E8F9] tracking-[0.2em] uppercase mb-4 block">
            // OPERATIONAL_WORKFLOW
          </span>
          <h2 className="text-4xl md:text-5xl font-bold font-display text-[#F5F7FA] tracking-tight">
            How It Works
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
          
          {/* Left Column: Interactive List */}
          <div className="flex flex-col gap-6">
            {steps.map((step) => (
              <motion.div
                key={step.id}
                onMouseEnter={() => setActiveStep(step.id)}
                className={`group relative p-6 rounded-leta border transition-all duration-300 cursor-default ${
                  activeStep === step.id 
                    ? 'bg-[#151922] border-[#67E8F9]/18 shadow-2xl' 
                    : 'bg-transparent border-white/[0.03] hover:border-white/[0.07]'
                }`}
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className={`text-xl font-bold font-display transition-colors ${
                    activeStep === step.id ? 'text-[#F5F7FA]' : 'text-white/50 group-hover:text-white/80'
                  }`}>
                    {step.title}
                  </h3>
                  {step.status === 'coming_soon' && (
                    <span className="px-2 py-1 rounded-leta bg-[#07090D] border border-white/[0.06] text-[10px] text-white/40 font-mono uppercase tracking-wider">
                      Coming Soon
                    </span>
                  )}
                </div>
                
                <p className={`text-sm leading-relaxed transition-colors font-light max-w-md ${
                   activeStep === step.id ? 'text-[#A1AAB8]' : 'text-[#A1AAB8]/60'
                }`}>
                  {step.desc}
                </p>
              </motion.div>
            ))}
          </div>

          {/* Right Column: Visual Preview Area */}
          <div className="hidden lg:block relative h-full min-h-[600px]">
             <div className="sticky top-24">
                <div className="relative w-full aspect-square md:aspect-[4/3] bg-[#151922] rounded-leta border border-white/[0.06] overflow-hidden flex items-center justify-center p-8 shadow-2xl">
                   

                   
                   <AnimatePresence mode="wait">
                     <motion.div
                       key={activeStep}
                       initial={{ opacity: 0, scale: 0.95 }}
                       animate={{ opacity: 1, scale: 1 }}
                       exit={{ opacity: 0, scale: 1.05 }}
                       transition={{ duration: 0.4 }}
                       className="relative z-10 w-full h-full flex items-center justify-center"
                     >
                        {/* Abstract Representation of the Feature */}
                        <div className="text-center">
                           <div className="w-24 h-24 mx-auto mb-8 rounded-full bg-white/[0.02] border border-white/[0.06] flex items-center justify-center text-[#67E8F9] shadow-[0_0_50px_rgba(255,255,255,0.01)]">
                              {(() => {
                                 const Icon = steps.find(s => s.id === activeStep)?.icon || MessageSquare;
                                 return <Icon size={48} strokeWidth={1} />;
                              })()}
                           </div>
                           <h4 className="text-xl font-mono text-[#F5F7FA] mb-2 uppercase tracking-widest">
                             {steps.find(s => s.id === activeStep)?.title}
                           </h4>
                           <div className="mt-8 flex justify-center gap-2">
                              <span className="w-2 h-2 rounded-full bg-[#67E8F9] animate-pulse" />
                              <span className="w-2 h-2 rounded-full bg-white/10" />
                              <span className="w-2 h-2 rounded-full bg-white/10" />
                           </div>
                           
                           {/* Decorative Code Snippet */}
                           <div className="mt-12 text-left p-4 bg-[#07090D] border border-white/[0.06] rounded-leta font-mono text-[10px] text-white/50 max-w-xs mx-auto">
                              <p opacity="0.5">// EXECUTING PROTOCOL...</p>
                              <p className="text-[#67E8F9] mt-1">&gt; load_module('{activeStep}')</p>
                              <p className="text-[#A1AAB8] mt-1">&gt; status: active</p>
                           </div>
                        </div>
                     </motion.div>
                   </AnimatePresence>

                   {/* Floating Nodes */}
                   <div className="absolute top-10 right-10 w-3 h-3 border border-white/[0.05] rounded-full" />
                   <div className="absolute bottom-20 left-10 w-2 h-2 bg-white/5 rounded-full" />
                </div>
             </div>
          </div>

        </div>
      </div>
    </section>
  );
};

export default HowItWorks;
