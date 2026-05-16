import React, { useState } from 'react';
import { motion } from 'framer-motion';
import ConfidenceBadge from './ConfidenceBadge';
import CitationList from './CitationList';
import LetaExplainability from './LetaExplainability';
import { BASE_URL } from '../../config/api';
import { ShieldCheck, Copy, Check, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ThinkingSources from './ThinkingSources';

function linkifyLegalRefs(markdown, sources) {
  if (!sources || sources.length === 0 || !markdown) return markdown;

  const findSrc = (...keywords) =>
    sources.find(s => {
      const hay = (s.title || s.url || '').toLowerCase();
      return keywords.some(kw => hay.includes(kw.toLowerCase()));
    });

  const placeholders = [];
  const shield = m => { placeholders.push(m); return `\x00LINK${placeholders.length - 1}\x00`; };

  let safe = markdown.replace(/\[([^\]]*)\]\(([^)]+)\)/g, (match, text, url) => {
    if (url.includes('/api/documents/view')) return shield(match);
    return text;
  });

  const wrap = (text, src) => (src?.url ? `[${text}](${src.url})` : text);

  const findSrcForBold = text => {
    const t = text.toLowerCase();
    const gstrM = t.match(/gstr[-‑]?(\d+[a-z]?)/i);
    if (gstrM) {
      const norm = 'gstr' + gstrM[1].replace(/[-‑]/g, '');
      return (
        sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s%20]/g, '').includes(norm)) ||
        findSrc('gstr', 'form', 'return') || sources[0]
      );
    }
    if (/(?:c|i|s|ut)?gst\s+act/i.test(t)) return findSrc('act', 'bare law', 'cgst', 'igst') || sources[0];
    if (/section\s+\d/i.test(t)) return findSrc('act', 'cgst', 'igst', 'gst') || sources[0];
    if (/rule\s+\d/i.test(t)) return findSrc('rule', 'rules') || sources[0];
    if (/notification\s+no/i.test(t)) return findSrc('notification', 'circular') || sources[0];
    if (/circular\s+no/i.test(t)) return findSrc('circular') || sources[0];
    if (/\b(?:drc|rfd|pmt|reg|cmp|ewb)[-‑\s]?\d/i.test(t)) return findSrc('form', 'drc', 'rfd', 'pmt') || sources[0];
    if (/\b(?:cgst|igst|sgst|utgst|gstr|itc\b|lut\b|rcm\b|aar\b|hsn\b|sac\b|zero.?rated|reverse.?charge|input.?tax|annual.?return|reconciliation|e-?way)\b/i.test(t)) return sources[0];
    return null;
  };

  safe = safe.replace(/\*\*([^*\x00\n]{2,150})\*\*/g, (match, inner) => {
    const src = findSrcForBold(inner);
    if (!src?.url) return match;
    return shield(`[${match}](${src.url})`);
  });

  safe = safe.replace(/\b(?:CBIC\s+)?Circular\s+No\.?\s*\d+\/\d+\/\d{4}\b/gi, m => wrap(m, findSrc('circular') || sources[0]));
  safe = safe.replace(/\bNotification\s+No\.?\s*\d+\/\d{4}[-\w]*/gi, m => wrap(m, findSrc('notification', 'circular') || sources[0]));
  safe = safe.replace(/\bSection\s+\d+[A-Z]?(?:\(\d+[A-Za-z]?\))*/g, m => wrap(m, findSrc('act', 'cgst', 'igst', 'gst') || sources[0]));
  safe = safe.replace(/\bRule\s+\d+(?:\(\d+\))*/g, m => wrap(m, findSrc('rule', 'rules') || sources[0]));
  safe = safe.replace(/\bGSTR[-‑]?\d+[A-Z]?\b/gi, m => {
    const norm = m.replace(/[-‑\s]/g, '').toLowerCase();
    return wrap(m, sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s%20]/g, '').includes(norm)) || findSrc('gstr', 'form', 'return') || sources[0]);
  });
  safe = safe.replace(/\b(?:C|I|S|UT)?GST\s+Act(?:,?\s*\d{4})?\b/gi, m => wrap(m, findSrc('act', 'bare law', 'cgst', 'igst') || sources[0]));
  safe = safe.replace(/\b(?:DRC|RFD|PMT|REG|CMP|ITC|RET|ANX|PCT|EWB)[-\s]?\d+[A-Z]?\b/gi, m => {
    const norm = m.replace(/[-\s]/g, '').toLowerCase();
    return wrap(m, sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s]/g, '').includes(norm)) || findSrc('form', 'drc', 'rfd', 'pmt') || sources[0]);
  });

  return safe.replace(/\x00LINK(\d+)\x00/g, (_, i) => placeholders[+i]);
}

