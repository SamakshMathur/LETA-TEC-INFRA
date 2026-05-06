import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Send, Download, Copy, Loader2, FileText, User, Sparkles, AlertCircle, Trash2, CheckCircle2, Zap, Share2 } from 'lucide-react';
import { BASE_URL } from '../config/api';

const TemplateCustomization: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const chatEndRef = useRef<HTMLDivElement>(null);
  
  const [template, setTemplate] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [inputValue, setInputValue] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generatedDraft, setGeneratedDraft] = useState<string>('');
  const [showCopyFeedback, setShowCopyFeedback] = useState<boolean>(false);

  useEffect(() => {
    const fetchTemplate = async () => {
      try {
        const response = await fetch(`${BASE_URL}/api/templates/${id}`);
        const data = await response.json();
        setTemplate(data);
        
        setMessages([{
          role: 'assistant',
          content: `Welcome to the **Sovereign Drafting Suite**. I've initialized the **${data.title}** protocol. \n\nProvide the case specifics—GSTINs, amounts, or contextual nuances—and I will synthesize a high-fidelity legal draft for your review.`
        }]);
      } catch (err) {
        console.error(err);
      }
    };
    fetchTemplate();
  }, [id]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputValue.trim() || isGenerating) return;

    const userMsg = inputValue.trim();
    setInputValue('');
    
    const updatedMessages = [...messages, { role: 'user', content: userMsg }];
    setMessages(updatedMessages);
    
    setIsGenerating(true);
    try {
      const response = await fetch(`${BASE_URL}/api/templates/${id}/customize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          user_context: userMsg,
          messages: messages.filter(m => m.role !== 'assistant' || !m.content.startsWith('Welcome')) 
        })
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        setMessages([...updatedMessages, { role: 'assistant', content: data.full_response.split('[DRAFT_START]')[0].trim() || 'The draft has been recalibrated with your latest specifications.' }]);
        setGeneratedDraft(data.customized_draft);
      } else {
        throw new Error(data.detail || 'Failed to generate draft');
      }
    } catch (err) {
      console.error(err);
      setMessages([...updatedMessages, { role: 'assistant', content: "An error occurred in the neural synthesis layer. Please re-input your directives." }]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = () => {
    const content = generatedDraft || (template?.content || "");
    const encodedContent = encodeURIComponent(content);
    window.open(`${BASE_URL}/api/templates/${id}/download?content=${encodedContent}`, '_blank');
  };

  const copyToClipboard = () => {
    if (!generatedDraft) return;
    navigator.clipboard.writeText(generatedDraft);
    setShowCopyFeedback(true);
    setTimeout(() => setShowCopyFeedback(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#FFFFFF] text-leta-gray-200 flex flex-col h-screen overflow-hidden selection:bg-emerald-500/30">
      
      {/* Top Navigation - Titan Glass */}
      <div className="bg-glass border-b border-leta-gray-100 px-8 py-4 flex items-center justify-between z-30 relative backdrop-blur-2xl">
        <div className="flex items-center gap-6">
          <button 
            onClick={() => navigate('/gst/templates')}
            className="group flex items-center gap-2 text-leta-gray-600 hover:text-leta-gray-900 transition-all bg-leta-gray-50 px-3 py-2 rounded-leta border border-leta-gray-100 hover:border-emerald-500/30"
          >
            <ArrowLeft size={18} className="group-hover:-translate-x-1 transition-transform" />
            <span className="text-[10px] font-black tracking-widest uppercase">Dashboard</span>
          </button>
          
          <div className="h-8 w-[1px] bg-leta-white/10" />
          
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-sm font-black tracking-widest text-leta-gray-900 uppercase flex items-center gap-2">
                <Zap size={14} className="text-emerald-500 fill-emerald-500" /> 
                LETA_TITAN // DRAFT_SUITE
              </h1>
              <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 font-mono tracking-tighter">v3.0_STABLE</span>
            </div>
            <p className="text-[10px] text-leta-gray-500 mt-0.5 tracking-tight flex items-center gap-2 uppercase">
              REFINING: <span className="text-emerald-400 font-bold max-w-[200px] truncate">{template?.title}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button className="p-2.5 rounded-leta bg-leta-gray-50 border border-leta-gray-200 text-leta-gray-600 hover:text-emerald-400 transition-all">
            <Share2 size={18} />
          </button>
          {generatedDraft && (
             <button 
               onClick={handleDownload}
               className="flex items-center gap-3 bg-leta-white text-leta-black px-6 py-2.5 rounded-leta text-[10px] font-black tracking-widest uppercase hover:opacity-90 transition-opacity shadow-[0_4px_20px_rgba(0,0,0,0.05)]"
             >
               <Download size={16} /> EXPORT .DOCX
             </button>
          )}
        </div>
      </div>

      {/* Main Workspace Surface */}
      <div className="flex-1 flex overflow-hidden relative">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_-20%,rgba(16,185,129,0.05)_0%,transparent_50%)] pointer-events-none" />
        
        {/* Left Side: Modular Chat Panel */}
        <div className="w-[440px] flex flex-col bg-[#050505] border-r border-leta-gray-100 relative z-20 shadow-[-20px_0_60px_rgba(0,0,0,0.5)]">
          
          {/* Status Bar */}
          <div className="px-6 py-2 border-b border-leta-gray-100 bg-leta-white/[0.02] flex items-center justify-between">
            <span className="text-[8px] font-black tracking-[0.2em] text-leta-gray-500 uppercase">Neural Stream</span>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-[8px] font-black text-emerald-500 uppercase">Synced</span>
            </div>
          </div>

          {/* Chat History Container */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar bg-[linear-gradient(rgba(0,0,0,0)_0%,rgba(16,185,129,0.02)_100%)]">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[90%] rounded-2xl p-5 text-[13px] leading-relaxed transition-all duration-500 ${
                  msg.role === 'user' 
                  ? 'bg-emerald-600 text-leta-gray-900 font-medium rounded-tr-none shadow-[0_10px_25px_rgba(16,185,129,0.15)] animate-slide-left' 
                  : 'bg-leta-gray-50 border border-leta-gray-200 text-leta-gray-300 rounded-tl-none backdrop-blur-md animate-slide-right'
                }`}>
                  <div className="flex items-center gap-2 mb-2 opacity-50">
                    {msg.role === 'user' ? <User size={12} strokeWidth={2.5} /> : <Zap size={12} className="text-emerald-500" />}
                    <span className="text-[9px] uppercase tracking-[0.2em] font-black">
                      {msg.role === 'user' ? 'Advocate' : 'LETA_CORELINK'}
                    </span>
                  </div>
                  <div className="whitespace-pre-wrap font-sans">
                    {msg.content}
                  </div>
                </div>
              </div>
            ))}
            {isGenerating && (
              <div className="flex justify-start animate-slide-right">
                <div className="bg-leta-gray-50 border border-leta-gray-100 text-leta-gray-600 p-5 rounded-2xl rounded-tl-none flex flex-col gap-4 w-full">
                  <div className="flex items-center gap-3">
                    <Loader2 size={16} className="animate-spin text-emerald-500" />
                    <span className="text-[10px] font-black tracking-widest uppercase italic text-emerald-500/70">Synthesizing draft...</span>
                  </div>
                  <div className="flex gap-1">
                    <div className="h-1 bg-emerald-500/20 rounded-full w-full overflow-hidden">
                       <div className="h-full bg-emerald-500 w-1/3 animate-progress"></div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Chat Input - Premium Dock */}
          <div className="p-6 bg-glass border-t border-leta-gray-100 backdrop-blur-3xl">
            <form onSubmit={handleSendMessage} className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500/20 to-blue-500/20 rounded-2xl blur opacity-0 group-focus-within:opacity-100 transition duration-700"></div>
              <div className="relative">
                <textarea
                  rows={3}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="Instruct LETA (e.g., 'Incorporate the new ITC circular 183' or 'Set date as 24/03/24')"
                  className="w-full bg-leta-white/[0.03] border border-leta-gray-200 rounded-2xl p-5 pr-14 text-sm text-leta-gray-100 placeholder-gray-600 focus:outline-none focus:border-emerald-500/50 resize-none transition-all shadow-inner font-sans"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                />
                <button 
                  type="submit"
                  disabled={!inputValue.trim() || isGenerating}
                  className="absolute right-4 bottom-4 w-10 h-10 bg-emerald-600 text-leta-gray-900 rounded-leta hover:bg-emerald-500 transition-colors disabled:opacity-30 disabled:grayscale flex items-center justify-center shadow-lg"
                >
                  <Send size={18} />
                </button>
              </div>
            </form>
            <div className="flex items-center justify-center gap-6 mt-4 opacity-40">
               <div className="flex items-center gap-1.5 text-[8px] font-black uppercase tracking-widest"><Sparkles size={8}/> AI_ENHANCED</div>
               <div className="flex items-center gap-1.5 text-[8px] font-black uppercase tracking-widest"><FileText size={8}/> LEGALLY_VETTED</div>
            </div>
          </div>
        </div>

        {/* Right Side: High-Fidelity Document Canvas */}
        <div className="flex-1 bg-[#0a0a0a] flex flex-col p-12 overflow-hidden relative">
          
          {/* Decorative Canvas Background */}
          <div className="absolute inset-0 opacity-[0.4] pointer-events-none overflow-hidden">
             <div className="absolute top-0 right-0 w-[800px] h-[800px] bg-emerald-500/10 blur-[180px] rounded-full translate-x-1/2 -translate-y-1/2" />
             <div className="absolute bottom-0 left-0 w-[600px] h-[600px] bg-blue-500/5 blur-[150px] rounded-full -translate-x-1/2 translate-y-1/2" />
          </div>

          {/* Action Ribbon for Draft */}
          {generatedDraft && (
            <div className="absolute top-12 right-12 z-20 flex items-center gap-3 animate-slide-left">
              <button 
                onClick={copyToClipboard}
                className="flex items-center gap-2 bg-leta-gray-50 hover:bg-leta-white text-leta-gray-600 hover:text-leta-black px-4 py-2 rounded-leta border border-leta-gray-200 transition-all font-black text-[10px] uppercase tracking-widest"
              >
                {showCopyFeedback ? <CheckCircle2 size={14} className="text-emerald-500" /> : <Copy size={14} />}
                {showCopyFeedback ? 'Copied' : 'Copy'}
              </button>
            </div>
          )}

          {/* Real-world Paper Physics Simulation / Document Layer */}
          <div className="flex-1 max-w-4xl mx-auto w-full overflow-y-auto custom-scrollbar bg-leta-white shadow-[0_40px_100px_rgba(0,0,0,0.6)] rounded-leta p-16 md:p-24 text-leta-gray-900 leading-[1.8] font-serif transition-all duration-700 relative hover:shadow-[0_60px_120px_rgba(0,0,0,0.7)] group/doc">
            
            {/* Watermark */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none opacity-[0.03] rotate-[30deg] select-none text-9xl font-black">
               LETA_TITAN
            </div>

            {!generatedDraft && !isGenerating ? (
              <div className="h-full flex flex-col items-center justify-center text-center opacity-20 select-none py-32 grayscale group-hover/doc:grayscale-0 transition-all duration-1000">
                <FileText size={120} strokeWidth={0.5} className="mb-8 text-leta-black" />
                <h3 className="text-3xl font-serif italic mb-4">Awaiting Synthesis</h3>
                <p className="text-base font-sans font-light max-w-sm tracking-tight leading-relaxed">Your professional legal response will materialize here as you collaborate with LETA on the left.</p>
                <div className="mt-12 flex gap-4">
                   <div className="w-12 h-[1px] bg-leta-black/20" />
                   <div className="w-2 h-2 rounded-full border border-leta-gray-300" />
                   <div className="w-12 h-[1px] bg-leta-black/20" />
                </div>
              </div>
            ) : (
              <div className="whitespace-pre-wrap text-[17px] relative z-10 animate-fade-in animate-float-text">
                {generatedDraft}
              </div>
            )}
          </div>

          {/* Status Indicators Footer */}
          <div className="mt-8 flex justify-between items-center px-4">
             <div className="flex items-center gap-12 text-[10px] text-leta-gray-900/20 font-mono tracking-[0.3em] uppercase">
                <span className="flex items-center gap-2"><div className="w-1 h-1 bg-emerald-500 rounded-full" /> CANVAS: HIGH_FIDELITY</span>
                <span>SECURITY: ENCRYPTED</span>
             </div>
             <div className="text-[9px] text-leta-gray-900/30 font-black tracking-widest uppercase bg-leta-gray-50 border border-leta-gray-100 py-1.5 px-4 rounded-leta">
                TITAN_INTELLIGENCE // V3_ENGINE
             </div>
          </div>
        </div>

      </div>

      <style>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(0, 0, 0, 0.05);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(16, 185, 129, 0.2);
        }
        @keyframes slide-left {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes slide-right {
          from { opacity: 0; transform: translateX(-20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes progress {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(200%); }
        }
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes float-text {
          0% { transform: translateY(0px); }
          12% { transform: translateY(-5px); }
        }
        .animate-slide-left { animation: slide-left 0.6s cubic-bezier(0.23, 1, 0.32, 1) forwards; }
        .animate-slide-right { animation: slide-right 0.6s cubic-bezier(0.23, 1, 0.32, 1) forwards; }
        .animate-progress { animation: progress 2s linear infinite; }
        .animate-fade-in { animation: fade-in 1.5s ease-out forwards; }
        .animate-float-text { animation: float-text 1s cubic-bezier(0.4, 0, 0.2, 1) forwards; }
      `}</style>
    </div>
  );
};

export default TemplateCustomization;
