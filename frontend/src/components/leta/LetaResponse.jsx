import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { BASE_URL } from '../../config/api';
import { ShieldCheck, Copy, Check, RefreshCw, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ThinkingSources from './ThinkingSources';

// ─── helpers ──────────────────────────────────────────────────────────────────

/** Normalise a filename for loose matching (no ext, lower, collapse separators). */
function normTitle(str) {
  return (str || '')
    .toLowerCase()
    .replace(/\.[a-z]{2,5}$/, '')           // strip extension
    .replace(/[_+%20\s-]+/g, ' ')           // collapse separators
    .trim();
}

/**
 * Find the best source for a piece of text by trying keyword matching
 * against actual source titles, then falling back to category keywords.
 */
function findBestSrc(text, sources, ...categoryKws) {
  const t = text.toLowerCase();

  // 1. Direct title match — prefer source whose normalised title overlaps most
  let best = null;
  let bestScore = 0;
  for (const s of sources) {
    const nt = normTitle(s.title);
    const words = nt.split(' ').filter(w => w.length > 3);
    const hits = words.filter(w => t.includes(w)).length;
    if (hits > bestScore) { bestScore = hits; best = s; }
  }
  if (bestScore >= 2) return best;

  // 2. Category keywords fallback
  if (categoryKws.length) {
    const found = sources.find(s => {
      const hay = (s.title || s.url || '').toLowerCase();
      return categoryKws.some(kw => hay.includes(kw.toLowerCase()));
    });
    if (found) return found;
  }

  return null;
}

/**
 * Turn legal references in the markdown text into clickable links
 * pointing to the most relevant consulted source.
 */
function linkifyLegalRefs(markdown, sources) {
  if (!sources || sources.length === 0 || !markdown) return markdown;

  const placeholders = [];
  const shield = m => { placeholders.push(m); return `\x00LINK${placeholders.length - 1}\x00`; };

  // Preserve existing doc links so we don't double-wrap them.
  // Strip whitespace/newlines from captured URLs — LLMs sometimes wrap long
  // URLs across lines which embeds \n inside the URL, causing CommonMark to
  // reject it as a link and render the raw (url) as plain text.
  let safe = markdown
    // Collapse split links: LLMs sometimes put the URL on a new line after ]
    .replace(/\]\(\s*\n\s*(\/api\/)/g, ']($1')       // handles ](\n/api/
    .replace(/\]\s*\n+\s*\((?=\s*\/api\/)/g, '](')   // handles ]\n(/api/
    // Process all [text](url) patterns
    .replace(/\[([^\]]*)\]\(([^)]+)\)/g, (match, text, url) => {
      const cleanUrl = url.replace(/\s+/g, ''); // strip embedded whitespace/newlines
      if (cleanUrl.includes('/api/documents/')) return shield(`[${text}](${cleanUrl})`);
      return text;           // strip non-doc markdown links to plain text
    });

  const wrap = (text, src) => (src?.url ? `[${text}](${src.url})` : text);

  // ── Specific document pattern helpers ─────────────────────────────────────
  const findSrc = (...kws) =>
    sources.find(s => { const h = (s.title || s.url || '').toLowerCase(); return kws.some(k => h.includes(k)); });

  // ── 0. SOURCE FILENAME HYPERLINKS — runs first, highest priority ──────────
  // Wraps every occurrence of a source's actual filename (with and without extension)
  // in the text into a clickable link that opens the document in the sidebar.
  // Handles **bold** occurrences (e.g. **CGST ACT.docx**) and plain text.
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  for (const src of sources) {
    if (!src?.url || !src?.title) continue;
    const rawName = decodeURIComponent(src.title).replace(/%20/g, ' ').trim();
    const nameNoExt = rawName.replace(/\.[a-z]{2,5}$/i, '').trim();
    if (rawName.length < 5) continue;

    // Bold occurrences: **filename.pdf** or **filename** → [**filename**](url)
    for (const candidate of [rawName, nameNoExt]) {
      if (candidate.length < 5) continue;
      const boldPat = new RegExp(`\\*\\*(${esc(candidate)})\\*\\*`, 'gi');
      safe = safe.replace(boldPat, (_, inner) =>
        shield(`[**${inner}**](${src.url})`)
      );
    }

    // Plain occurrences (not already inside a link or placeholder)
    const plainPat = new RegExp(`(?<![\\[\\(\x00])\\b(${esc(rawName)})`, 'gi');
    safe = safe.replace(plainPat, (_, inner) => shield(wrap(inner, src)));
  }

  // ── 1. Source [N] / [Source N] numbered citations from the LLM ──────────
  safe = safe.replace(/\[?(?:Source|source|Src)\s*\[?(\d+)\]?\]?/g, (match, numStr) => {
    const idx = parseInt(numStr, 10) - 1; // LLM uses 1-based index
    // Map to nearest source in the 0-7 range
    const src = sources[Math.min(Math.max(idx, 0), sources.length - 1)];
    if (!src?.url) return match;
    const label = (src.title || 'Document').replace(/%20/g, ' ').replace(/\.[a-z]{2,5}$/i, '');
    return shield(`[📄 ${label}](${src.url})`);
  });

  // ── 1b. Case-law citations: "XYZ vs ABC" or "XYZ v. ABC" ─────────────
  safe = safe.replace(
    /\b([A-Z][A-Za-z./&\s]{2,60?}?)\s+(?:v\.?s?\.?|versus)\s+([A-Za-z][A-Za-z./&\s]{2,60?}?)(?=[,;:()\n]|$)/g,
    (match) => {
      const src = findBestSrc(match, sources) || findSrc('court', 'aar', 'judgment', 'ruling', 'appeal');
      return src ? shield(wrap(match, src)) : match;
    }
  );

  // ── 2. Specific CBIC Circulars: "Circular No. 228/2024" ──────────────────
  safe = safe.replace(/\b(?:CBIC\s+)?Circular\s+No\.?\s*(\d+)[/\-](\d+)(?:[/\-]\w+)?\b/gi, (match, num) => {
    const src =
      sources.find(s => (s.title || '').toLowerCase().includes(num)) ||
      findSrc('circular');
    return wrap(match, src);  // no fallback to sources[0] — unlink if no circular found
  });

  // ── 3. Notifications: "Notification No. 12/2023" ─────────────────────────
  safe = safe.replace(/\bNotification\s+No\.?\s*\d+\/\d{4}[-\w]*/gi, m =>
    wrap(m, findSrc('notification', 'circular'))  // no sources[0] fallback
  );

  // ── 4. Sections: "Section 17(5)(c)" — handles any number of sub-clauses ──
  safe = safe.replace(/\bSection\s+\d+[A-Z]?(?:\([^)]{1,10}\))*/g, m =>
    wrap(m, findSrc('act', 'cgst', 'igst', 'gst', 'rules'))  // no sources[0] fallback
  );

  // ── 5. Rules: "Rule 86A" ─────────────────────────────────────────────────
  safe = safe.replace(/\bRule\s+\d+[A-Z]?(?:\(\d+\))*/g, m =>
    wrap(m, findSrc('rule', 'rules', 'cgst rules', 'igst rules'))  // no sources[0] fallback
  );

  // ── 6. GSTR forms: "GSTR-3B", "GSTR 9C" ─────────────────────────────────
  safe = safe.replace(/\bGSTR[-‑]?\d+[A-Z]?\b/gi, m => {
    const norm = m.replace(/[-‑\s]/g, '').toLowerCase();
    return wrap(
      m,
      sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s%20]/g, '').includes(norm)) ||
      findSrc('gstr', 'form', 'return')
      // no sources[0] fallback
    );
  });

  // ── 7. GST Act references ─────────────────────────────────────────────────
  safe = safe.replace(/\b(?:C|I|S|UT)?GST\s+Act(?:,?\s*\d{4})?\b/gi, m =>
    wrap(m, findSrc('act', 'bare law', 'cgst', 'igst'))  // no sources[0] fallback
  );

  // ── 8. Form codes: "DRC-01", "RFD-09", "PMT-06" ─────────────────────────
  safe = safe.replace(/\b(?:DRC|RFD|PMT|REG|CMP|ITC|RET|ANX|PCT|EWB|SPL)[-\s]?\d+[A-Z]?\b/gi, m => {
    const norm = m.replace(/[-\s]/g, '').toLowerCase();
    return wrap(
      m,
      sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s]/g, '').includes(norm)) ||
      findSrc('form', 'drc', 'rfd', 'pmt')
      // no sources[0] fallback
    );
  });

  // ── 9. Bold legal terms (broad sweep) ────────────────────────────────────
  safe = safe.replace(/\*\*([^*\x00\n]{2,150})\*\*/g, (match, inner) => {
    const t = inner.toLowerCase();
    const gstrM = t.match(/gstr[-‑]?(\d+[a-z]?)/i);
    if (gstrM) {
      const norm = 'gstr' + gstrM[1].replace(/[-‑]/g, '');
      const src =
        sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s%20]/g, '').includes(norm)) ||
        findSrc('gstr', 'form', 'return') ||
        sources[0];
      return src?.url ? shield(`[${match}](${src.url})`) : match;
    }
    if (/(?:c|i|s|ut)?gst\s+act/i.test(t)) {
      const src = findSrc('act', 'bare law', 'cgst', 'igst') || sources[0];
      return src?.url ? shield(`[${match}](${src.url})`) : match;
    }
    if (/section\s+\d/i.test(t)) {
      const src = findSrc('act', 'cgst', 'igst', 'gst') || sources[0];
      return src?.url ? shield(`[${match}](${src.url})`) : match;
    }
    if (/circular\s+no/i.test(t)) {
      const src = findSrc('circular') || sources[0];
      return src?.url ? shield(`[${match}](${src.url})`) : match;
    }
    return match;
  });

  // Restore shielded placeholders
  return safe.replace(/\x00LINK(\d+)\x00/g, (_, i) => placeholders[+i]);
}

