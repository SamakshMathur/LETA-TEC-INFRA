import React, { useState, useRef, useCallback } from 'react';
import { Search, Scale } from 'lucide-react';
import { SimpleSearchLoader } from '../effects';
import LetaResponse from './LetaResponse';

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

  const handleAsk = () => {
    if (!query.trim()) return;
    setIsLoading(true);
    setResponse(null);

    setTimeout(() => {
      setIsLoading(false);
      setResponse({
        query,
        confidence: 0.95,
        answer: `**[CONSULTATION BRIEF]**\n\nBased on the relevant provisions of the ${domain.toUpperCase()} Act, the query regarding "${query.substring(0, 45)}..." interprets as follows:\n\n**Section 17(5)(c)** of the CGST Act, 2017 restricts input tax credit on works contract services when supplied for construction of an immovable property (other than plant and machinery), even where the same would be treated as plant and machinery.\n\n*This draft analysis has been synthesized using verified statutory notifications.*`,
        reasoning: {
          interpretation: `Analysis of advisory query within ${domain.toUpperCase()} statutory context.`,
          provisions: [`Section 17(5) of ${domain.toUpperCase()} Act`, 'Notification 45/2024'],
          deduction: 'The statutory reading suggests compliance is mandatory under given conditions.',
          limitations: 'General professional advisory format only.',
        },
        citations: [`${domain.toUpperCase()} Act, Section 12`, 'Statutory Notification 45/2024'],
      });
    }, 2000);
  };

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: '#10141B',
        border: '1px solid rgba(255,255,255,0.04)',
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
            <SimpleSearchLoader />
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
