import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { FileText, Landmark, Globe, Briefcase, Activity } from 'lucide-react';

const AI_IMAGE = '/magnific_frontfacing-futuristic-ai_XtA30onBfo.png';

const MODULES = [
  {
    num: '01', icon: FileText, title: 'GST',
    desc: 'GSTR-1 to GSTR-9, ITC reconciliation, SCN replies, DRC-01 drafts, place of supply, e-invoicing, and appeal preparation.',
    status: 'live', value: '98.4%', width: '98.4%', metric: 'Coverage', href: '/gst', position: 'tl',
  },
  {
    num: '02', icon: Landmark, title: 'Income Tax',
    desc: 'ITR filing, TDS compliance, capital gains, tax planning, scrutiny notices, and audit support under the Income Tax Act.',
    status: 'soon', value: '35%', width: '35%', metric: 'Coming Soon', position: 'tr',
  },
  {
    num: '03', icon: Globe, title: 'FEMA & RBI',
    desc: 'FDI/ODI compliance, inward remittances, compounding applications, ECB advisory, and RBI reporting requirements.',
    status: 'soon', value: '22%', width: '22%', metric: 'Coming Soon', position: 'bl',
  },
  {
    num: '04', icon: Briefcase, title: 'Company Law',
    desc: 'Annual filings, board resolutions, charge creation, ROC compliance, share transfers, and MOA/AOA amendments.',
    status: 'soon', value: '41%', width: '41%', metric: 'Coming Soon', position: 'br',
  },
];

// ── Floating label callout (no card, no box) ──────────────────────────────────
const Callout = ({ mod, align = 'left' }) => {
  const [hovered, setHovered] = useState(false);
  const isLive = mod.status === 'live';
  const r = align === 'right';

  return (
    <motion.div
      initial={{ opacity: 0, x: r ? 30 : -30 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ textAlign: r ? 'right' : 'left', cursor: isLive ? 'pointer' : 'default' }}
    >
      {/* Node indicator + number */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexDirection: r ? 'row-reverse' : 'row' }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
          background: isLive ? '#4FB7C5' : 'rgba(107,114,128,0.4)',
          boxShadow: isLive ? '0 0 14px rgba(79,183,197,0.9)' : 'none',
          animation: isLive ? 'nodeGlow 2.2s ease-in-out infinite' : 'none',
        }} />
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 'clamp(36px, 4vw, 56px)',
          fontWeight: 700, lineHeight: 1,
          color: isLive ? 'rgba(79,183,197,0.25)' : 'rgba(255,255,255,0.06)',
          letterSpacing: '-0.04em',
          transition: 'color 0.3s',
          ...(hovered && { color: isLive ? 'rgba(79,183,197,0.45)' : 'rgba(255,255,255,0.12)' }),
        }}>
          {mod.num}
        </span>
      </div>

      {/* Title */}
      <h3 style={{
        fontFamily: "'Inter Tight', sans-serif",
        fontWeight: 700, fontSize: 'clamp(13px, 1.4vw, 17px)',
        letterSpacing: '-0.01em', textTransform: 'uppercase',
        color: hovered ? '#ffffff' : (isLive ? '#F4F7FA' : 'rgba(167,179,194,0.5)'),
        margin: '0 0 8px 0',
        transition: 'color 0.3s',
      }}>
        {mod.title}
      </h3>

      {/* Thin rule */}
      <div style={{
        height: 1,
        background: isLive
          ? `linear-gradient(${r ? 'to left' : 'to right'}, rgba(79,183,197,0.5), transparent)`
          : `linear-gradient(${r ? 'to left' : 'to right'}, rgba(255,255,255,0.08), transparent)`,
        marginBottom: 10,
        transition: 'opacity 0.3s',
        opacity: hovered ? 1 : 0.6,
      }} />

      {/* Description */}
      <p style={{
        fontFamily: "'Inter', sans-serif",
        fontSize: 'clamp(11px, 0.95vw, 13px)',
        fontWeight: 300, lineHeight: 1.65,
        color: isLive ? 'rgba(167,179,194,0.75)' : 'rgba(107,114,128,0.5)',
        margin: '0 0 14px 0', maxWidth: 240,
        ...(r && { marginLeft: 'auto' }),
      }}>
        {mod.desc}
      </p>

      {/* Progress */}
      <div style={{ marginBottom: isLive ? 12 : 0 }}>
        <div style={{ display: 'flex', justifyContent: r ? 'flex-end' : 'flex-start', gap: 8, marginBottom: 5, alignItems: 'center' }}>
          <span style={{ fontFamily: "'IBM Plex Mono'", fontSize: 8, color: 'rgba(107,114,128,0.5)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>
            {mod.metric}
          </span>
          <span style={{ fontFamily: "'IBM Plex Mono'", fontSize: 9, fontWeight: 700, color: isLive ? '#4FB7C5' : 'rgba(107,114,128,0.5)' }}>
            {mod.value}
          </span>
        </div>
        <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', position: 'relative', overflow: 'hidden', maxWidth: 200, ...(r && { marginLeft: 'auto' }) }}>
          <motion.div
            initial={{ width: 0 }}
            whileInView={{ width: mod.width }}
            viewport={{ once: true }}
            transition={{ duration: 1.4, ease: 'easeOut', delay: 0.5 }}
            style={{ position: 'absolute', top: 0, left: r ? 'auto' : 0, right: r ? 0 : 'auto', height: '100%', background: isLive ? 'linear-gradient(90deg, #4FB7C5, #67E8F9)' : 'rgba(107,114,128,0.3)' }}
          />
        </div>
      </div>

      {/* Live CTA */}
      {isLive && (
        <Link to={mod.href} style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          fontFamily: "'IBM Plex Mono'", fontSize: 8, fontWeight: 700,
          letterSpacing: '0.2em', textTransform: 'uppercase',
          color: hovered ? '#67E8F9' : '#4FB7C5', textDecoration: 'none',
          transition: 'color 0.2s, letter-spacing 0.2s',
          ...(hovered && { letterSpacing: '0.26em' }),
        }}>
          Initialize Workspace →
        </Link>
      )}
    </motion.div>
  );
};

