import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity } from 'lucide-react';

const MODULES = [
  {
    num: '01', title: 'GST',
    desc: 'GSTR-1 to GSTR-9, ITC reconciliation, SCN replies, DRC-01 drafts, place of supply, e-invoicing, and appeal preparation.',
    status: 'live', value: '98.4%', width: '98.4%', metric: 'Coverage', href: '/dashboard',
    orbitDur: ['18s', '26s', '14s'],
  },
  {
    num: '02', title: 'Income Tax',
    desc: 'ITR filing, TDS compliance, capital gains, tax planning, scrutiny notices, and audit support under the Income Tax Act.',
    status: 'soon', value: '35%', width: '35%', metric: 'In Progress',
    orbitDur: ['22s', '30s', '17s'],
  },
  {
    num: '03', title: 'FEMA & RBI',
    desc: 'FDI/ODI compliance, inward remittances, compounding applications, ECB advisory, and RBI reporting requirements.',
    status: 'soon', value: '22%', width: '22%', metric: 'In Progress',
    orbitDur: ['20s', '28s', '15s'],
  },
  {
    num: '04', title: 'Company Law',
    desc: 'Annual filings, board resolutions, charge creation, ROC compliance, share transfers, and MOA/AOA amendments.',
    status: 'soon', value: '41%', width: '41%', metric: 'In Progress',
    orbitDur: ['16s', '24s', '19s'],
  },
];

/* ── Pure-CSS orbital visual (no JS, no WebGL) ──────────────────────────── */
const OrbitalVisual = ({ isLive, orbitDur }) => {
  const C = isLive ? '#4FB7C5' : '#3a4a5a';
  const alpha = isLive ? 1 : 0.35;

  return (
    <div style={{
      position: 'relative', width: '100%', height: '100%',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      overflow: 'hidden',
    }}>
      {/* Outer orbit ring */}
      <div style={{
        position: 'absolute',
        width: 100, height: 60,
        borderRadius: '50%',
        border: `1px solid ${C}`,
        opacity: 0.15 * alpha,
        animation: `orbitSpin ${orbitDur[0]} linear infinite`,
      }} />
      {/* Outer orbiter dot */}
      <div style={{
        position: 'absolute',
        width: 100, height: 60,
        animation: `orbitSpin ${orbitDur[0]} linear infinite`,
      }}>
        <div style={{
          position: 'absolute', top: -3, left: '50%', transform: 'translateX(-50%)',
          width: 5, height: 5, borderRadius: '50%',
          background: C, opacity: 0.8 * alpha,
          boxShadow: isLive ? `0 0 6px ${C}` : 'none',
        }} />
      </div>

      {/* Middle orbit ring */}
      <div style={{
        position: 'absolute',
        width: 64, height: 38,
        borderRadius: '50%',
        border: `1px solid ${C}`,
        opacity: 0.2 * alpha,
        animation: `orbitSpin ${orbitDur[1]} linear infinite reverse`,
      }} />
      <div style={{
        position: 'absolute',
        width: 64, height: 38,
        animation: `orbitSpin ${orbitDur[1]} linear infinite reverse`,
      }}>
        <div style={{
          position: 'absolute', top: -2.5, left: '50%', transform: 'translateX(-50%)',
          width: 4, height: 4, borderRadius: '50%',
          background: C, opacity: 0.7 * alpha,
        }} />
      </div>

      {/* Inner orbit ring */}
      <div style={{
        position: 'absolute',
        width: 34, height: 20,
        borderRadius: '50%',
        border: `1px solid ${C}`,
        opacity: 0.25 * alpha,
        animation: `orbitSpin ${orbitDur[2]} linear infinite`,
      }} />

      {/* Core dot */}
      <div style={{
        width: 7, height: 7, borderRadius: '50%',
        background: isLive ? '#9AE3EE' : '#3a4a5a',
        boxShadow: isLive ? '0 0 12px rgba(79,183,197,0.9), 0 0 24px rgba(79,183,197,0.4)' : 'none',
        position: 'relative', zIndex: 2,
        animation: isLive ? 'corePulse 2.5s ease-in-out infinite' : 'none',
      }} />
    </div>
  );
};

