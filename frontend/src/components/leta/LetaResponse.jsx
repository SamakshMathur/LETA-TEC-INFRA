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

// Ensures every bold (green) term in the response is a clickable document link.
//
// Phase 1 — bold text: any **bold** containing a legal/GST keyword gets wrapped
//   in a link to the best matching consulted source.
// Phase 2 — plain text: catches remaining unlinked legal refs (Section X, Rule X, etc.)
//
// Both phases use a placeholder shield so already-processed links are never
// double-wrapped.
function linkifyLegalRefs(markdown, sources) {
  if (!sources || sources.length === 0 || !markdown) return markdown;

  const findSrc = (...keywords) =>
    sources.find(s => {
      const hay = (s.title || s.url || '').toLowerCase();
      return keywords.some(kw => hay.includes(kw.toLowerCase()));
    });

  // Shared shield: protect links from re-processing
  const placeholders = [];
  const shield = m => { placeholders.push(m); return `\x00LINK${placeholders.length - 1}\x00`; };

  // Shield only links that already use an internal /api/documents/view URL.
  // Links with external URLs (e.g. https://cbic-gst.gov.in) are stripped back to
  // plain text so Phase 1 / Phase 2 can re-link them to the correct internal source.
  let safe = markdown.replace(/\[([^\]]*)\]\(([^)]+)\)/g, (match, text, url) => {
    if (url.includes('/api/documents/view')) return shield(match);
    return text; // strip external link, let phases re-process
  });

  const wrap = (text, src) => (src?.url ? `[${text}](${src.url})` : text);

  // Choose the best source for a bold phrase using specificity-first matching
  const findSrcForBold = text => {
    const t = text.toLowerCase();

    // 1. Specific GSTR form code → match source by form code in filename
    const gstrM = t.match(/gstr[-‑]?(\d+[a-z]?)/i);
    if (gstrM) {
      const norm = 'gstr' + gstrM[1].replace(/[-‑]/g, '');
      return (
        sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s%20]/g, '').includes(norm)) ||
        findSrc('gstr', 'form', 'return') ||
        sources[0]
      );
    }

    // 2. Statutory Acts
    if (/(?:c|i|s|ut)?gst\s+act/i.test(t))
      return findSrc('act', 'bare law', 'cgst', 'igst') || sources[0];

    // 3. Section reference
    if (/section\s+\d/i.test(t))
      return findSrc('act', 'cgst', 'igst', 'gst') || sources[0];

    // 4. Rule reference
    if (/rule\s+\d/i.test(t))
      return findSrc('rule', 'rules') || sources[0];

    // 5. Notification / Circular
    if (/notification\s+no/i.test(t)) return findSrc('notification', 'circular') || sources[0];
    if (/circular\s+no/i.test(t))    return findSrc('circular') || sources[0];

    // 6. Form codes (DRC-01, RFD-01, PMT-06, EWB-01, …)
    if (/\b(?:drc|rfd|pmt|reg|cmp|ewb)[-‑\s]?\d/i.test(t))
      return findSrc('form', 'drc', 'rfd', 'pmt') || sources[0];

    // 7. Broad GST-specific signal → link to highest-ranked retrieved source
    //    (conservative list — avoids generic headers like "LEGAL PROVISIONS")
    if (/\b(?:cgst|igst|sgst|utgst|gstr|itc\b|lut\b|rcm\b|aar\b|hsn\b|sac\b|zero.?rated|reverse.?charge|input.?tax|annual.?return|reconciliation|e-?way)\b/i.test(t))
      return sources[0];

    return null; // generic phrase — leave unlinked
  };

  // ── PHASE 1: Bold text ────────────────────────────────────────────────────
  // Match **bold** that does NOT span newlines or contain placeholder sentinels.
  // Limit to 150 chars so we don't accidentally swallow large blocks.
  safe = safe.replace(/\*\*([^*\x00\n]{2,150})\*\*/g, (match, inner) => {
    const src = findSrcForBold(inner);
    if (!src?.url) return match;
    return shield(`[${match}](${src.url})`); // e.g. [**GSTR-9C**](url)
  });

  // ── PHASE 2: Plain-text legal references (not bold, not already linked) ──
  // Every replacement falls back to sources[0] so there is always a link target.

  // CBIC Circular No. 76/50/2018
  safe = safe.replace(/\b(?:CBIC\s+)?Circular\s+No\.?\s*\d+\/\d+\/\d{4}\b/gi,
    m => wrap(m, findSrc('circular') || sources[0]));

  // Notification No. 13/2017-CT
  safe = safe.replace(/\bNotification\s+No\.?\s*\d+\/\d{4}[-\w]*/gi,
    m => wrap(m, findSrc('notification', 'circular') || sources[0]));

  // Section 47, Section 16(2)(c)
  safe = safe.replace(/\bSection\s+\d+[A-Z]?(?:\(\d+[A-Za-z]?\))*/g,
    m => wrap(m, findSrc('act', 'cgst', 'igst', 'gst') || sources[0]));

  // Rule 42, Rule 36(4)
  safe = safe.replace(/\bRule\s+\d+(?:\(\d+\))*/g,
    m => wrap(m, findSrc('rule', 'rules') || sources[0]));

  // GSTR Forms (plain text)
  safe = safe.replace(/\bGSTR[-‑]?\d+[A-Z]?\b/gi, m => {
    const norm = m.replace(/[-‑\s]/g, '').toLowerCase();
    return wrap(m,
      sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s%20]/g, '').includes(norm)) ||
      findSrc('gstr', 'form', 'return') || sources[0]);
  });

  // GST Acts (plain text)
  safe = safe.replace(/\b(?:C|I|S|UT)?GST\s+Act(?:,?\s*\d{4})?\b/gi, m =>
    wrap(m, findSrc('act', 'bare law', 'cgst', 'igst') || sources[0]));

  // Form codes (plain text): DRC-01, RFD-01A, PMT-06, EWB-01, …
  safe = safe.replace(/\b(?:DRC|RFD|PMT|REG|CMP|ITC|RET|ANX|PCT|EWB)[-\s]?\d+[A-Z]?\b/gi, m => {
    const norm = m.replace(/[-\s]/g, '').toLowerCase();
    return wrap(m,
      sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s]/g, '').includes(norm)) ||
      findSrc('form', 'drc', 'rfd', 'pmt') || sources[0]);
  });

  // Restore all shielded links
  return safe.replace(/\x00LINK(\d+)\x00/g, (_, i) => placeholders[+i]);
}

