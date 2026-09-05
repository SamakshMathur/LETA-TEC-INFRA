import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { BASE_URL } from '../../config/api';
import { ShieldCheck, Copy, Check, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
 * Replace inline (Sn) citation markers with real document links.
 *
 * Returns the shielded text plus the list of real links it stands for —
 * NOT the links inline. linkifyLegalRefs (called right after this, on the
 * shielded text) unconditionally strips every markdown link it finds
 * before doing its own separate keyword-based relinking pass, on the
 * assumption that any link already in the text is stale noise to
 * flatten and re-derive. That's correct for text this function never
 * touched, but it was also destroying these citation-map-verified links
 * — the most precise ones available, resolved from real retrieved
 * chunks — the moment they were created. The caller restores them from
 * `placeholders` only after linkifyLegalRefs (and its own trailing
 * bracket cleanup) have both run.
 */
function applyCitationMarkers(text, citationMap) {
  const placeholders = [];
  if (!citationMap || citationMap.length === 0 || !text) return { text, placeholders };

  // Same Private Use Area sentinel linkifyLegalRefs uses for its own
  // shielding below, with a distinct token name (CITE vs LINK) so the
  // two restoration passes never collide.
  const CITE_SENTINEL = '';

  const lookup = {};
  for (const entry of citationMap) {
    const num = String(entry.marker || '').replace(/[^0-9]/g, '');
    if (num) lookup[num] = entry;
  }

  const shielded = text.replace(/\(S(\d+)\)/g, (match, num) => {
    const entry = lookup[num];
    if (!entry || !entry.url) return match;
    const label = (entry.title || 'Source')
      .replace(/%20/g, ' ')
      .replace(/\.[a-z]{2,5}$/i, '')
      .trim();
    const pageAnchor = entry.page ? `#page=${entry.page}` : '';
    placeholders.push(`[📄 ${label}](${entry.url}${pageAnchor})`);
    // Same Private Use Area sentinel linkifyLegalRefs uses for its own
    // shielding below, with a distinct token name (CITE vs LINK) so the
    // two restoration passes never collide.
    return `CITE${placeholders.length - 1}`;
  });

  return { text: shielded, placeholders };
}

/**
 * Turn legal references in the markdown text into clickable links.
 */
function linkifyLegalRefs(markdown, sources) {
  if (!sources || sources.length === 0 || !markdown) return markdown;

  const placeholders = [];
  // Sentinel marking a placeholder's boundaries while later regex passes
  // run over `safe`. A Private Use Area code point (never appears in real
  // legal text, and unlike \x00 isn't flagged as a "control character" by
  // static regex analysis) — same delimiter role, just a safer glyph.
  const SENTINEL = '';
  const shield = m => { placeholders.push(m); return `${SENTINEL}LINK${placeholders.length - 1}${SENTINEL}`; };

  let safe = markdown
    .replace(/\[([^\]]*)\]\s*\(\/api\/[\s\S]*?\)/g, '$1')
    .replace(/\]\s*\(\/api\/[\s\S]*?\)/g, ']')
    .replace(/(?<!\])\(\/api\/[\s\S]*?\)/g, '')
    .replace(/\[([^\]]*)\]\(([^)]+)\)/g, (match, text) => text);

  const wrap = (text, src) => (src?.url ? `[${text}](${src.url})` : text);

  const findSrc = (...kws) =>
    sources.find(s => { const h = (s.title || s.url || '').toLowerCase(); return kws.some(k => h.includes(k)); });

  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  for (const src of sources) {
    if (!src?.url || !src?.title) continue;
    const rawName = (() => { try { return decodeURIComponent(src.title); } catch { return src.title; } })().replace(/%20/g, ' ').trim();
    const nameNoExt = rawName.replace(/\.[a-z]{2,5}$/i, '').trim();
    if (rawName.length < 5) continue;

    for (const candidate of [rawName, nameNoExt]) {
      if (candidate.length < 5) continue;
      const boldPat = new RegExp(`\\*\\*(${esc(candidate)})\\*\\*`, 'gi');
      safe = safe.replace(boldPat, (_, inner) => shield(`[**${inner}**](${src.url})`));
    }

    const plainPat = new RegExp(`(?<![\\[\\(${SENTINEL}])\\b(${esc(rawName)})`, 'gi');
    safe = safe.replace(plainPat, (_, inner) => shield(wrap(inner, src)));
  }

  safe = safe.replace(/\[?(?:Source|source|Src)\s*\[?(\d+)\]?\]?/g, (match, numStr) => {
    const idx = parseInt(numStr, 10) - 1;
    const src = sources[Math.min(Math.max(idx, 0), sources.length - 1)];
    if (!src?.url) return match;
    const label = (src.title || 'Document').replace(/%20/g, ' ').replace(/\.[a-z]{2,5}$/i, '');
    return shield(`[📄 ${label}](${src.url})`);
  });

  safe = safe.replace(
    /\b([A-Z][A-Za-z./&\s]{2,60?}?)\s+(?:v\.?s?\.?|versus)\s+([A-Za-z][A-Za-z./&\s]{2,60?}?)(?=[,;:()\n]|$)/g,
    (match) => {
      const src = findBestSrc(match, sources) || findSrc('court', 'aar', 'judgment', 'ruling', 'appeal');
      return src ? shield(wrap(match, src)) : match;
    }
  );

  safe = safe.replace(/\b(?:CBIC\s+)?Circular\s+No\.?\s*(\d+)[/-](\d+)(?:[/-]\w+)?\b/gi, (match, num) => {
    const src = sources.find(s => (s.title || '').toLowerCase().includes(num)) || findSrc('circular');
    return wrap(match, src);
  });

  safe = safe.replace(/\bNotification\s+No\.?\s*\d+\/\d{4}[-\w]*/gi, m =>
    wrap(m, findSrc('notification', 'circular'))
  );

  safe = safe.replace(/\bSection\s+\d+[A-Z]?(?:\([^)]{1,10}\))*/g, m =>
    wrap(m, findSrc('act', 'cgst', 'igst', 'gst', 'rules'))
  );

  safe = safe.replace(/\bRule\s+\d+[A-Z]?(?:\(\d+\))*/g, m =>
    wrap(m, findSrc('rule', 'rules', 'cgst rules', 'igst rules'))
  );

  safe = safe.replace(/\bGSTR[-‑]?\d+[A-Z]?\b/gi, m => {
    const norm = m.replace(/[-‑\s]/g, '').toLowerCase();
    return wrap(
      m,
      sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s%20]/g, '').includes(norm)) ||
      findSrc('gstr', 'form', 'return')
    );
  });

  safe = safe.replace(/\b(?:C|I|S|UT)?GST\s+Act(?:,?\s*\d{4})?\b/gi, m =>
    wrap(m, findSrc('act', 'bare law', 'cgst', 'igst'))
  );

  safe = safe.replace(/\b(?:DRC|RFD|PMT|REG|CMP|ITC|RET|ANX|PCT|EWB|SPL)[-\s]?\d+[A-Z]?\b/gi, m => {
    const norm = m.replace(/[-\s]/g, '').toLowerCase();
    return wrap(
      m,
      sources.find(s => (s.title || s.url || '').toLowerCase().replace(/[_\-.\s]/g, '').includes(norm)) ||
      findSrc('form', 'drc', 'rfd', 'pmt')
    );
  });

  safe = safe.replace(/\*\*([^*\n]{2,150})\*\*/g, (match, inner) => {
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

  return safe.replace(/LINK(\d+)/g, (_, i) => placeholders[+i]);
}

// ─── component ────────────────────────────────────────────────────────────────

const LetaResponse = ({ data, isDark: _isDark = false, animate: _animate = true, onDocumentClick, onRegenerate, isStreaming = false }) => {
  const [hasCopied, setHasCopied] = useState(false);
  const [actionsVisible, setActionsVisible] = useState(false);

  // Generated once, by the caller, at the moment this message is created
  // (see handleAsk in LetaWorkspace.tsx) — not here. Render must stay free
  // of side effects/randomness entirely; a ref-guarded Math.random() still
  // has the call reachable from render and fails a strict lint rule for
  // exactly that reason. 'PENDING' only shows for the streaming instant
  // before the caller's ID has propagated through props.
  const responseId = data?.responseId || 'PENDING';

  // Hooks must run unconditionally on every render (rules-of-hooks). This
  // used to sit after the `if (!data) return null` early return below,
  // which is an illegal conditional hook call on the very first render of
  // a fresh placeholder message (data is momentarily undefined). Guard
  // internally instead of gating the hook call itself; behavior is
  // unchanged — computes the same processed markdown once `data.answer`
  // exists.
  const processedContent = React.useMemo(() => {
    if (!data?.answer) return '';
    if (isStreaming) return data.answer;
    const { text: withMarkers, placeholders: citationPlaceholders } = applyCitationMarkers(data.answer, data.citationMap);
    const memoSources = data.consulted_sources || [];
    let out = linkifyLegalRefs(withMarkers, memoSources)
      .replace(/(?<!\])\(\/api\/[^()\s)]+\)/g, '')
      .replace(/\[([^\]]{1,300})\](?!\()/g, '$1');
    // Restore citation-map links only now, after linkifyLegalRefs's own
    // stripping/relinking pass and the trailing bracket cleanup above —
    // see the comment on applyCitationMarkers for why.
    if (citationPlaceholders.length) {
      const CITE_SENTINEL = String.fromCharCode(0xE000);
      const restorePattern = new RegExp(CITE_SENTINEL + 'CITE(\\d+)' + CITE_SENTINEL, 'g');
      out = out.replace(restorePattern, (_, i) => citationPlaceholders[+i]);
    }
    return out;
  }, [data, isStreaming]);

  const handleCopy = () => {
    if (!data?.answer) return;
    navigator.clipboard.writeText(data.answer);
    setHasCopied(true);
    setTimeout(() => setHasCopied(false), 2000);
  };

  if (!data) return null;

  const sources = data.consulted_sources || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="relative w-full"
      onMouseEnter={() => setActionsVisible(true)}
      onMouseLeave={() => setActionsVisible(false)}
    >
      {/* ── Thinking / loading state ─────────────────────────────────────── */}
      {/* Deliberately just dots + a status line — no staged pipeline rail.
          The rail (Init/Cache/Retrieve/Rerank/Generate, dots + connecting
          lines) read as a technical dashboard instead of a calm "thinking"
          moment; ChatGPT/Claude's own loaders are exactly this restrained.
          The status text is kept — real transparency into what LETA is
          doing that those products don't even offer — it's the dots that
          needed to stay minimal, not the information. */}
      {!data?.answer && (
        <div className="flex items-center gap-3 py-2">
          <div className="flex gap-1.5">
            {[0, 150, 300].map(delay => (
              <span
                key={delay}
                style={{
                  display: 'inline-block',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: '#67E8F9',
                  animation: `leta-thinking-bounce 1.1s ease-in-out ${delay}ms infinite`,
                  opacity: 0.85,
                }}
              />
            ))}
          </div>
          <span
            key={data?.status}
            style={{
              fontFamily: 'monospace',
              fontSize: '11px',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: '#67E8F9',
              opacity: 0.9,
              animation: 'leta-status-fade 0.35s ease',
            }}
          >
            {data?.status || 'Initializing Statutory Analyzer...'}
          </span>
        </div>
      )}

      {/* ── Answer body ──────────────────────────────────────────────────── */}
      {data?.answer && (
        <>
          {/* Floating action bar — appears on hover, top-right of the answer */}
          <motion.div
            initial={false}
            animate={{ opacity: actionsVisible ? 1 : 0, y: actionsVisible ? 0 : -4 }}
            transition={{ duration: 0.15 }}
            className="absolute top-0 right-0 flex items-center gap-1 z-10"
            style={{ pointerEvents: actionsVisible ? 'auto' : 'none' }}
          >
            {/* LETA badge */}
            <div
              className="flex items-center gap-1.5 px-2 py-1 rounded-md"
              style={{ background: 'rgba(103,232,249,0.06)', border: '1px solid rgba(103,232,249,0.12)' }}
            >
              <ShieldCheck size={10} style={{ color: '#67E8F9' }} />
              <span className="font-mono text-[9px] font-bold tracking-widest uppercase" style={{ color: '#4FB7C5' }}>
                LETA
              </span>
            </div>

            {/* Copy */}
            <button
              onClick={handleCopy}
              className="p-1.5 rounded-md transition-all"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.07)',
                color: hasCopied ? '#22C55E' : '#64748B',
              }}
              onMouseEnter={e => { e.currentTarget.style.color = '#CBD5E1'; e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = hasCopied ? '#22C55E' : '#64748B'; e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; }}
              title="Copy answer"
            >
              {hasCopied ? <Check size={12} /> : <Copy size={12} />}
            </button>

            {/* Regenerate */}
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                className="p-1.5 rounded-md transition-all"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.07)',
                  color: '#64748B',
                }}
                onMouseEnter={e => { e.currentTarget.style.color = '#CBD5E1'; e.currentTarget.style.background = 'rgba(255,255,255,0.08)'; }}
                onMouseLeave={e => { e.currentTarget.style.color = '#64748B'; e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; }}
                title="Regenerate"
              >
                <RefreshCw size={12} />
              </button>
            )}
          </motion.div>

          {/* Content — no box, flows naturally */}
          <div
            className="prose prose-sm md:prose-base max-w-none leading-relaxed pt-1"
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
                  if (p.href && p.href.includes('view_by_path')) {
                    return <>{p.children}</>;
                  }
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

            {/* Blinking cursor during streaming */}
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

          {/* Minimal ID watermark — only visible on hover */}
          <motion.div
            initial={false}
            animate={{ opacity: actionsVisible ? 1 : 0 }}
            transition={{ duration: 0.2 }}
            className="mt-4 flex items-center gap-2"
            style={{ pointerEvents: 'none' }}
          >
            <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.04)' }} />
            <span className="font-mono text-[9px] tracking-widest uppercase" style={{ color: 'rgba(42,48,80,0.8)' }}>
              ID: {responseId}
            </span>
          </motion.div>
        </>
      )}
    </motion.div>
  );
};

export default LetaResponse;