/* ── Single domain card ─────────────────────────────────────────────────── */
const DomainCard = ({ mod }) => {
  const [hovered, setHovered] = useState(false);
  const isLive = mod.status === 'live';

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position: 'relative', overflow: 'hidden',
        background: 'linear-gradient(145deg, #0a0f18 0%, #04080f 100%)',
        border: `1px solid ${hovered
          ? (isLive ? 'rgba(79,183,197,0.45)' : 'rgba(255,255,255,0.12)')
          : (isLive ? 'rgba(79,183,197,0.18)' : 'rgba(255,255,255,0.05)')}`,
        transition: 'border-color 0.3s, box-shadow 0.3s',
        boxShadow: hovered && isLive
          ? '0 0 32px rgba(79,183,197,0.08), 0 6px 24px rgba(0,0,0,0.5)'
          : '0 4px 20px rgba(0,0,0,0.4)',
      }}
    >
      {/* Top accent line */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 1,
        background: isLive
          ? 'linear-gradient(90deg, #4FB7C5, rgba(79,183,197,0.2) 100%)'
          : 'linear-gradient(90deg, rgba(255,255,255,0.07), transparent)',
        opacity: hovered ? 1 : 0.6,
        transition: 'opacity 0.3s',
      }} />

      {/* Orbital visual strip */}
      <div style={{
        height: 120, position: 'relative',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
      }}>
        <OrbitalVisual isLive={isLive} orbitDur={mod.orbitDur} />

        {/* Fade at bottom */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: 36,
          background: 'linear-gradient(to bottom, transparent, #04080f)',
          pointerEvents: 'none',
        }} />

        {/* Number ghost */}
        <span style={{
          position: 'absolute', top: 10, left: 14,
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 40, fontWeight: 700, lineHeight: 1,
          color: isLive ? 'rgba(79,183,197,0.15)' : 'rgba(255,255,255,0.05)',
          letterSpacing: '-0.04em', pointerEvents: 'none',
          transition: 'color 0.3s',
          ...(hovered && { color: isLive ? 'rgba(79,183,197,0.3)' : 'rgba(255,255,255,0.1)' }),
        }}>
          {mod.num}
        </span>

        {/* Status badge */}
        <div style={{
          position: 'absolute', top: 12, right: 12,
          display: 'flex', alignItems: 'center', gap: 5,
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: isLive ? '#4FB7C5' : 'rgba(107,114,128,0.4)',
            boxShadow: isLive ? '0 0 8px rgba(79,183,197,0.9)' : 'none',
            animation: isLive ? 'statusPulse 2.2s ease-in-out infinite' : 'none',
          }} />
          <span style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: 7, fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: '0.18em',
            color: isLive ? 'rgba(79,183,197,0.7)' : 'rgba(107,114,128,0.4)',
          }}>
            {isLive ? 'Live' : 'Soon'}
          </span>
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: '18px 20px 22px' }}>
        <h3 style={{
          fontFamily: "'Inter Tight', sans-serif", fontWeight: 700,
          fontSize: 15, letterSpacing: '-0.01em', textTransform: 'uppercase',
          color: hovered ? '#ffffff' : (isLive ? '#F4F7FA' : 'rgba(167,179,194,0.45)'),
          margin: '0 0 6px', transition: 'color 0.3s',
        }}>
          {mod.title}
        </h3>

        <div style={{
          height: 1, marginBottom: 12,
          background: isLive
            ? 'linear-gradient(to right, rgba(79,183,197,0.45), transparent)'
            : 'linear-gradient(to right, rgba(255,255,255,0.07), transparent)',
          opacity: hovered ? 1 : 0.55, transition: 'opacity 0.3s',
        }} />

        <p style={{
          fontFamily: "'Inter', sans-serif", fontSize: 12.5, fontWeight: 300,
          lineHeight: 1.68, color: isLive ? 'rgba(167,179,194,0.70)' : 'rgba(107,114,128,0.45)',
          margin: '0 0 16px',
        }}>
          {mod.desc}
        </p>

        {/* Metric bar */}
        <div style={{ marginBottom: isLive ? 14 : 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ fontFamily: "'IBM Plex Mono'", fontSize: 7.5, color: 'rgba(107,114,128,0.45)', textTransform: 'uppercase', letterSpacing: '0.14em' }}>
              {mod.metric}
            </span>
            <span style={{ fontFamily: "'IBM Plex Mono'", fontSize: 8, fontWeight: 700, color: isLive ? '#4FB7C5' : 'rgba(107,114,128,0.4)' }}>
              {mod.value}
            </span>
          </div>
          <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', position: 'relative', overflow: 'hidden' }}>
            <div style={{
              position: 'absolute', top: 0, left: 0, height: '100%', width: mod.width,
              background: isLive ? 'linear-gradient(90deg, #4FB7C5, #67E8F9)' : 'rgba(107,114,128,0.25)',
            }} />
          </div>
        </div>

        {isLive && (
          <Link to={mod.href} style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            fontFamily: "'IBM Plex Mono'", fontSize: 7.5, fontWeight: 700,
            letterSpacing: '0.2em', textTransform: 'uppercase',
            color: hovered ? '#67E8F9' : '#4FB7C5', textDecoration: 'none',
            transition: 'color 0.2s',
          }}>
            Initialize Workspace →
          </Link>
        )}
      </div>
    </div>
  );
};

/* ── Section ─────────────────────────────────────────────────────────────── */
const StatutoryDomains = () => (
  <section style={{
    padding: '80px 0 100px', background: '#000',
    position: 'relative', overflow: 'hidden',
    borderTop: '1px solid rgba(255,255,255,0.03)',
  }}>
    <style>{`
      @keyframes orbitSpin  { from { transform: rotate(0deg); }  to { transform: rotate(360deg); } }
      @keyframes statusPulse { 0%,100% { box-shadow: 0 0 8px rgba(79,183,197,0.9); } 50% { box-shadow: 0 0 3px rgba(79,183,197,0.3); } }
      @keyframes corePulse  { 0%,100% { opacity: 1; transform: scale(1); }  50% { opacity: 0.6; transform: scale(0.85); } }
    `}</style>

    <div className="section-container" style={{ position: 'relative', zIndex: 10 }}>

      <div className="section-header">
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
          <div>
            <p className="section-eyebrow">// Practice Coverage</p>
            <h2 className="section-headline">Every Practice Area.<br />One Platform.</h2>
          </div>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '6px 14px',
            border: '1px solid rgba(255,255,255,0.05)',
            background: 'rgba(255,255,255,0.02)', flexShrink: 0,
          }}>
            <Activity size={11} style={{ color: '#4FB7C5' }} className="animate-pulse" />
            <span style={{ fontFamily: "'IBM Plex Mono'", fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.15em', color: '#4FB7C5' }}>
              GST Live — Income Tax, FEMA &amp; Company Law Expanding
            </span>
          </div>
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: 20,
      }}>
        {MODULES.map(mod => (
          <DomainCard key={mod.num} mod={mod} />
        ))}
      </div>

    </div>
  </section>
);

export default StatutoryDomains;
