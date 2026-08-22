import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Search, Scale } from 'lucide-react';
import LetaResponse from './LetaResponse';
import { BASE_URL } from '../../config/api';

// Step-by-step thinking display for /ask-sync (simulated timing, realistic steps)
const THINKING_STEPS = [
  { msg: 'Initializing Statutory Analyzer...', duration: 1500 },
  { msg: 'Scanning Semantic Cache...', duration: 800 },
  { msg: 'Searching 49,845 Legal Documents...', duration: 3000 },
  { msg: 'Expanding Query for Precision Retrieval...', duration: 2500 },
  { msg: 'Reranking by Legal Authority Weight...', duration: 2000 },
  { msg: 'Synthesizing Sovereign Legal Position...', duration: 99999 }, // stays until done
];

const LetaThinkingLoader = ({ isActive }) => {
  const [stepIdx, setStepIdx] = useState(0);

  useEffect(() => {
    if (!isActive) { setStepIdx(0); return; }
    let idx = 0;
    const advance = () => {
      idx = Math.min(idx + 1, THINKING_STEPS.length - 1);
      setStepIdx(idx);
      if (idx < THINKING_STEPS.length - 1) {
        t = setTimeout(advance, THINKING_STEPS[idx].duration);
      }
    };
    let t = setTimeout(advance, THINKING_STEPS[0].duration);
    return () => clearTimeout(t);
  }, [isActive]);

  if (!isActive) return null;
  const step = THINKING_STEPS[stepIdx];

  return (
    <div className="flex flex-col items-center justify-center py-10 px-6 gap-5">
      {/* Dots + status text */}
      <div className="flex items-center gap-3">
        <div className="flex gap-1.5">
          {[0, 150, 300].map(d => (
            <span key={d} style={{
              display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%',
              background: '#67E8F9',
              animation: `leta-thinking-bounce 1.1s ease-in-out ${d}ms infinite`,
            }} />
          ))}
        </div>
        <span key={step.msg} style={{
          fontFamily: 'monospace', fontSize: '11px', letterSpacing: '0.12em',
          textTransform: 'uppercase', color: '#67E8F9',
          animation: 'leta-status-fade 0.35s ease',
        }}>
          {step.msg}
        </span>
      </div>

      {/* Stage rail */}
      {(() => {
        const stages = ['Init', 'Cache', 'Retrieve', 'Rerank', 'Generate'];
        const active = Math.min(Math.floor(stepIdx * stages.length / THINKING_STEPS.length), stages.length - 1);
        return (
          <div className="flex items-center" style={{ maxWidth: '300px', width: '100%' }}>
            {stages.map((s, i) => (
              <React.Fragment key={s}>
                <div className="flex flex-col items-center gap-1" style={{ minWidth: '48px' }}>
                  <div style={{
                    width: '7px', height: '7px', borderRadius: '50%',
                    background: i <= active ? '#67E8F9' : 'rgba(255,255,255,0.08)',
                    boxShadow: i === active ? '0 0 8px rgba(103,232,249,0.6)' : 'none',
                    transition: 'all 0.35s ease',
                  }} />
                  <span style={{
                    fontFamily: 'monospace', fontSize: '8px', letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    color: i <= active ? '#67E8F9' : 'rgba(255,255,255,0.15)',
                    transition: 'color 0.35s ease',
                  }}>{s}</span>
                </div>
                {i < stages.length - 1 && (
                  <div style={{
                    flex: 1, height: '1px', marginBottom: '14px',
                    background: i < active ? '#67E8F9' : 'rgba(255,255,255,0.08)',
                    transition: 'background 0.35s ease',
                  }} />
                )}
              </React.Fragment>
            ))}
          </div>
        );
      })()}
    </div>
  );
};

const SAMPLE_PROMPTS = [
  'Is ITC available on works contract for factory construction?',
  'What is the time limit to claim ITC under Section 16(4)?',
  'GST applicability on renting of immovable property to registered dealer?',
];

