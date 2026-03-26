import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, X, Send, Sparkles, FileText, ChevronRight, Terminal, Menu, Paperclip } from 'lucide-react';
import LetaResponse from './LetaResponse';
import { BASE_URL } from '../../config/api';
import ChatSidebar from './ChatSidebar';
import { NeuralLoader } from '../effects';
import { PDFViewer } from '../documents';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const AskLetaWidget = ({ domain = 'gst', contextDesc = 'GST scenarios' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);
  
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };
  
  const navigate = useNavigate();

  // Session State
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]); // Array of {role, content, ...}
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [openDocuments, setOpenDocuments] = useState([]);
  const [activeDocId, setActiveDocId] = useState(null);

  const handleDocumentClick = ({ url, page, search }) => {
    // Check if doc already open
    const id = url;
    const existing = openDocuments.find(d => d.id === id);
    if (!existing) {
       setOpenDocuments(prev => [...prev, { id, url, title: url.split('filename=')[1]?.replace(/%20/g, ' ') || 'Document', page, search }]);
    } else {
       // Update page/search if clicking a new citation for same doc
       setOpenDocuments(prev => prev.map(d => d.id === id ? { ...d, page, search } : d));
    }
    setActiveDocId(id);
  };
  
  const closeDocument = (id) => {
    setOpenDocuments(prev => {
       const next = prev.filter(d => d.id !== id);
       if (activeDocId === id) {
          setActiveDocId(next.length > 0 ? next[next.length - 1].id : null);
       }
       return next;
    });
  };

  // Auto-scroll ref
  const messagesEndRef = useRef(null);
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // ... (rest remains same until handleOpen)

  const handleOpenWidget = () => {
    setIsOpen(true);
  };

  // Load Session
  const handleSelectSession = async (sessionId) => {
    try {
      setIsLoading(true);
      setCurrentSessionId(sessionId);
      const res = await axios.get(`${BASE_URL}/api/sessions/${sessionId}`);
      
      // Map history to UI format
      // Note: Backend stores plain text. We wrap it for LetaResponse.
      const uiMessages = res.data.messages.map(msg => ({
        role: msg.role,
        content: msg.content,
        // Mock data for UI components that expect it (since we only stored text)
        confidence: 1.0, 
        citations: [],
        isHistory: true // Mark as history to disable animation 
      }));
      setMessages(uiMessages);
      setIsLoading(false);
    } catch (err) {
      console.error("Failed to load session:", err);
      setIsLoading(false);
    }
  };

  const handleNewSession = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setQuery("");
    setIsLoading(false);
  };

  // Real Steam API Call to LETA Backend
  const handleAsk = async (queryOverride = null) => {
    const activeQuery = typeof queryOverride === 'string' ? queryOverride : query;
    if (!activeQuery.trim()) return;

    // 1. Setup Request
    const userMsg = { role: 'user', content: activeQuery };
    const newAiMsg = { role: 'assistant', content: '', confidence: 0.95, citations: [] };
    
    // Optimistic Update
    setMessages(prev => [...prev, userMsg, newAiMsg]);
    setQuery("");
    setSelectedFile(null); // Clear file after staging for upload
    setIsLoading(true);

    try {
      const baseUrl = BASE_URL;
      
      // 2. Create Session if needed
      let activeSessionId = currentSessionId;
      if (!activeSessionId) {
        const title = query.length > 30 ? query.substring(0, 30) + "..." : query;
        const sessionRes = await axios.post(`${baseUrl}/api/sessions/new`, { title });
        activeSessionId = sessionRes.data.session_id;
        setCurrentSessionId(activeSessionId);
      }

      // 3. Call Ask API
      const headers = {};

      let res;
      if (selectedFile) {
          const formData = new FormData();
          formData.append('file', selectedFile);
          formData.append('question', userMsg.content);
          if (activeSessionId) {
             formData.append('session_id', activeSessionId);
          }
          // Do NOT set Content-Type header manually when sending FormData
          res = await fetch(`${baseUrl}/ask-with-file`, {
            method: 'POST',
            headers,
            body: formData,
          });
      } else {
          headers['Content-Type'] = 'application/json';
          res = await fetch(`${baseUrl}/ask`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
              question: userMsg.content,
              session_id: activeSessionId,
              intent: "general"
            }),
          });
      }

      if (!res.ok) throw new Error(`Server error: ${res.status}`);

      // 4. Stream Response
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      setIsLoading(false); // Stop loader, show streaming text

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        
        setMessages(prev => {
            const newHistory = [...prev];
            const lastMsg = newHistory[newHistory.length - 1];
            if (lastMsg.role === 'assistant') {
                // Create a NEW object — prevents React double-render from direct mutation
                newHistory[newHistory.length - 1] = {
                    ...lastMsg,
                    content: lastMsg.content + chunk
                };
            }
            return newHistory;
        });
      }

    } catch (error) {
      console.error("LETA API Error:", error);
      setMessages(prev => {
         const newHistory = [...prev];
         const lastMsg = newHistory[newHistory.length - 1];
         lastMsg.content += `\n\n[Error Terminated]: ${error.message}`;
         return newHistory;
      });
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Sidebar Trigger Card - Console Module */}
      <div 
        className="group relative bg-[#050A10]/60 backdrop-blur-md rounded-sm border border-sentinel-blue/30 overflow-hidden cursor-pointer hover:border-sentinel-green/80 transition-all duration-500 hover:shadow-[0_0_30px_rgba(11,115,80,0.3)]"
        onClick={handleOpenWidget}
      >
        <div className="absolute top-0 left-0 w-1 h-full bg-sentinel-blue group-hover:bg-sentinel-green transition-colors duration-300 shadow-[0_0_10px_#003B59]" />
        <div className="p-6 relative z-10">
           <div className="flex items-center justify-between mb-4">
              <div className="p-0 text-sentinel-blue group-hover:text-sentinel-green transition-colors duration-300 drop-shadow-[0_0_5px_rgba(0,0,0,0.5)]">
                <Terminal size={24} />
              </div>
              <ChevronRight className="text-gray-600 group-hover:text-sentinel-green group-hover:translate-x-1 transition-all" />
           </div>
           <h3 className="text-xl font-bold text-white mb-2 font-mono uppercase tracking-tight group-hover:text-shadow-[0_0_10px_rgba(255,255,255,0.3)]">Access LETA Console</h3>
           <p className="text-xs text-gray-500 mb-0 font-mono tracking-wide">
             // INITIALIZE ADVISORY PROTOCOL FOR {domain.toUpperCase()}
           </p>
           <button className="mt-6 w-full py-3 bg-[#081018]/50 border border-white/10 text-gray-400 text-xs font-mono font-bold uppercase tracking-[0.2em] hover:text-white hover:border-sentinel-green hover:bg-sentinel-green/10 transition-colors backdrop-blur-sm">
             [ LAUNCH_TERMINAL ]
           </button>
        </div>
      </div>

      {/* Full Screen Overlay Modal - PORTALED TO BODY */}
      {ReactDOM.createPortal(
        <AnimatePresence>
          {isOpen && (
            <div className="fixed inset-0 z-[9999] flex justify-end pointer-events-none">
               {/* Backdrop */}
               <motion.div 
                 initial={{ opacity: 0 }}
                 animate={{ opacity: 1 }}
                 exit={{ opacity: 0 }}
                 className="absolute inset-0 bg-black/60 backdrop-blur-md pointer-events-auto"
                 onClick={() => setIsOpen(false)}
               />

               {/* Slide-out Panel (Dynamic Width) */}
               <motion.div
                 initial={{ x: '100%' }}
                 animate={{ x: 0 }}
                 exit={{ x: '100%' }}
                 transition={{ type: "spring", damping: 30, stiffness: 300 }}
                 className={`relative h-full bg-[#020202] border-l border-white/20 shadow-none pointer-events-auto flex flex-row font-sans ${
                    openDocuments.length > 0 ? 'w-full' : 'w-full lg:w-3/4'
                 }`}
               >
                  {/* LEFT SPLIT: PDF VIEWER TABS */}
                  {openDocuments.length > 0 && (
                    <div className="hidden lg:flex flex-col border-r border-white/10 animate-in slide-in-from-left duration-300 bg-[#050A10]" style={{ width: '40%', minWidth: '500px' }}>
                        {/* Tabs Area */}
                        <div className="flex bg-[#050A10] border-b border-white/10 overflow-x-auto custom-scrollbar">
                            {openDocuments.map((doc) => (
                                <div 
                                    key={doc.id}
                                    onClick={() => setActiveDocId(doc.id)}
                                    className={`flex items-center gap-2 px-4 py-3 text-xs font-mono font-bold uppercase tracking-wider cursor-pointer border-r border-white/10 transition-colors whitespace-nowrap ${
                                        activeDocId === doc.id ? 'bg-[#020202] text-sentinel-green border-b-2 border-b-sentinel-green' : 'text-gray-500 hover:text-gray-300 hover:bg-[#1A1A1A]'
                                    }`}
                                >
                                    <span className="truncate max-w-[200px]">{doc.title}</span>
                                    <button 
                                        onClick={(e) => { e.stopPropagation(); closeDocument(doc.id); }}
                                        className="ml-3 text-gray-600 hover:text-red-400"
                                    >
                                        <X size={14} />
                                    </button>
                                </div>
                            ))}
                        </div>
                        
                        {/* Active Viewer */}
                        {openDocuments.map((doc) => (
                            doc.id === activeDocId && (
                                <div key={doc.id} className="flex-1 h-full overflow-hidden">
                                    <PDFViewer 
                                        url={doc.url} 
                                        onClose={() => closeDocument(doc.id)}
                                        title={doc.title}
                                        initialPage={doc.page}
                                        keyword={doc.search}
                                    />
                                </div>
                            )
                        ))}
                    </div>
                  )}

                  {/* RIGHT SPLIT: CHAT INTERFACE */}
                  <div className="flex-1 flex flex-col h-full overflow-hidden relative">
                  
                  {/* Chat Header */}
                  <div className="flex items-center justify-between p-4 border-b border-white/10 bg-[#050A10]">
                     <div className="flex items-center gap-4">
                        <button 
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            className="p-2 text-gray-400 hover:text-white border border-transparent hover:bg-white/5 rounded transition-colors"
                        >
                            <Menu size={20} />
                        </button>
                        <div>
                          <h2 className="text-lg font-bold text-white font-mono tracking-wide uppercase">LETA Console</h2>
                          <div className="flex items-center gap-2">
                             <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"/>
                             <span className="text-[10px] font-mono text-gray-400 uppercase tracking-wider">
                                SYSTEM ONLINE {currentSessionId ? `:: SESSION ${currentSessionId.substring(0,4)}` : ''}
                             </span>
                          </div>
                        </div>
                     </div>
                     <button 
                       onClick={() => setIsOpen(false)}
                       className="p-2 text-gray-500 hover:text-white border border-transparent hover:border-white/10 rounded-sm transition-colors"
                     >
                       <X size={24} />
                     </button>
                  </div>

                  {/* Body Layout: Sidebar + Main */}
                  <div className="flex flex-1 overflow-hidden">
                      {/* Sidebar */}
                      <ChatSidebar 
                        isOpen={isSidebarOpen} 
                        currentSessionId={currentSessionId}
                        onSelectSession={handleSelectSession}
                        onNewSession={handleNewSession}
                        toggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
                      />

                      {/* Chat Area */}
                      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#020202] relative">
                         <div className="flex-1 overflow-y-auto p-6 md:p-10 custom-scrollbar">
                            {messages.length === 0 ? (
                               <div className="max-w-4xl mx-auto mt-10">
                                  <div className="text-center mb-12">
                                    <h1 className="text-2xl md:text-3xl font-bold text-white mb-4 font-mono uppercase tracking-tight">
                                      Awaiting Query Input
                                    </h1>
                                    <p className="text-gray-500 font-mono text-sm max-w-xl mx-auto border-l-2 border-sentinel-blue pl-4 text-left">
                                      System Ready. Enter a query to begin a new session.
                                    </p>
                                  </div>
                                  
                                  {/* Quick Starters */}
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto">
                                     <div className="p-4 bg-[#050A10] border border-white/10 hover:border-sentinel-green/50 cursor-pointer transition-colors group" onClick={() => setQuery("What is the penalty for delayed filing of GSTR-3B under Section 47?")}>
                                        <div className="flex items-center gap-2 mb-2 text-gray-500 group-hover:text-sentinel-green text-xs font-mono font-bold uppercase transition-colors">
                                           <FileText size={14} /> &gt; Load_Sample_01
                                        </div>
                                        <p className="text-gray-400 text-sm font-mono leading-tight group-hover:text-gray-200">Penalty for delayed filing under Section 47?</p>
                                     </div>
                                     <div className="p-4 bg-[#050A10] border border-white/10 hover:border-sentinel-blue/50 cursor-pointer transition-colors group" onClick={() => setQuery("Explain the applicability of RCM on legal services provided by an advocate.")}>
                                        <div className="flex items-center gap-2 mb-2 text-gray-500 group-hover:text-sentinel-blue text-xs font-mono font-bold uppercase transition-colors">
                                           <FileText size={14} /> &gt; Load_Sample_02
                                        </div>
                                        <p className="text-gray-400 text-sm font-mono leading-tight group-hover:text-gray-200">Applicability of RCM on legal services?</p>
                                     </div>
                                  </div>
                               </div>
                            ) : (
                               <div className="max-w-4xl mx-auto space-y-8 pb-20">
                                  {messages.map((msg, idx) => (
                                    <div key={idx} className={`animate-in fade-in slide-in-from-bottom-2 duration-500`}>
                                        {msg.role === 'user' ? (
                                            <div className="flex justify-end mb-6">
                                                <div className="bg-[#0A1622] rounded-2xl rounded-tr-sm p-4 text-white max-w-[80%] border border-white/10 shadow-[0_4px_10px_rgba(0,0,0,0.3)]">
                                                    <div className="text-[10px] text-sentinel-blue font-mono mb-1 uppercase tracking-wider">User Query</div>
                                                    <p className="whitespace-pre-wrap leading-relaxed text-sm">{msg.content}</p>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="flex justify-start mb-10 w-full relative">
                                                <div className="w-full">
                                                    {/* AI Avatar / Indicator */}
                                                    <div className="flex items-center gap-2 mb-2 pl-1">
                                                        <Sparkles className="w-4 h-4 text-sentinel-green animate-pulse" />
                                                        <span className="text-xs font-mono text-sentinel-green uppercase">LETA AI Analysis</span>
                                                    </div>
                                                    
                                                    {/* The Response Component */}
                                                    {/* We adapt the data structure to fit LetaResponse */}
                                                    <LetaResponse 
                                                        data={{
                                                            query: messages[idx - 1]?.content || "",
                                                            answer: msg.content,
                                                            citations: msg.citations || [],
                                                            confidence: msg.confidence || 0.95
                                                        }} 
                                                        isDark={true}
                                                        animate={!msg.isHistory}
                                                        onDocumentClick={handleDocumentClick}
                                                        onRegenerate={() => {
                                                            // Find previous user message
                                                            const prevMsg = messages[idx - 1];
                                                            if (prevMsg && prevMsg.role === 'user') {
                                                                handleAsk(prevMsg.content);
                                                            }
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                  ))}
                                  {isLoading && (
                                     <div className="flex justify-center py-8">
                                        <NeuralLoader />
                                     </div>
                                  )}
                                  <div ref={messagesEndRef} />
                               </div>
                            )}
                         </div>

                         {/* Sticky Input Area */}
                         <div className="p-4 bg-[#020202] border-t border-white/10 z-20">
                            <div className="max-w-4xl mx-auto relative group">
                               <div className="absolute -top-3 left-4 px-2 bg-[#020202] text-xs font-mono text-sentinel-green border border-sentinel-green/20">
                                  INPUT_TERMINAL
                               </div>
                               {/* File Preview Badge */}
                               <AnimatePresence>
                                  {selectedFile && (
                                     <motion.div 
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, scale: 0.9 }}
                                        className="absolute -top-3 right-4 flex items-center gap-2 bg-[#081018] border border-sentinel-green/30 px-3 py-1 rounded-sm z-30"
                                     >
                                         <Paperclip size={12} className="text-sentinel-green" />
                                         <span className="text-xs font-mono text-gray-300 max-w-[150px] truncate">
                                             {selectedFile.name}
                                         </span>
                                         <button onClick={clearFile} className="text-gray-500 hover:text-red-400 ml-2">
                                             <X size={14} />
                                         </button>
                                     </motion.div>
                                  )}
                               </AnimatePresence>

                               <textarea
                                  value={query}
                                  onChange={(e) => setQuery(e.target.value)}
                                  placeholder={currentSessionId ? "Continue this session..." : "Start a new analysis..."}
                                  className="w-full min-h-[80px] p-4 bg-[#050A10] border border-white/10 text-gray-300 placeholder-gray-600 focus:border-sentinel-green focus:bg-[#081018] transition-all outline-none resize-none text-sm font-mono leading-relaxed rounded-sm shadow-inner custom-scrollbar"
                                  onKeyDown={(e) => {
                                    if(e.key === 'Enter' && !e.shiftKey) {
                                        e.preventDefault();
                                        handleAsk();
                                    }
                                  }}
                               />
                               <div className="absolute bottom-4 right-4 flex items-center gap-3">
                                  {/* Hidden File Input */}
                                  <input 
                                     type="file" 
                                     ref={fileInputRef} 
                                     onChange={handleFileChange} 
                                     className="hidden" 
                                     accept=".pdf,.png,.jpg,.jpeg,.txt"
                                  />
                                  <button
                                     onClick={() => fileInputRef.current?.click()}
                                     disabled={isLoading}
                                     className={`p-2 transition-colors disabled:opacity-50 ${selectedFile ? 'text-sentinel-green' : 'text-gray-500 hover:text-sentinel-green'}`}
                                     title="Attach Document"
                                  >
                                      <Paperclip size={18} />
                                  </button>

                                  <button
                                     onClick={handleAsk}
                                     disabled={(!query.trim() && !selectedFile) || isLoading}
                                     className={`flex items-center gap-2 px-4 py-2 font-mono font-bold text-xs uppercase tracking-widest border transition-all ${
                                       (!query.trim() && !selectedFile) || isLoading
                                         ? 'bg-gray-900 border-gray-800 text-gray-600 cursor-not-allowed'
                                         : 'bg-sentinel-green/10 border-sentinel-green text-sentinel-green hover:bg-sentinel-green hover:text-white'
                                     }`}
                                   >
                                       <Send size={14} />
                                       EXECUTE
                                   </button>
                               </div>
                            </div>
                         </div>
                      </div>
                  </div>

                  </div>
               </motion.div>
            </div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </>
  );
};

export default AskLetaWidget;