// ─── component ────────────────────────────────────────────────────────────────

const LetaResponse = ({ data, isDark = false, animate = true, onDocumentClick, onRegenerate, isStreaming = false }) => {
  const [hasCopied, setHasCopied] = useState(false);

  const responseId = React.useMemo(() => Math.random().toString(36).substr(2, 9).toUpperCase(), []);

  const handleCopy = () => {
    if (!data?.answer) return;
    navigator.clipboard.writeText(data.answer);
    setHasCopied(true);
    setTimeout(() => setHasCopied(false), 2000);
  };

  if (!data) return null;

  const sources = data.consulted_sources || [];

  // Skip heavy linkification during streaming — only process once complete
  const processedContent = React.useMemo(() => {
    if (isStreaming) return data?.answer || '';
    return linkifyLegalRefs(data?.answer || '', sources)
      // Remove orphaned (/api/...) URLs not part of a markdown link
      .replace(/(?<!\])\(\/api\/[^()\s)]+\)/g, '')
      // Remove naked [text] brackets left when their URL was stripped
      .replace(/\[([^\]\x00]{1,300})\](?!\()/g, '$1');
  }, [data?.answer, isStreaming, sources.length]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Open a source document in the right-panel viewer. */
  const openDoc = (src) => {
    if (!onDocumentClick) return;
    const cleanTitle = (src.title || 'Document').replace(/%20/g, ' ');
    let url = src.url || '';
    if (url.startsWith('/api/')) url = BASE_URL + url;
    onDocumentClick({ url, page: src.page, title: cleanTitle });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl overflow-hidden"
      style={{ background: '#000000', border: '1px solid rgba(79,183,197,0.15)' }}
    >
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div
        className="px-5 py-3 flex items-center justify-between"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(103,232,249,0.05)' }}
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

      {/* ── Body ─────────────────────────────────────────────────────────── */}
      <div className="p-6 md:p-8">
        {/* Thinking / sources panel (collapsible, shown during + after streaming) */}
        {(sources.length > 0 || data.status) && (
          <ThinkingSources
            sources={sources}
            status={data.status}
            onDocumentClick={onDocumentClick}
          />
        )}

        {/* Main answer — body: Times New Roman, headings: Bookman Old Style */}
        <div
          className="prose prose-sm md:prose-base max-w-none leading-relaxed"
          style={{ color: '#CBD5E1', fontFamily: "'Times New Roman', Times, serif" }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: p => <h1 className="text-xl font-bold mt-6 mb-4 text-white" style={{ fontFamily: "'Bookman Old Style', 'Book Antiqua', 'Palatino Linotype', serif" }} {...p} />,
              h2: p => <h2 className="text-lg font-bold mt-5 mb-3 text-white" style={{ fontFamily: "'Bookman Old Style', 'Book Antiqua', 'Palatino Linotype', serif" }} {...p} />,
              h3: p => <h3 className="text-base font-bold mt-4 mb-2 text-white" style={{ fontFamily: "'Bookman Old Style', 'Book Antiqua', 'Palatino Linotype', serif" }} {...p} />,
              ul: p => <ul className="list-disc list-outside ml-5 mb-4 space-y-2" {...p} />,
              ol: p => <ol className="list-decimal list-outside ml-5 mb-4 space-y-2" {...p} />,
              li: p => <li className="pl-1" style={{ color: '#CBD5E1', fontFamily: "'Times New Roman', Times, serif" }} {...p} />,
              p:  p => <p className="mb-4" style={{ color: '#CBD5E1', fontFamily: "'Times New Roman', Times, serif" }} {...p} />,
              strong: p => <strong className="font-bold" style={{ color: '#67E8F9' }} {...p} />,
              table: p => (
                <div className="overflow-x-auto my-6">
                  <table className="min-w-full text-sm font-mono" style={{ border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px' }} {...p} />
                </div>
              ),
              thead: p => <thead style={{ background: 'rgba(103,232,249,0.08)', borderBottom: '1px solid rgba(255,255,255,0.08)' }} {...p} />,
              th: p => <th className="px-4 py-3 text-left font-bold text-white" {...p} />,
              td: p => <td className="px-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', color: '#CBD5E1' }} {...p} />,
              a: p => {
                const isDocLink = p.href && p.href.includes('/api/documents/');
                const openInViewer = (href, linkText) => {
                  let baseUrl = href;
                  let page = null;
                  let search = null;
                  if (href.includes('#')) {
                    const [base, hash] = href.split('#');
                    baseUrl = base;
                    const hp = new URLSearchParams(hash);
                    if (hp.has('page')) page = hp.get('page');
                    if (hp.has('search')) search = hp.get('search');
                  }
                  if (baseUrl.startsWith('/api/')) baseUrl = BASE_URL + baseUrl;
                  const urlTitle = (() => { try { return decodeURIComponent(baseUrl.split('filename=')[1]?.split('&')[0] || ''); } catch { return ''; } })();
                  const docTitle = (linkText && !linkText.startsWith('http')) ? linkText : urlTitle || 'Document';
                  if (onDocumentClick) onDocumentClick({ url: baseUrl, page, search, title: docTitle });
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
                      if (onDocumentClick && sources.length > 0 && /section|rule|gstr|act|notification|circular|itc|lut|rcm/i.test(linkText)) {
                        e.preventDefault();
                        openInViewer(BASE_URL + sources[0].url, linkText);
                      }
                    }}
                  />
                );
              },
            }}
          >
            {processedContent}
          </ReactMarkdown>
          {/* Blinking cursor during active streaming */}
          {isStreaming && (
            <span
              style={{
                display: 'inline-block',
                width: '2px',
                height: '1em',
                background: '#4FB7C5',
                marginLeft: '2px',
                verticalAlign: 'text-bottom',
                animation: 'leta-cursor-blink 0.8s step-end infinite',
              }}
            />
          )}
        </div>

        {/* ── Always-visible Referenced Documents bar ───────────────────── */}
        {sources.length > 0 && (
          <div
            className="mt-6 pt-4"
            style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
          >
            <span
              className="text-[9px] font-mono uppercase tracking-[0.2em] block mb-2.5"
              style={{ color: '#475569' }}
            >
              Referenced Documents &nbsp;·&nbsp; {sources.length} source{sources.length !== 1 ? 's' : ''}
            </span>
            <div className="flex flex-wrap gap-2">
              {sources.map((src, i) => {
                const label = (src.title || 'Document')
                  .replace(/%20/g, ' ')
                  .replace(/\.[a-z]{2,5}$/i, '');
                return (
                  <button
                    key={i}
                    onClick={() => openDoc(src)}
                    title={`Open ${src.title} — page ${src.page || 1}`}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-mono transition-all"
                    style={{
                      background: 'rgba(103,232,249,0.05)',
                      border: '1px solid rgba(103,232,249,0.15)',
                      color: '#94A3B8',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = 'rgba(103,232,249,0.5)';
                      e.currentTarget.style.background = 'rgba(103,232,249,0.12)';
                      e.currentTarget.style.color = '#67E8F9';
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'rgba(103,232,249,0.15)';
                      e.currentTarget.style.background = 'rgba(103,232,249,0.05)';
                      e.currentTarget.style.color = '#94A3B8';
                    }}
                  >
                    <FileText size={10} />
                    <span className="max-w-[180px] truncate">{label}</span>
                    {src.page && src.page > 1 && (
                      <span style={{ color: '#475569' }}>p.{src.page}</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <div
        className="px-6 py-2 flex justify-between items-center text-[10px] font-mono uppercase tracking-widest"
        style={{ borderTop: '1px solid rgba(255,255,255,0.04)', color: '#2a3050' }}
      >
        <span>GENERATED_BY_LETA.AI_ENGINE</span>
        <span>ID: {responseId}</span>
      </div>
    </motion.div>
  );
};

export default LetaResponse;
