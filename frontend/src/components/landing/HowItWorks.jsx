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
    <section className="relative py-24 bg-[#FFFFFF] overflow-hidden">
      {/* Background Ambience */}
      <div className="absolute top-0 right-0 w-1/2 h-full bg-sentinel-blue/5 blur-[120px] rounded-full pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <motion.div
           initial={{ opacity: 0, y: 20 }}
           whileInView={{ opacity: 1, y: 0 }}
           viewport={{ once: true }}
           className="mb-16"
        >
          <span className="text-[10px] font-mono text-sentinel-green tracking-[0.2em] uppercase mb-4 block">
            // OPERATIONAL_WORKFLOW
          </span>
          <h2 className="text-4xl md:text-5xl font-bold text-leta-gray-900 font-sans tracking-tight">
            How It <span className="text-leta-gray-500">Works</span>
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
                    ? 'bg-[#F9FAFB] border-sentinel-blue/40 shadow-[0_0_30px_rgba(0,59,89,0.15)]' 
                    : 'bg-transparent border-leta-gray-100 hover:border-leta-gray-200'
                }`}
              >
                {/* Active Indicator Line */}
                <div className={`absolute left-0 top-0 bottom-0 w-1 bg-sentinel-blue transition-all duration-300 ${
                   activeStep === step.id ? 'opacity-100' : 'opacity-0'
                }`} />

                <div className="flex justify-between items-start mb-2">
                  <h3 className={`text-xl font-bold font-sans transition-colors ${
                    activeStep === step.id ? 'text-leta-gray-900' : 'text-leta-gray-500 group-hover:text-leta-gray-300'
                  }`}>
                    {step.title}
                  </h3>
                  {step.status === 'coming_soon' && (
                    <span className="px-2 py-1 rounded-leta bg-leta-gray-50 border border-leta-gray-100 text-[10px] text-leta-gray-500 font-mono uppercase tracking-wider">
                      Coming Soon
                    </span>
                  )}
                </div>
                
                <p className={`text-sm leading-relaxed transition-colors font-light max-w-md ${
                   activeStep === step.id ? 'text-leta-gray-300' : 'text-leta-gray-600'
                }`}>
                  {step.desc}
                </p>
              </motion.div>
            ))}
          </div>

          {/* Right Column: Visual Preview Area */}
          <div className="hidden lg:block relative h-full min-h-[600px]">
             <div className="sticky top-24">
                <div className="relative w-full aspect-square md:aspect-[4/3] bg-[#F9FAFB] rounded-leta border border-leta-gray-200 overflow-hidden flex items-center justify-center p-8">
                   
                   {/* Background Grid */}
                   <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:24px_24px]" />
                   
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
                           <div className="w-24 h-24 mx-auto mb-8 rounded-full bg-sentinel-blue/10 border border-sentinel-blue/30 flex items-center justify-center text-leta-gray-900 shadow-[0_0_50px_rgba(0,59,89,0.2)]">
                              {(() => {
                                 const Icon = steps.find(s => s.id === activeStep)?.icon || MessageSquare;
                                 return <Icon size={48} strokeWidth={1} />;
                              })()}
                           </div>
                           <h4 className="text-2xl font-mono text-leta-gray-900 mb-2 uppercase tracking-widest">
                             {steps.find(s => s.id === activeStep)?.title}
                           </h4>
                           <div className="mt-8 flex justify-center gap-2">
                              <span className="w-2 h-2 rounded-full bg-sentinel-green animate-pulse" />
                              <span className="w-2 h-2 rounded-full bg-sentinel-green/20" />
                              <span className="w-2 h-2 rounded-full bg-sentinel-green/20" />
                           </div>
                           
                           {/* Decorative Code Snippet */}
                           <div className="mt-12 text-left p-4 bg-leta-gray-500 border border-leta-gray-100 rounded-leta font-mono text-[10px] text-leta-gray-600 max-w-xs mx-auto">
                              <p opacity="0.5">// EXECUTING PROTOCOL...</p>
                              <p className="text-leta-gray-900 mt-1">&gt; load_module('{activeStep}')</p>
                              <p className="text-sentinel-green mt-1">&gt; status: active</p>
                           </div>
                        </div>
                     </motion.div>
                   </AnimatePresence>

                   {/* Floating Nodes */}
                   <div className="absolute top-10 right-10 w-3 h-3 border border-leta-gray-300 rounded-full" />
                   <div className="absolute bottom-20 left-10 w-2 h-2 bg-leta-white/10 rounded-full" />
                </div>
             </div>
          </div>

        </div>
      </div>
    </section>
  );
};

export default HowItWorks;
