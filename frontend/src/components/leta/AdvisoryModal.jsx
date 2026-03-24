import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, FileText, PenTool, Download, ChevronLeft } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { advisoryService } from '../../services/advisoryService';
import { NeuralBrainLoader } from '../effects';

// Internal Error Boundary for the Modal
class AdvisoryErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("AdvisoryModal Crash:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center text-red-400 border border-red-500/20 bg-red-500/10 rounded-lg m-4">
          <h3 className="text-xl font-bold mb-2 font-mono uppercase">System Error</h3>
          <p className="font-mono text-sm mb-4">
            The advisory generation interface encountered a display error.
            <br/>
            {this.state.error && this.state.error.toString()}
          </p>
          <button 
            onClick={() => this.setState({ hasError: false })}
            className="px-6 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 rounded text-sm uppercase font-mono transition-colors"
          >
            [ HOST_RECOVERY ]
          </button>
        </div>
      );
    }

    return this.props.children; 
  }
}

const AdvisoryModal = ({ isOpen, onClose, initialQuery, initialContext }) => {
  const [step, setStep] = useState('selection'); // selection, manual_input, generating, result
  const [manualFacts, setManualFacts] = useState('');
  const [advisoryContent, setAdvisoryContent] = useState('');
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleGenerate = async (useManual = false) => {
    setStep('generating');
    setError(null);
    try {
      const queryToUse = useManual ? manualFacts : (initialQuery || "Context-based Advisory Generation");
      // If manual, we don't pass initialContext so backend fetches fresh law
      const contextToUse = useManual ? null : initialContext; 

      const data = await advisoryService.generateAdvisory(queryToUse, contextToUse, useManual);
      
      // Safety check for content
      if (!data || !data.advisory) {
         throw new Error("Received empty advisory from system.");
      }

      setAdvisoryContent(data.advisory);
      setStep('result');
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to generate advisory.');
      setStep('selection'); 
    }
  };

  const handleDownload = () => {
    // Simple text download for now
    const element = document.createElement('a');
    const file = new Blob([advisoryContent], {type: 'text/markdown'});
    element.href = URL.createObjectURL(file);
    element.download = "Legal_Advisory_Opinion.md";
    document.body.appendChild(element);
    element.click();
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div 
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="absolute inset-0 bg-black/90 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Modal Container */}
        <motion.div 
          initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
          className="relative w-full max-w-4xl bg-[#0F172A] border border-sentinel-green/30 shadow-2xl rounded-none overflow-hidden flex flex-col max-h-[90vh]"
        >
          {/* Header */}
          <div className="p-6 border-b border-white/10 flex justify-between items-center bg-[#020202]">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-sentinel-green/20 text-sentinel-green rounded-sm">
                <FileText size={20} />
              </div>
              <div>
                 <h2 className="text-xl font-bold text-white font-mono uppercase tracking-wider">Legal Advisory Generator</h2>
                 <p className="text-xs text-gray-500 font-mono">
                   // MODE: {step === 'result' ? 'REPORT_VIEW' : 'CONFIGURATION'}
                 </p>
              </div>
            </div>
            <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
              <X size={24} />
            </button>
          </div>

          {/* Content Area */}
          <AdvisoryErrorBoundary>
            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
              
              {/* STEP 1: SELECTION */}
              {step === 'selection' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 h-full items-center">
                  
                  {/* Option A: Current Context */}
                  <div 
                    onClick={() => handleGenerate(false)}
                    className="group cursor-pointer p-8 border border-white/10 bg-[#050A10] hover:border-sentinel-green hover:bg-sentinel-green/5 transition-all text-center flex flex-col items-center gap-4"
                  >
                    <div className="p-4 rounded-full bg-sentinel-green/10 text-sentinel-green group-hover:scale-110 transition-transform">
                      <FileText size={32} />
                    </div>
                    <h3 className="text-lg font-bold text-white uppercase tracking-wide">On Current Query</h3>
                    <p className="text-sm text-gray-400">
                      Generate a formal opinion based on the question you just asked and the retrieved documents.
                    </p>
                    <div className="mt-4 px-4 py-1 border border-sentinel-green/30 text-sentinel-green text-xs font-mono uppercase">
                      [ EXECUTE_AUTO ]
                    </div>
                  </div>

                  {/* Option B: Manual Input */}
                  <div 
                    onClick={() => setStep('manual_input')}
                    className="group cursor-pointer p-8 border border-white/10 bg-[#050A10] hover:border-sentinel-blue hover:bg-sentinel-blue/5 transition-all text-center flex flex-col items-center gap-4"
                  >
                     <div className="p-4 rounded-full bg-sentinel-blue/10 text-sentinel-blue group-hover:scale-110 transition-transform">
                      <PenTool size={32} />
                    </div>
                    <h3 className="text-lg font-bold text-white uppercase tracking-wide">Manual Case Study</h3>
                    <p className="text-sm text-gray-400">
                      Input a specific set of facts or a new scenario. The system will find relevant laws for you.
                    </p>
                    <div className="mt-4 px-4 py-1 border border-sentinel-blue/30 text-sentinel-blue text-xs font-mono uppercase">
                      [ CONFIGURE_MANUAL ]
                    </div>
                  </div>

                  {error && (
                    <div className="col-span-2 text-red-400 text-center font-mono text-sm mt-4 p-2 border border-red-500/20 bg-red-500/10">
                      Error: {error}
                    </div>
                  )}
                </div>
              )}

              {/* STEP 2: MANUAL INPUT */}
              {step === 'manual_input' && (
                <div className="max-w-2xl mx-auto">
                   <button onClick={() => setStep('selection')} className="flex items-center gap-2 text-gray-500 hover:text-white mb-6 text-xs font-mono uppercase">
                     <ChevronLeft size={14} /> Back
                   </button>
                   <h3 className="text-lg font-bold text-white mb-4 font-mono uppercase">Enter Case Facts</h3>
                   <textarea
                     value={manualFacts}
                     onChange={(e) => setManualFacts(e.target.value)}
                     className="w-full h-64 bg-[#020202] border border-white/20 p-4 text-gray-300 font-mono text-sm focus:border-sentinel-blue outline-none resize-none"
                     placeholder="Describe the facts of the case, the transaction details, and the specific doubt..."
                   />
                   <button
                     onClick={() => handleGenerate(true)}
                     disabled={!manualFacts.trim()}
                     className="mt-6 w-full py-3 bg-sentinel-blue hover:bg-sentinel-blue/80 text-black font-bold font-mono uppercase tracking-widest disabled:opacity-50 disabled:cursor-not-allowed"
                   >
                     [ GENERATE_OPINION ]
                   </button>
                </div>
              )}

              {/* STEP 3: GENERATING */}
              {step === 'generating' && (
                 <div className="flex flex-col items-center justify-center h-96 w-full text-center bg-black/50 border border-white/5 rounded-lg overflow-hidden relative">
                    <NeuralBrainLoader />
                 </div>
              )}

              {/* STEP 4: RESULT */}
              {step === 'result' && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div className="bg-white text-black p-10 font-serif shadow-xl mb-8 min-h-[600px] border-t-8 border-sentinel-green">
                     {/* We render markdown here nicely */}
                     <div className="prose prose-sm max-w-none prose-headings:font-bold prose-headings:uppercase prose-p:leading-relaxed prose-li:my-0">
                       <ReactMarkdown remarkPlugins={[remarkGfm]}>
                         {advisoryContent}
                       </ReactMarkdown>
                     </div>
                  </div>
                </div>
              )}

            </div>
          </AdvisoryErrorBoundary>

          {/* Footer (Only for Result) */}
          {step === 'result' && (
            <div className="p-4 border-t border-white/10 bg-[#020202] flex justify-between items-center">
               <button onClick={() => setStep('selection')} className="text-gray-500 hover:text-white text-xs font-mono uppercase">
                 &lt; New Advisory
               </button>
               <button 
                 onClick={handleDownload}
                 className="flex items-center gap-2 px-6 py-2 bg-sentinel-green text-black font-bold font-mono uppercase text-xs tracking-wider hover:bg-white transition-colors"
               >
                 <Download size={16} /> Download Report
               </button>
            </div>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default AdvisoryModal;