// ── SVG: connector lines + decorative elements ────────────────────────────────
const HUDOverlay = () => (
  <svg
    style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', overflow: 'visible' }}
    viewBox="0 0 1300 660"
    preserveAspectRatio="none"
  >
    <defs>
      <radialGradient id="figureGlow" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stopColor="rgba(79,183,197,0.18)" />
        <stop offset="100%" stopColor="rgba(79,183,197,0)" />
      </radialGradient>
    </defs>

    {/* Outer decorative ellipse */}
    <ellipse cx="650" cy="330" rx="580" ry="300" fill="none" stroke="rgba(79,183,197,0.05)" strokeWidth="1" strokeDasharray="3 12" />

    {/* Connector: TL callout → figure */}
    <line x1="295" y1="190" x2="530" y2="270" stroke="rgba(79,183,197,0.22)" strokeWidth="0.7" strokeDasharray="5 7">
      <animate attributeName="stroke-dashoffset" from="0" to="-60" dur="3.5s" repeatCount="indefinite" />
    </line>
    {/* Connector: TR callout → figure */}
    <line x1="1005" y1="190" x2="770" y2="270" stroke="rgba(79,183,197,0.22)" strokeWidth="0.7" strokeDasharray="5 7">
      <animate attributeName="stroke-dashoffset" from="0" to="-60" dur="4s" repeatCount="indefinite" />
    </line>
    {/* Connector: BL callout → figure */}
    <line x1="295" y1="470" x2="530" y2="400" stroke="rgba(79,183,197,0.22)" strokeWidth="0.7" strokeDasharray="5 7">
      <animate attributeName="stroke-dashoffset" from="0" to="-60" dur="3.8s" repeatCount="indefinite" />
    </line>
    {/* Connector: BR callout → figure */}
    <line x1="1005" y1="470" x2="770" y2="400" stroke="rgba(79,183,197,0.22)" strokeWidth="0.7" strokeDasharray="5 7">
      <animate attributeName="stroke-dashoffset" from="0" to="-60" dur="4.3s" repeatCount="indefinite" />
    </line>

    {/* Corner tick marks at callout endpoints */}
    {[[295,190],[1005,190],[295,470],[1005,470]].map(([x,y], i) => (
      <g key={i}>
        <line x1={x-8} y1={y} x2={x+8} y2={y} stroke="rgba(79,183,197,0.4)" strokeWidth="0.8" />
        <line x1={x} y1={y-8} x2={x} y2={y+8} stroke="rgba(79,183,197,0.4)" strokeWidth="0.8" />
      </g>
    ))}

    {/* Horizontal centre axis line (subtle) */}
    <line x1="70" y1="330" x2="1230" y2="330" stroke="rgba(79,183,197,0.04)" strokeWidth="0.6" strokeDasharray="2 20" />
  </svg>
);