const LetaResponse = ({ data, isDark = false, animate = true, onDocumentClick, onRegenerate }) => {
  const [hasCopied, setHasCopied] = useState(false);

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
        className="rounded-2xl overflow-hidden"
        style={{
          background: '#000000',
          border: '1px solid rgba(79,183,197,0.15)',
        }}
      >
        {/* Header Bar */}
        <div
          className="px-5 py-3 flex items-center justify-between"
          style={{
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            background: 'rgba(103,232,249,0.05)',
          }}
        >
          <div className="flex items-center gap-2">
            <ShieldCheck size={14} style={{ color: '#67E8F9' }} />
            <span className="font-mono text-[10px] font-bold tracking-widest uppercase" style={{ color: '#67E8F9' }}>
              LETA_OUTPUT_V1.0
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="p-1.5 rounded-lg transition-colors"
              style={{ color: '#475569' }}
              onMouseEnter={e => { e.currentTarget.style.color = '#CBD5E1'; e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = '#475569'; e.currentTarget.style.background = 'transparent'; }}
              title="Copy Answer"
            >
              {hasCopied ? <Check size={13} style={{ color: '#22C55E' }} /> : <Copy size={13} />}
            </button>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="p-1.5 rounded-lg transition-colors"
                style={{ color: '#475569' }}
                onMouseEnter={e => { e.currentTarget.style.color = '#CBD5E1'; e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
                onMouseLeave={e => { e.currentTarget.style.color = '#475569'; e.currentTarget.style.background = 'transparent'; }}
                title="Regenerate"
              >
                <RefreshCw size={13} />
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="p-6 md:p-8">
          {(data.consulted_sources?.length > 0 || data.status) && (
            <ThinkingSources
              sources={data.consulted_sources}
              status={data.status}
              onDocumentClick={onDocumentClick}
            />
          )}

          <div className="prose prose-sm md:prose-base max-w-none leading-relaxed"
            style={{ color: '#CBD5E1' }}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: p => <h1 className="text-xl font-bold mt-6 mb-4 text-white" {...p} />,
                h2: p => <h2 className="text-lg font-bold mt-5 mb-3 text-white" {...p} />,
                h3: p => <h3 className="text-base font-bold mt-4 mb-2 text-white" {...p} />,
                ul: p => <ul className="list-disc list-outside ml-5 mb-4 space-y-2" {...p} />,
                ol: p => <ol className="list-decimal list-outside ml-5 mb-4 space-y-2" {...p} />,
                li: p => <li className="pl-1" style={{ color: '#CBD5E1' }} {...p} />,
                p:  p => <p className="mb-4" style={{ color: '#CBD5E1' }} {...p} />,
                strong: p => <strong className="font-bold" style={{ color: '#67E8F9' }} {...p} />,
                table: p => (
                  <div className="overflow-x-auto my-6">
                    <table className="min-w-full text-sm font-mono" style={{ border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px' }} {...p} />
                  </div>
                ),
                thead: p => <thead style={{ background: 'rgba(103,232,249,0.08)', borderBottom: '1px solid rgba(255,255,255,0.08)' }} {...p} />,
                th: p => <th className="px-4 py-3 text-left font-bold text-white" {...p} />,
                td: p => (
                  <td className="px-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', color: '#CBD5E1' }} {...p} />
                ),
                a: p => {
                  const isDocLink = p.href && p.href.includes('/api/documents/view');

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
                      {...p}
                      target={isDocLink ? undefined : '_blank'}
                      rel="noopener noreferrer"
                      className="font-mono font-bold underline cursor-pointer transition-colors"
                      style={{ color: '#67E8F9' }}
                      onMouseEnter={e => { e.currentTarget.style.color = '#22D3EE'; }}
                      onMouseLeave={e => { e.currentTarget.style.color = '#67E8F9'; }}
                      onClick={e => {
                        e.stopPropagation();
                        const linkText = p.children?.toString?.() || '';
                        if (isDocLink && onDocumentClick) { e.preventDefault(); openInViewer(p.href, linkText); return; }
                        if (onDocumentClick && data?.consulted_sources?.length > 0 && /section|rule|gstr|act|notification|circular|itc|lut|rcm/i.test(linkText)) {
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

        </div>

        {/* Footer */}
        <div
          className="px-6 py-2 flex justify-between items-center text-[10px] font-mono uppercase tracking-widest"
          style={{ borderTop: '1px solid rgba(255,255,255,0.04)', color: '#2a3050' }}
        >
          <span>GENERATED_BY_LETA.AI_ENGINE</span>
          <span>ID: {responseId}</span>
        </div>
      </motion.div>

    </>
  );
};

export default LetaResponse;
