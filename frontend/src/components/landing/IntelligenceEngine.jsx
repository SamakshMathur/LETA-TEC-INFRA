import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Map, Award, BookOpen, FileCheck } from 'lucide-react';
import PillarThreeScene from './PillarThreeScene';

const STEPS = [
  {
    id: 'query', icon: Search, label: 'User Query', tag: 'INPUT_STREAM',
    desc: 'You type a GST question — ITC eligibility, SCN reply, place of supply, GSTR mismatch. LETA understands the legal context before it searches.',
    metrics: [
      { name: 'Parse Speed',  value: '1,200 tokens/sec' },
      { name: 'Query Encode', value: 'Vector-Hashed' },
    ],
  },
  {
    id: 'mapping', icon: Map, label: 'Statute Mapping', tag: 'ACT_SEARCH',
    desc: 'LETA pinpoints the exact section, notification, or circular — across the CGST Act, IGST Act, Rules, and CBIC circulars — relevant to your query.',
    metrics: [
      { name: 'Accuracy',     value: '99.2%' },
      { name: 'Acts Indexed', value: '14 Million+' },
    ],
  },
  {
    id: 'caselaw', icon: BookOpen, label: 'Case Law Analysis', tag: 'CITATION_CHECK',
    desc: 'Cross-references High Court and Supreme Court judgments, AAR/AAAR rulings, and tribunal orders that are directly relevant to your matter.',
    metrics: [
      { name: 'Cross-references', value: '540,000+' },
      { name: 'Retrieval Depth',  value: 'Cognitive Rank' },
    ],
  },
  {
    id: 'reasoning', icon: Award, label: 'AI Reasoning', tag: 'LOGIC_ENGINE',
    desc: 'Evaluates conflicts between statutory text, circular exceptions, and judicial outcomes. Surfaces the risk level and the strongest defensible position.',
    metrics: [
      { name: 'Logic Chains', value: 'Multi-Path' },
      { name: 'Bias Shield',  value: 'Active' },
    ],
  },
  {
    id: 'output', icon: FileCheck, label: 'Structured Output', tag: 'REPLY_DRAFT',
    desc: 'Delivers a cited advisory, risk matrix, and ready-to-file draft — DRC-01, appeal brief, or compliance memo — with every citation verified.',
    metrics: [
      { name: 'Latency',   value: '2.3 seconds' },
      { name: 'Citations', value: '100% Verified' },
    ],
  },
];

const SCROLL_HEIGHT_VH = 400;

// Direction tracker so we know which way to revolve
let prevStep = 0;