// ── AI Figure with rings + scan ───────────────────────────────────────────────
const AIFigure = () => (
  <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>

    {/* No background glow — keep it pure black */}

    {/* Outer ring */}
    <div style={{ position: 'absolute', width: 430, height: 430, borderRadius: '50%', border: '1px dashed rgba(79,183,197,0.18)', animation: 'spinRing 28s linear infinite' }} />

    {/* Inner ring */}
    <div style={{ position: 'absolute', width: 340, height: 340, borderRadius: '50%', border: '1px solid rgba(79,183,197,0.10)', animation: 'spinRing 16s linear infinite reverse' }}>
      <div style={{ position: 'absolute', top: -5, left: '50%', transform: 'translateX(-50%)', width: 8, height: 8, borderRadius: '50%', background: '#4FB7C5', boxShadow: '0 0 16px rgba(79,183,197,1)' }} />
    </div>

    {/* The figure */}
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
      style={{
        position: 'relative', zIndex: 2, width: '78%', maxWidth: 300,
        /* Radial mask: face/circuits fully visible, edges dissolve to transparent */
        WebkitMaskImage: 'radial-gradient(ellipse 78% 80% at 50% 42%, black 42%, rgba(0,0,0,0.85) 58%, rgba(0,0,0,0.3) 72%, transparent 88%)',
        maskImage: 'radial-gradient(ellipse 78% 80% at 50% 42%, black 42%, rgba(0,0,0,0.85) 58%, rgba(0,0,0,0.3) 72%, transparent 88%)',
      }}
    >
      <img
        src={AI_IMAGE}
        alt="LETA Intelligence Core"
        style={{
          width: '100%', display: 'block',
          mixBlendMode: 'screen',
          filter: 'contrast(1.6) brightness(0.95) saturate(1.15)',
        }}
      />

      {/* Scan line */}
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none', zIndex: 3 }}>
        <div style={{ position: 'absolute', left: 0, right: 0, height: 2, background: 'linear-gradient(to right, transparent, rgba(79,183,197,0.6), transparent)', animation: 'scanLine 4s ease-in-out infinite', boxShadow: '0 0 12px rgba(79,183,197,0.4)' }} />
      </div>
    </motion.div>

    {/* Label below */}
    <div style={{ position: 'absolute', bottom: '6%', zIndex: 4, textAlign: 'center' }}>
      <p style={{ fontFamily: "'IBM Plex Mono'", fontSize: 8, fontWeight: 700, letterSpacing: '0.3em', textTransform: 'uppercase', color: 'rgba(79,183,197,0.45)', margin: 0 }}>
        LETA · INTELLIGENCE CORE · v2.4
      </p>
    </div>

    <style>{`
      @keyframes spinRing { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      @keyframes scanLine { 0% { top: -2%; opacity: 0; } 10% { opacity: 1; } 90% { opacity: 0.4; } 100% { top: 102%; opacity: 0; } }
      @keyframes nodeGlow { 0%,100% { box-shadow: 0 0 14px rgba(79,183,197,0.9); } 50% { box-shadow: 0 0 6px rgba(79,183,197,0.4); } }
    `}</style>
  </div>
);

// ── Section ───────────────────────────────────────────────────────────────────
const StatutoryDomains = () => (
  <section style={{ padding: '40px 0 80px', background: '#000', position: 'relative', overflow: 'hidden', borderTop: '1px solid rgba(255,255,255,0.03)' }}>


    <div className="section-container" style={{ position: 'relative', zIndex: 10 }}>

      {/* Header */}
      <motion.div
        className="section-header"
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1] }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
          <div>
            <p className="section-eyebrow">// Practice Coverage</p>
            <h2 className="section-headline">Every Practice Area.<br />One Platform.</h2>
          </div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px', border: '1px solid rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.02)', flexShrink: 0 }}>
            <Activity size={11} style={{ color: '#4FB7C5' }} className="animate-pulse" />
            <span style={{ fontFamily: "'IBM Plex Mono'", fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.15em', color: '#4FB7C5' }}>
              GST Live — Income Tax, FEMA &amp; Co. Law Coming
            </span>
          </div>
        </div>
      </motion.div>

      {/* Arena */}
      <div style={{ position: 'relative', minHeight: 640 }}>
        <HUDOverlay />

        {/* Left callouts */}
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '28%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', paddingTop: 0, paddingBottom: 20, zIndex: 2 }}>
          <Callout mod={MODULES[0]} align="left" />
          <Callout mod={MODULES[2]} align="left" />
        </div>

        {/* Center: AI figure */}
        <div style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)', top: 0, bottom: 0, width: '32%', zIndex: 2 }}>
          <AIFigure />
        </div>

        {/* Right callouts */}
        <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: '28%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', paddingTop: 0, paddingBottom: 20, zIndex: 2 }}>
          <Callout mod={MODULES[1]} align="right" />
          <Callout mod={MODULES[3]} align="right" />
        </div>

      </div>
    </div>
  </section>
);

export default StatutoryDomains;
