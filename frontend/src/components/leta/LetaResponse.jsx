import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import ConfidenceBadge from './ConfidenceBadge';
import CitationList from './CitationList';
import LetaExplainability from './LetaExplainability';
import { BASE_URL } from '../../config/api';
import { Button } from '../common';
import { FileText, AlignLeft, ShieldCheck, Copy, Check, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import AdvisoryModal from './AdvisoryModal';
import ThinkingSources from './ThinkingSources';

const LetaResponse = ({ data, isDark = false, animate = true, onDocumentClick, onRegenerate }) => {
  const [citationMode, setCitationMode] = useState(false);
  const [isAdvisoryOpen, setIsAdvisoryOpen] = useState(false);
  const [hasCopied, setHasCopied] = useState(false);

  const handleCopy = () => {
    if (!data?.answer) return;
    navigator.clipboard.writeText(data.answer);
    setHasCopied(true);
    setTimeout(() => setHasCopied(false), 2000);
  };

  if (!data) return null;

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={`rounded-sm border overflow-hidden transition-all duration-300 ${
          isDark 
            ? 'bg-[#050A10] border-white/10 shadow-none' 
            : 'bg-white shadow-sentinel-blue/5 border-gray-100'
        }`}
      >
        {/* Header Bar */}
        <div className={`px-6 py-3 border-b flex items-center justify-between ${
           isDark ? 'bg-[#020202] border-white/10' : 'bg-gray-50 border-gray-100'
        }`}>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sentinel-green">
               <ShieldCheck size={16} />
               <span className="font-mono text-xs font-bold tracking-widest uppercase">LETA_OUTPUT_V1.0</span>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button 
                onClick={handleCopy}
                className="p-1.5 text-gray-500 hover:text-white hover:bg-white/10 rounded transition-colors relative group"
                title="Copy Answer"
            >
                {hasCopied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
            </button>
            
            {onRegenerate && (
                <button 
                    onClick={onRegenerate}
                    className="p-1.5 text-gray-500 hover:text-sentinel-blue hover:bg-sentinel-blue/10 rounded transition-colors"
                    title="Regenerate Answer"
                >
                    <RefreshCw size={14} />
                </button>
            )}
          </div>
        </div>
  
        {/* Content Area */}
        <div className="p-6 md:p-8 bg-[#050A10]">
          {(data.consulted_sources?.length > 0 || data.status) && (
            <ThinkingSources 
              sources={data.consulted_sources} 
              status={data.status}
              onDocumentClick={onDocumentClick}
            />
          )}

          {!citationMode ? (
            <>
              <div className={`prose prose-sm md:prose-base max-w-none font-sans leading-relaxed ${
                 isDark ? 'text-gray-300 prose-invert prose-headings:font-mono prose-headings:uppercase prose-strong:text-white prose-a:text-sentinel-green prose-table:border-white/10 prose-th:bg-[#020202] prose-td:border-white/10' : 'text-gray-700'
              }`}>
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({node, ...props}) => <h1 className="text-xl font-bold mt-6 mb-4" {...props} />,
                    h2: ({node, ...props}) => <h2 className="text-lg font-bold mt-5 mb-3" {...props} />,
                    h3: ({node, ...props}) => <h3 className="text-base font-bold mt-4 mb-2" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc list-outside ml-5 mb-4 space-y-2" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal list-outside ml-5 mb-4 space-y-2" {...props} />,
                    li: ({node, ...props}) => <li className="pl-1" {...props} />,
                    p: ({node, ...props}) => <p className="mb-4" {...props} />,
                    strong: ({node, ...props}) => <strong className="font-bold text-sentinel-green dark:text-sentinel-green" {...props} />,
                    table: ({node, ...props}) => <div className="overflow-x-auto my-6"><table className="min-w-full text-sm font-mono border border-white/10 rounded-sm" {...props} /></div>,
                    thead: ({node, ...props}) => <thead className="bg-[#020202] border-b border-white/10 text-white" {...props} />,
                    th: ({node, ...props}) => <th className="px-4 py-3 text-left font-bold" {...props} />,
                    td: ({node, ...props}) => <td className="px-4 py-3 border-b border-white/5 bg-[#050A10]" {...props} />,
                    a: ({node, ...props}) => {
                      const isDocLink = props.href && props.href.includes('/api/documents/view');
                      
                      return (
                        <a 
                          {...props} 
                          target={isDocLink ? undefined : "_blank"}
                          rel="noopener noreferrer" 
                          className="text-sentinel-green hover:text-white font-mono font-bold underline cursor-pointer transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (isDocLink && onDocumentClick) {
                                e.preventDefault();
                                
                                // Parse out the base URL and the hash fragments for precise PDF jumping
                                let baseUrl = props.href;
                                let page = null;
                                let search = null;
                                
                                if (props.href.includes('#')) {
                                   const parts = props.href.split('#');
                                   baseUrl = parts[0];
                                   const hashParams = new URLSearchParams(parts[1]);
                                   if (hashParams.has('page')) page = hashParams.get('page');
                                   if (hashParams.has('search')) search = hashParams.get('search');
                                }
                                
                                // Fix relative links so they hit the backend, not the Vite dev server
                                if (baseUrl.startsWith('/api/')) {
                                    const backendUrl = BASE_URL;
                                    baseUrl = backendUrl + baseUrl;
                                }
                                
                                onDocumentClick({ url: baseUrl, page, search });
                            }
                          }}
                        />
                      );
                    },
                  }}
                >
                  {data?.answer || ''}
                </ReactMarkdown>
              </div>
              
              {/* ADVISORY CTA */}
              <div className="mt-8 pt-6 border-t border-white/10 flex justify-end">
                  <button 
                    onClick={() => setIsAdvisoryOpen(true)}
                    className="group flex items-center gap-3 px-5 py-2.5 bg-sentinel-blue/10 border border-sentinel-blue/30 text-sentinel-blue hover:bg-sentinel-blue hover:text-white transition-all rounded-sm"
                  >
                     <FileText size={16} className="group-hover:scale-110 transition-transform" />
                     <span className="font-mono text-xs font-bold uppercase tracking-widest">Generate Legal Advisory</span>
                  </button>
              </div>

            </>
          ) : (
             <div className="py-4">
                {/* Citations Mode hidden */}
             </div>
          )}
        </div>
        
        {/* Footer */}
        <div className={`px-6 py-2 border-t flex justify-between items-center text-[10px] font-mono uppercase tracking-widest ${
           isDark 
             ? 'bg-[#020202] border-white/10 text-gray-600' 
             : 'bg-sentinel-blue/5 border-sentinel-blue/10 text-sentinel-blue/60'
        }`}>
          <span>GENERATED_BY_SENTINEL.AI_ENGINE</span>
          <span>ID: {data && Math.random().toString(36).substr(2, 9).toUpperCase()}</span>
        </div>
      </motion.div>

      {/* Render Modal */}
      <AdvisoryModal 
        isOpen={isAdvisoryOpen} 
        onClose={() => setIsAdvisoryOpen(false)}
        initialQuery={data.query} // We need to ensure data.query exists or is passed down!
        initialContext={data.answer} // Using answer as context for now, ideally we pass retrieved chunks
      />
    </>
  );
};

export default LetaResponse;
