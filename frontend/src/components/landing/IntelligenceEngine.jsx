import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Map, Award, BookOpen, FileCheck } from 'lucide-react';
import PipelineThreeScene from './PipelineThreeScene';
import pipelineImg from '../../pages/IMAGES/magnific_futuristic-horizontal-dat_iAsjqAE3uK.png';

const STEPS = [
  {
    id: 'query',
    icon: Search,
    label: 'User Query',
    tag: 'INPUT_STREAM',
    desc: 'The user enters a complex statutory or transaction-level question (e.g., input tax credit eligibility on custom construction, corporate restructuring notifications).',
    metrics: [
      { name: 'Parser Rate',       value: '1,200 tokens/sec' },
      { name: 'Resolver Encoding', value: 'Vector-Hashed' },
    ],
  },
  {
    id: 'mapping',
    icon: Map,
    label: 'Statute Mapping',
    tag: 'HIERARCHICAL_SEARCH',
    desc: "The core engine isolates target acts, sub-sections, notifications, and circulars across India's direct and indirect tax codes.",
    metrics: [
      { name: 'Mapping Accuracy',  value: '99.2%' },
      { name: 'Act Codes Indexed', value: '14 Million+' },
    ],
  },
  {
    id: 'caselaw',
    icon: BookOpen,
    label: 'Case Law Analysis',
    tag: 'CITATION_VERIFICATION',
    desc: 'Synthesizes thousands of high-level judicial decisions from High Courts, Supreme Court, and appellate authorities for current relevance.',
    metrics: [
      { name: 'Cross References', value: '540,000+' },
      { name: 'Retrieval Depth',  value: 'Cognitive Rank' },
    ],
  },
  {
    id: 'reasoning',
    icon: Award,
    label: 'AI Legal Reasoning',
    tag: 'LOGIC_ENGINE',
    desc: 'Evaluates contradictions between statutory wording, circular exceptions, and judicial outcomes using domain-specific legal reasoning chains.',
    metrics: [
      { name: 'Logic Chains',   value: 'Multi-Path' },
      { name: 'Bias Filtering', value: 'Static-Shielded' },
    ],
  },
  {
    id: 'output',
    icon: FileCheck,
    label: 'Structured Output',
    tag: 'COMPLIANCE_RECON',
    desc: 'Generates a secure, highly-cited legal response containing statutory definitions, risk matrices, and actionable recommendations.',
    metrics: [
      { name: 'Latency',       value: '2.3 seconds' },
      { name: 'Citation Rate', value: '100% Verified' },
    ],
  },
];