const AskLeta = ({ domain = 'gst', contextDesc = 'GST scenarios' }) => {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const textareaRef = useRef(null);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 320) + 'px';
  }, []);

  const handleAsk = async () => {
    if (!query.trim()) return;
    setIsLoading(true);
    setResponse(null);

    try {
      const res = await fetch(`${BASE_URL}/ask-sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: query, session_id: null, intent: 'general' }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setResponse({
        query,
        confidence: 0.92,
        answer: data.answer || 'No answer returned.',
        citations: (data.sources || []).map(s => s.title).filter(Boolean),
      });
    } catch (err) {
      setResponse({
        query,
        confidence: 0,
        answer: `**[Connection Error]**\n\nUnable to reach the advisory engine: ${err.message}. Please check your connection and try again.`,
        citations: [],
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: '#000000',
        border: '1px solid rgba(255,255,255,0.06)',
        boxShadow: '0 40px 80px rgba(0,0,0,0.55)',
      }}
    >
      {/* Top accent bar */}
      <div className="h-[2px] w-full" style={{ background: 'linear-gradient(90deg, #67E8F9, #0E7490, transparent)' }} />

      <div className="p-6 md:p-8">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-white/[0.02] border border-white/[0.05]">
            <Scale size={15} style={{ color: '#67E8F9' }} />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider font-display">
              Advisory Briefing Suite
            </h2>
            <p className="text-[10px] uppercase tracking-widest text-[#6B7280]">
              STATUTORY REFERENCE SEARCH
            </p>
          </div>
        </div>

        {/* Query area */}
        <div className="relative mb-4">
          <textarea
            ref={textareaRef}
            value={query}
            onChange={e => { setQuery(e.target.value); autoResize(); }}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk(); } }}
            placeholder={`Enter your ${contextDesc} query or notice scenario...\n\nShift + Enter for new line`}
            className="w-full resize-none outline-none text-xs leading-relaxed transition-all duration-200 bg-white/[0.01] border border-white/[0.04] p-4 pb-12 text-[#F5F7FA]"
            style={{
              borderRadius: '12px',
              minHeight: '100px',
              maxHeight: '320px',
              overflowY: 'auto',
            }}
            onFocus={e => {
              e.currentTarget.style.borderColor = 'rgba(103,232,249,0.3)';
              e.currentTarget.style.boxShadow = '0 0 15px rgba(103,232,249,0.05)';
            }}
            onBlur={e => {
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.04)';
              e.currentTarget.style.boxShadow = 'none';
            }}
          />
          {/* Submit button pinned inside bottom-right of textarea box */}
          <div className="absolute bottom-3 right-3">
            <button
              onClick={handleAsk}
              disabled={isLoading || !query.trim()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[11px] font-bold text-black transition-all duration-200"
              style={{
                background: isLoading || !query.trim()
                  ? 'rgba(103,232,249,0.25)'
                  : 'linear-gradient(135deg, #67E8F9, #5EEAD4)',
                cursor: isLoading || !query.trim() ? 'not-allowed' : 'pointer',
                opacity: isLoading || !query.trim() ? 0.5 : 1,
              }}
            >
              <Search size={11} />
              {isLoading ? 'Processing...' : 'Analyze Query'}
            </button>
          </div>
        </div>

        {/* Sample prompts */}
        {!query && !response && !isLoading && (
          <div className="flex flex-wrap gap-2 mb-5">
            {SAMPLE_PROMPTS.map((p, i) => (
              <button
                key={i}
                onClick={() => setQuery(p)}
                className="text-[10px] px-3 py-1.5 rounded-lg transition-all duration-150 border border-white/[0.04] bg-white/[0.01] text-[#A1AAB8] hover:border-[#67E8F9]/30 hover:text-white"
              >
                {p.length > 45 ? p.slice(0, 42) + '…' : p}
              </button>
            ))}
          </div>
        )}

        {/* Hint row */}
        <div className="flex items-center justify-between gap-4 -mt-1 mb-1">
          <span className="text-[10px] text-[#52525B]">Enter to submit · Shift+Enter for new line</span>
        </div>
      </div>

      {/* Response area */}
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.04)', background: 'rgba(0,0,0,0.05)' }}>
        {!response && !isLoading && (
          <div className="flex flex-col items-center justify-center py-12 px-8 text-center">
            <Search size={28} className="mb-3 text-[#52525B]" />
            <p className="text-xs font-semibold text-[#A1AAB8]">
              Ready for Consultation Query
            </p>
            <p className="text-[11px] mt-1.5 text-[#52525B] max-w-sm leading-relaxed">
              LETA cross-references statutory codes, central rules, and notifications up to the latest gazette amendments.
            </p>
          </div>
        )}

        {isLoading && (
          <div className="min-h-[220px] flex items-center justify-center">
            <LetaThinkingLoader isActive={isLoading} />
          </div>
        )}

        {response && (
          <div className="p-6 md:p-8">
            <LetaResponse data={response} isDark />
          </div>
        )}
      </div>
    </div>
  );
};

export default AskLeta;