const IntelligenceEngine = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [dir, setDir]               = useState(1); // 1 = scroll down, -1 = scroll up
  const containerRef = useRef(null);
  const rafRef       = useRef(null);

  useEffect(() => {
    const onScroll = () => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        const el = containerRef.current;
        if (!el) return;
        const rect   = el.getBoundingClientRect();
        const totalH = el.offsetHeight - window.innerHeight;
        if (totalH <= 0) return;
        const progress = Math.max(0, Math.min(1, -rect.top / totalH));
        const step     = Math.min(STEPS.length - 1, Math.floor(progress * STEPS.length));
        if (step !== prevStep) {
          setDir(step > prevStep ? 1 : -1);
          prevStep = step;
          setActiveStep(step);
        }
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ height: `${SCROLL_HEIGHT_VH}vh`, position: 'relative', background: '#000', borderTop: '1px solid rgba(255,255,255,0.04)' }}
    >
      {/* Sticky viewport */}
      <div style={{ position: 'sticky', top: 0, height: '100dvh', overflow: 'hidden', display: 'grid', gridTemplateColumns: '1fr 1fr' }}>

        {/* ── Left: Vertical pipeline animation ─────────────────────────── */}
        <div style={{ position: 'relative', height: '100dvh', borderRight: '1px solid rgba(255,255,255,0.04)' }}>
          <PillarThreeScene activeStep={activeStep} />
        </div>

        {/* ── Right: Step content with revolving transition ──────────────── */}
        <div style={{
          display: 'flex', flexDirection: 'column', justifyContent: 'center',
          padding: 'clamp(40px,5vh,72px) clamp(32px,5vw,72px)',
          overflow: 'hidden',
          perspective: '900px',
        }}>

          {/* Section header — static, doesn't revolve */}
          <div style={{ marginBottom: 32 }}>
            <p className="section-eyebrow">// How It Works</p>
            <h2 className="section-headline" style={{ fontSize: 'clamp(26px,2.8vw,46px)' }}>
              How LETA<br />Answers Your Query
            </h2>
          </div>

          {/* Step pill nav */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 32, flexWrap: 'wrap' }}>
            {STEPS.map((s, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 10px',
                border: `1px solid ${i === activeStep ? 'rgba(79,183,197,0.55)' : 'rgba(255,255,255,0.06)'}`,
                borderRadius: 2,
                transition: 'all 0.5s ease',
              }}>
                <div style={{
                  width: 5, height: 5, borderRadius: '50%',
                  background: i < activeStep ? '#4FB7C5' : i === activeStep ? '#dff6fa' : 'rgba(255,255,255,0.12)',
                  boxShadow: i === activeStep ? '0 0 6px rgba(79,183,197,0.9)' : 'none',
                  transition: 'all 0.5s ease',
                }} />
                <span style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: 8, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.15em',
                  color: i === activeStep ? '#4FB7C5' : 'rgba(255,255,255,0.20)',
                  transition: 'color 0.5s ease',
                }}>
                  {s.label}
                </span>
              </div>
            ))}
          </div>

          {/* Revolving step detail — drum-roll around X axis */}
          <div style={{ position: 'relative', transformStyle: 'preserve-3d', minHeight: 280 }}>
            <AnimatePresence mode="wait" custom={dir}>
              <motion.div
                key={activeStep}
                custom={dir}
                variants={{
                  enter:  (d) => ({ opacity: 0, rotateX: d * 48, y: d * 32, filter: 'blur(4px)' }),
                  center: { opacity: 1, rotateX: 0,      y: 0,      filter: 'blur(0px)' },
                  exit:   (d) => ({ opacity: 0, rotateX: d * -52, y: d * -28, filter: 'blur(3px)' }),
                }}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.52, ease: [0.16, 1, 0.3, 1] }}
                style={{ transformOrigin: '50% 50%', transformStyle: 'preserve-3d' }}
              >
                {/* Step header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 20 }}>
                  <span style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 'clamp(36px,4vw,58px)', fontWeight: 700,
                    color: 'rgba(79,183,197,0.10)', lineHeight: 1,
                    letterSpacing: '-0.04em', flexShrink: 0,
                  }}>
                    0{activeStep + 1}
                  </span>
                  <div style={{ paddingTop: 6 }}>
                    <p style={{
                      fontFamily: "'IBM Plex Mono', monospace", fontSize: 8, fontWeight: 700,
                      textTransform: 'uppercase', letterSpacing: '0.22em', color: '#4FB7C5', margin: '0 0 5px',
                    }}>
                      {STEPS[activeStep].tag}
                    </p>
                    <h3 style={{
                      fontFamily: "'Inter Tight', sans-serif", fontWeight: 700,
                      fontSize: 'clamp(15px,1.6vw,22px)', letterSpacing: '-0.02em',
                      color: '#F4F7FA', textTransform: 'uppercase', margin: 0,
                    }}>
                      {STEPS[activeStep].label}
                    </h3>
                  </div>
                </div>

                {/* Description */}
                <p style={{
                  fontFamily: "'Inter', sans-serif", fontSize: 15, fontWeight: 300,
                  lineHeight: 1.78, color: 'rgba(167,179,194,0.85)',
                  margin: '0 0 28px', maxWidth: 460,
                }}>
                  {STEPS[activeStep].desc}
                </p>

                {/* Metrics */}
                <div style={{ borderLeft: '1px solid rgba(255,255,255,0.06)', paddingLeft: 20 }}>
                  <p style={{
                    fontFamily: "'IBM Plex Mono', monospace", fontSize: 7.5, fontWeight: 600,
                    textTransform: 'uppercase', letterSpacing: '0.2em',
                    color: 'rgba(107,114,128,0.4)', marginBottom: 16,
                  }}>
                    — Telemetry
                  </p>
                  {STEPS[activeStep].metrics.map((m, i) => (
                    <div key={i} style={{ marginBottom: i < STEPS[activeStep].metrics.length - 1 ? 16 : 0 }}>
                      <p style={{
                        fontFamily: "'IBM Plex Mono', monospace", fontSize: 7.5,
                        textTransform: 'uppercase', letterSpacing: '0.14em',
                        color: 'rgba(107,114,128,0.40)', margin: '0 0 4px',
                      }}>
                        {m.name}
                      </p>
                      <p style={{
                        fontFamily: "'Inter Tight', sans-serif",
                        fontSize: 'clamp(16px,1.8vw,24px)', fontWeight: 700,
                        letterSpacing: '-0.02em', color: '#4FB7C5', margin: 0,
                      }}>
                        {m.value}
                      </p>
                    </div>
                  ))}
                </div>
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Scroll hint */}
          <AnimatePresence>
            {activeStep === 0 && (
              <motion.p
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: 8,
                  color: 'rgba(79,183,197,0.30)', letterSpacing: '0.2em',
                  textTransform: 'uppercase', marginTop: 32,
                }}
              >
                ↓ Scroll to advance
              </motion.p>
            )}
          </AnimatePresence>

        </div>
      </div>
    </div>
  );
};

export default IntelligenceEngine;