// ── Main component ────────────────────────────────────────────────────────────
const IntelligenceEngine = () => {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setActiveStep(prev => (prev + 1) % STEPS.length), 4500);
    return () => clearInterval(timer);
  }, []);

  return (
    <section style={{ padding: '80px 0', background: '#000000', position: 'relative', overflow: 'hidden', borderTop: '1px solid rgba(255,255,255,0.03)' }}>

      <div aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'radial-gradient(ellipse 70% 50% at 50% 50%, rgba(79,183,197,0.03) 0%, transparent 70%)' }} />

      <div className="section-container" style={{ position: 'relative', zIndex: 10 }}>

        {/* Header */}
        <motion.div
          className="section-header"
          initial={{ opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <p className="section-eyebrow">// Operational Architecture</p>
          <h2 className="section-headline">Statutory Intelligence<br />Engine</h2>
          <p className="section-subhead">
            Tracking LETA's high-fidelity reasoning, contextual cross-referencing,
            and structural statutory mapping pipelines.
          </p>
        </motion.div>

        {/* Pipeline image with Three.js overlay */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          style={{ position: 'relative', border: '1px solid rgba(79,183,197,0.12)', overflow: 'hidden', height: 340 }}
        >
          {/* Top accent line */}
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, #4FB7C5 0%, transparent 60%)', zIndex: 10, pointerEvents: 'none' }} />

          {/* Static pipeline image */}
          <img
            src={pipelineImg}
            alt="LETA Intelligence Pipeline"
            style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center', display: 'block' }}
          />

          {/* Three.js glow overlay — mix-blend-mode: screen */}
          <div style={{ position: 'absolute', inset: 0, zIndex: 5 }}>
            <PipelineThreeScene activeStep={activeStep} onStepClick={setActiveStep} overlay />
          </div>

          {/* Bottom fade into black */}
          <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 90, background: 'linear-gradient(to top, #000 0%, transparent 100%)', pointerEvents: 'none', zIndex: 6 }} />
        </motion.div>

        {/* Step tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.06)', marginBottom: 0 }}>
          {STEPS.map((step, index) => {
            const Icon = step.icon;
            const isActive = index === activeStep;
            const isPassed = index < activeStep;
            return (
              <button
                key={step.id}
                onClick={() => setActiveStep(index)}
                style={{
                  flex: '1 1 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10,
                  padding: '20px 8px', background: 'none', border: 'none', cursor: 'pointer',
                  borderBottom: `2px solid ${isActive ? '#4FB7C5' : 'transparent'}`,
                  transition: 'border-color 0.3s',
                  position: 'relative', top: 1,
                }}
              >
                <Icon
                  size={18}
                  strokeWidth={1.5}
                  style={{ color: isActive ? '#4FB7C5' : isPassed ? 'rgba(79,183,197,0.45)' : 'rgba(107,114,128,0.35)', transition: 'color 0.3s' }}
                />
                <span style={{
                  fontFamily: "'IBM Plex Mono'", fontSize: 8, fontWeight: 700,
                  textTransform: 'uppercase', letterSpacing: '0.14em', whiteSpace: 'nowrap',
                  color: isActive ? '#F4F7FA' : isPassed ? 'rgba(167,179,194,0.4)' : 'rgba(107,114,128,0.35)',
                  transition: 'color 0.3s',
                }}>
                  {step.label}
                </span>
              </button>
            );
          })}
        </div>

        {/* Step detail — open layout, no cards */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeStep}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
            style={{ padding: '40px 0 0', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '48px 80px', alignItems: 'start' }}
          >
            {/* Left: stage info */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                <span style={{ fontFamily: "'IBM Plex Mono'", fontSize: 'clamp(48px,5vw,72px)', fontWeight: 700, color: 'rgba(79,183,197,0.10)', lineHeight: 1, letterSpacing: '-0.04em' }}>
                  0{activeStep + 1}
                </span>
                <div>
                  <p style={{ fontFamily: "'IBM Plex Mono'", fontSize: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.2em', color: '#4FB7C5', margin: '0 0 4px' }}>
                    {STEPS[activeStep].tag}
                  </p>
                  <h3 style={{ fontFamily: "'Inter Tight'", fontWeight: 700, fontSize: 'clamp(18px,2vw,26px)', letterSpacing: '-0.025em', color: '#F4F7FA', textTransform: 'uppercase', margin: 0 }}>
                    {STEPS[activeStep].label}
                  </h3>
                </div>
              </div>
              <p style={{ fontFamily: "'Inter'", fontSize: 14, fontWeight: 300, lineHeight: 1.78, color: 'rgba(167,179,194,0.85)', margin: 0 }}>
                {STEPS[activeStep].desc}
              </p>
            </div>

            {/* Right: metrics as plain labeled rows, no box */}
            <div style={{ paddingTop: 8, borderLeft: '1px solid rgba(255,255,255,0.05)', paddingLeft: 48 }}>
              <p style={{ fontFamily: "'IBM Plex Mono'", fontSize: 8, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.2em', color: 'rgba(107,114,128,0.5)', marginBottom: 24 }}>
                — System Telemetry
              </p>
              {STEPS[activeStep].metrics.map((m, i) => (
                <div key={i} style={{ marginBottom: i < STEPS[activeStep].metrics.length - 1 ? 20 : 0 }}>
                  <p style={{ fontFamily: "'IBM Plex Mono'", fontSize: 8, textTransform: 'uppercase', letterSpacing: '0.14em', color: 'rgba(107,114,128,0.5)', margin: '0 0 6px' }}>
                    {m.name}
                  </p>
                  <p style={{ fontFamily: "'Inter Tight'", fontSize: 'clamp(18px,2vw,24px)', fontWeight: 700, letterSpacing: '-0.02em', color: '#4FB7C5', margin: 0 }}>
                    {m.value}
                  </p>
                </div>
              ))}
            </div>
          </motion.div>
        </AnimatePresence>

      </div>
    </section>
  );
};

export default IntelligenceEngine;
