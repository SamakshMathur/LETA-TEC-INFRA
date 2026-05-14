import React, { useState } from 'react';
import ReactDOM from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, FileText, PenTool, Download, ChevronLeft } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { advisoryService } from '../../services/advisoryService';
import { NeuralBrainLoader } from '../effects';

class AdvisoryErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  componentDidCatch(error, errorInfo) { console.error('AdvisoryModal Crash:', error, errorInfo); }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center m-4 rounded-2xl"
          style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#EF4444' }}>
          <h3 className="text-xl font-bold mb-2 font-mono uppercase">System Error</h3>
          <p className="font-mono text-sm mb-4" style={{ color: '#94A3B8' }}>
            The advisory generation interface encountered a display error.<br />
            {this.state.error && this.state.error.toString()}
          </p>
          <button
            onClick={() => this.setState({ hasError: false })}
            className="px-6 py-2 rounded-xl text-sm uppercase font-mono font-bold transition-colors"
            style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', color: '#EF4444' }}
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
  const [step, setStep] = useState('selection');
  const [manualFacts, setManualFacts] = useState('');
  const [advisoryContent, setAdvisoryContent] = useState('');
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleGenerate = async (useManual = false) => {
    setStep('generating');
    setError(null);
    try {
      const queryToUse = useManual ? manualFacts : (initialQuery || 'Context-based Advisory Generation');
      const contextToUse = useManual ? null : initialContext;
      const data = await advisoryService.generateAdvisory(queryToUse, contextToUse, useManual);
      if (!data || !data.advisory) throw new Error('Received empty advisory from system.');
      setAdvisoryContent(data.advisory);
      setStep('result');
    } catch (err) {
      console.error(err);
      setError(err.message || 'Failed to generate advisory.');
      setStep('selection');
    }
  };

  const handleDownload = () => {
    const element = document.createElement('a');
    const file = new Blob([advisoryContent], { type: 'text/markdown' });
    element.href = URL.createObjectURL(file);
    element.download = 'Legal_Advisory_Opinion.md';
    document.body.appendChild(element);
    element.click();
  };

  return ReactDOM.createPortal(
    <AnimatePresence>
      <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="absolute inset-0 backdrop-blur-sm"
          style={{ background: 'rgba(6,8,22,0.92)' }}
          onClick={onClose}
        />

        {/* Modal */}
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
          className="relative w-full max-w-4xl rounded-2xl overflow-hidden flex flex-col max-h-[90vh]"
          style={{
            background: 'rgba(11,16,32,0.98)',
            border: '1px solid rgba(103,232,249,0.25)',
            boxShadow: '0 40px 80px rgba(0,0,0,0.8), 0 0 60px rgba(103,232,249,0.1)',
            backdropFilter: 'blur(40px)',
          }}
        >
          {/* Top accent */}
          <div className="h-[2px] w-full" style={{ background: 'linear-gradient(90deg, #67E8F9, #0E7490, transparent)' }} />

          {/* Header */}
          <div
            className="px-6 py-5 flex justify-between items-center"
            style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl" style={{ background: 'rgba(103,232,249,0.12)', color: '#67E8F9' }}>
                <FileText size={18} />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white font-mono uppercase tracking-wider">
                  Legal Advisory Generator
                </h2>
                <p className="text-[10px] font-mono" style={{ color: '#475569' }}>
                  // MODE: {step === 'result' ? 'REPORT_VIEW' : 'CONFIGURATION'}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg transition-colors"
              style={{ color: '#475569' }}
              onMouseEnter={e => { e.currentTarget.style.color = '#CBD5E1'; e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = '#475569'; e.currentTarget.style.background = 'transparent'; }}
            >
              <X size={20} />
            </button>
          </div>

          {/* Content */}
          <AdvisoryErrorBoundary>
            <div className="flex-1 overflow-y-auto p-8">

              {/* STEP 1: Selection */}
              {step === 'selection' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
                  {/* Option A */}
                  <div
                    onClick={() => handleGenerate(false)}
                    className="cursor-pointer p-8 rounded-2xl flex flex-col items-center gap-4 text-center transition-all duration-200 group"
                    style={{ border: '1px solid rgba(103,232,249,0.2)', background: 'rgba(103,232,249,0.04)' }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = 'rgba(103,232,249,0.5)';
                      e.currentTarget.style.background = 'rgba(103,232,249,0.08)';
                      e.currentTarget.style.boxShadow = '0 0 30px rgba(103,232,249,0.15)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'rgba(103,232,249,0.2)';
                      e.currentTarget.style.background = 'rgba(103,232,249,0.04)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    <div className="p-4 rounded-full group-hover:scale-110 transition-transform"
                      style={{ background: 'rgba(103,232,249,0.12)', color: '#67E8F9' }}>
                      <FileText size={28} />
                    </div>
                    <h3 className="text-base font-bold text-white uppercase tracking-wide">On Current Query</h3>
                    <p className="text-sm" style={{ color: '#94A3B8' }}>
                      Generate a formal opinion based on the question you just asked and the retrieved documents.
                    </p>
                    <div className="mt-2 px-4 py-1 rounded-lg text-[10px] font-mono uppercase font-bold"
                      style={{ border: '1px solid rgba(103,232,249,0.3)', color: '#67E8F9' }}>
                      [ EXECUTE_AUTO ]
                    </div>
                  </div>

                  {/* Option B */}
                  <div
                    onClick={() => setStep('manual_input')}
                    className="cursor-pointer p-8 rounded-2xl flex flex-col items-center gap-4 text-center transition-all duration-200 group"
                    style={{ border: '1px solid rgba(96,165,250,0.2)', background: 'rgba(96,165,250,0.04)' }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = 'rgba(96,165,250,0.4)';
                      e.currentTarget.style.background = 'rgba(96,165,250,0.08)';
                      e.currentTarget.style.boxShadow = '0 0 30px rgba(96,165,250,0.1)';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'rgba(96,165,250,0.2)';
                      e.currentTarget.style.background = 'rgba(96,165,250,0.04)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    <div className="p-4 rounded-full group-hover:scale-110 transition-transform"
                      style={{ background: 'rgba(96,165,250,0.1)', color: '#60A5FA' }}>
                      <PenTool size={28} />
                    </div>
                    <h3 className="text-base font-bold text-white uppercase tracking-wide">Manual Case Study</h3>
                    <p className="text-sm" style={{ color: '#94A3B8' }}>
                      Input a specific set of facts or a new scenario. The system will find relevant laws for you.
                    </p>
                    <div className="mt-2 px-4 py-1 rounded-lg text-[10px] font-mono uppercase font-bold"
                      style={{ border: '1px solid rgba(96,165,250,0.3)', color: '#60A5FA' }}>
                      [ CONFIGURE_MANUAL ]
                    </div>
                  </div>

                  {error && (
                    <div className="col-span-2 text-center font-mono text-sm p-3 rounded-xl"
                      style={{ color: '#EF4444', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
                      Error: {error}
                    </div>
                  )}
                </div>
              )}

              {/* STEP 2: Manual Input */}
              {step === 'manual_input' && (
                <div className="max-w-2xl mx-auto">
                  <button
                    onClick={() => setStep('selection')}
                    className="flex items-center gap-2 mb-6 text-xs font-mono uppercase transition-colors"
                    style={{ color: '#475569' }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#CBD5E1'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = '#475569'; }}
                  >
                    <ChevronLeft size={13} /> Back
                  </button>
                  <h3 className="text-base font-bold text-white mb-4 font-mono uppercase">Enter Case Facts</h3>
                  <textarea
                    value={manualFacts}
                    onChange={e => setManualFacts(e.target.value)}
                    className="w-full h-64 p-4 font-mono text-sm outline-none resize-none transition-all"
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: '12px',
                      color: '#CBD5E1',
                    }}
                    placeholder="Describe the facts of the case, the transaction details, and the specific doubt..."
                    onFocus={e => { e.currentTarget.style.borderColor = 'rgba(103,232,249,0.5)'; e.currentTarget.style.boxShadow = '0 0 15px rgba(103,232,249,0.15)'; }}
                    onBlur={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; e.currentTarget.style.boxShadow = 'none'; }}
                  />
                  <button
                    onClick={() => handleGenerate(true)}
                    disabled={!manualFacts.trim()}
                    className="mt-5 w-full py-3 rounded-xl font-bold font-mono uppercase tracking-widest text-sm text-white transition-all"
                    style={{
                      background: manualFacts.trim() ? 'linear-gradient(135deg, #67E8F9, #0E7490)' : 'rgba(103,232,249,0.2)',
                      opacity: manualFacts.trim() ? 1 : 0.5,
                      cursor: manualFacts.trim() ? 'pointer' : 'not-allowed',
                    }}
                  >
                    [ GENERATE_OPINION ]
                  </button>
                </div>
              )}

              {/* STEP 3: Generating */}
              {step === 'generating' && (
                <div className="flex flex-col items-center justify-center h-96 w-full rounded-2xl overflow-hidden"
                  style={{ background: 'rgba(103,232,249,0.04)', border: '1px solid rgba(103,232,249,0.1)' }}>
                  <NeuralBrainLoader />
                </div>
              )}

              {/* STEP 4: Result */}
              {step === 'result' && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <div
                    className="p-10 rounded-2xl mb-6 min-h-[500px]"
                    style={{
                      background: 'rgba(255,255,255,0.03)',
                      border: '1px solid rgba(255,255,255,0.06)',
                      borderTop: '3px solid #67E8F9',
                    }}
                  >
                    <div className="prose prose-sm max-w-none"
                      style={{ color: '#CBD5E1' }}>
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h1: p => <h1 className="text-xl font-bold mt-6 mb-4 text-white" {...p} />,
                          h2: p => <h2 className="text-lg font-bold mt-5 mb-3 text-white" {...p} />,
                          h3: p => <h3 className="text-base font-bold mt-4 mb-2 text-white" {...p} />,
                          p: p => <p className="mb-4 leading-relaxed" style={{ color: '#CBD5E1' }} {...p} />,
                          li: p => <li style={{ color: '#CBD5E1' }} {...p} />,
                          strong: p => <strong style={{ color: '#67E8F9' }} {...p} />,
                        }}
                      >
                        {advisoryContent}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}

            </div>
          </AdvisoryErrorBoundary>

          {/* Footer (result only) */}
          {step === 'result' && (
            <div
              className="px-6 py-4 flex justify-between items-center"
              style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}
            >
              <button
                onClick={() => setStep('selection')}
                className="text-xs font-mono uppercase transition-colors"
                style={{ color: '#475569' }}
                onMouseEnter={e => { e.currentTarget.style.color = '#CBD5E1'; }}
                onMouseLeave={e => { e.currentTarget.style.color = '#475569'; }}
              >
                &lt; New Advisory
              </button>
              <button
                onClick={handleDownload}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold font-mono uppercase text-xs tracking-wider text-white transition-all"
                style={{ background: 'linear-gradient(135deg, #67E8F9, #0E7490)', boxShadow: '0 0 20px rgba(103,232,249,0.35)' }}
                onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 0 35px rgba(103,232,249,0.6)'; }}
                onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 0 20px rgba(103,232,249,0.35)'; }}
              >
                <Download size={14} /> Download Report
              </button>
            </div>
          )}
        </motion.div>
      </div>
    </AnimatePresence>,
    document.body
  );
};

export default AdvisoryModal;