const LetaResponse = ({ data, isDark = false, animate = true, onDocumentClick, onRegenerate }) => {
  const [citationMode, setCitationMode] = useState(false);
  const [isAdvisoryOpen, setIsAdvisoryOpen] = useState(false);
  const [hasCopied, setHasCopied] = useState(false);

  // Stable ID for the response to satisfy React purity rules (impure to call Math.random during render)
  const responseId = React.useMemo(() => Math.random().toString(36).substr(2, 9).toUpperCase(), []);

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
        className={`rounded-leta border overflow-hidden transition-all duration-300 ${
          isDark 
            ? 'bg-[#F9FAFB] border-leta-gray-200 shadow-none' 
            : 'bg-leta-white shadow-sentinel-blue/5 border-leta-gray-100'
        }`}
      >
        {/* Header Bar */}
        <div className={`px-6 py-3 border-b flex items-center justify-between ${
           isDark ? 'bg-[#FFFFFF] border-leta-gray-200' : 'bg-leta-gray-50 border-leta-gray-100'
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
                className="p-1.5 text-leta-gray-500 hover:text-leta-gray-900 hover:bg-leta-white/10 rounded-leta transition-colors relative group"
                title="Copy Answer"
            >
                {hasCopied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
            </button>
            
            {onRegenerate && (
                <button 
                    onClick={onRegenerate}
                    className="p-1.5 text-leta-gray-500 hover:text-leta-gray-900 hover:bg-sentinel-blue/10 rounded-leta transition-colors"
                    title="Regenerate Answer"
                >
                    <RefreshCw size={14} />
                </button>
            )}
          </div>
        </div>
  
        {/* Content Area */}
        <div className="p-6 md:p-8 bg-[#F9FAFB]">
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
                 isDark ? 'text-leta-gray-300 prose-invert prose-headings:font-mono prose-headings:uppercase prose-strong:text-leta-gray-900 prose-a:text-sentinel-green prose-table:border-leta-gray-200 prose-th:bg-[#FFFFFF] prose-td:border-leta-gray-200' : 'text-leta-gray-700'
              }`}>
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: (props) => <h1 className="text-xl font-bold mt-6 mb-4" {...props} />,
                    h2: (props) => <h2 className="text-lg font-bold mt-5 mb-3" {...props} />,
                    h3: (props) => <h3 className="text-base font-bold mt-4 mb-2" {...props} />,
                    ul: (props) => <ul className="list-disc list-outside ml-5 mb-4 space-y-2" {...props} />,
                    ol: (props) => <ol className="list-decimal list-outside ml-5 mb-4 space-y-2" {...props} />,
                    li: (props) => <li className="pl-1" {...props} />,
                    p: (props) => <p className="mb-4" {...props} />,
                    strong: (props) => <strong className="font-bold text-sentinel-green dark:text-sentinel-green" {...props} />,
                    table: (props) => <div className="overflow-x-auto my-6"><table className="min-w-full text-sm font-mono border border-leta-gray-200 rounded-leta" {...props} /></div>,
                    thead: (props) => <thead className="bg-[#FFFFFF] border-b border-leta-gray-200 text-leta-gray-900" {...props} />,
                    th: (props) => <th className="px-4 py-3 text-left font-bold" {...props} />,
                    td: (props) => <td className="px-4 py-3 border-b border-leta-gray-100 bg-[#F9FAFB]" {...props} />,
                    a: (props) => {
                      const isDocLink = props.href && props.href.includes('/api/documents/view');

                      const openInViewer = (href, linkText) => {
                        let baseUrl = href;
                        let page = null;
                        let search = null;

                        if (href.includes('#')) {
                          const parts = href.split('#');
                          baseUrl = parts[0];
                          const hashParams = new URLSearchParams(parts[1]);
                          if (hashParams.has('page')) page = hashParams.get('page');
                          if (hashParams.has('search')) search = hashParams.get('search');
                        }

                        if (baseUrl.startsWith('/api/')) baseUrl = BASE_URL + baseUrl;

                        const urlTitle = (() => { try { return decodeURIComponent(baseUrl.split('filename=')[1]?.split('&')[0] || ''); } catch { return ''; } })();
                        const docTitle = (linkText && !linkText.startsWith('http')) ? linkText : urlTitle || 'Document';
                        onDocumentClick({ url: baseUrl, page, search, title: docTitle });
                      };

                      return (
                        <a
                          {...props}
                          target={isDocLink ? undefined : "_blank"}
                          rel="noopener noreferrer"
                          className="text-sentinel-green hover:text-leta-gray-900 font-mono font-bold underline cursor-pointer transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            const linkText = props.children?.toString?.() || '';

                            if (isDocLink && onDocumentClick) {
                              e.preventDefault();
                              openInViewer(props.href, linkText);
                              return;
                            }

                            // Intercept external legal-reference links when sources are available:
                            // rather than opening a new tab, open the best matching source in the viewer.
                            if (onDocumentClick && data?.consulted_sources?.length > 0 &&
                                /section|rule|gstr|act|notification|circular|itc|lut|rcm/i.test(linkText)) {
                              e.preventDefault();
                              const src = data.consulted_sources[0];
                              openInViewer(BASE_URL + src.url, linkText);
                            }
                          }}
                        />
                      );
                    },
                  }}
                >
                  {linkifyLegalRefs(data?.answer || '', data?.consulted_sources)}
                </ReactMarkdown>
              </div>
              
              {/* ADVISORY CTA */}
              <div className="mt-8 pt-6 border-t border-leta-gray-200 flex justify-end">
                  <button 
                    onClick={() => setIsAdvisoryOpen(true)}
                    className="group flex items-center gap-3 px-5 py-2.5 bg-sentinel-blue/10 border border-sentinel-blue/30 text-leta-gray-900 hover:bg-sentinel-blue hover:text-leta-gray-900 transition-all rounded-leta"
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
             ? 'bg-[#FFFFFF] border-leta-gray-200 text-leta-gray-600' 
             : 'bg-sentinel-blue/5 border-sentinel-blue/10 text-leta-gray-900/60'
        }`}>
          <span>GENERATED_BY_SENTINEL.AI_ENGINE</span>
          <span>ID: {data && responseId}</span>
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
