import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, Search, Cpu, FileCheck } from 'lucide-react';

const STEPS = [
  {
    num: '01', icon: Search,
    title: 'Ask in Plain Language',
    desc: 'Type your question exactly as you would ask a senior partner — a notice reply, ITC eligibility check, FEMA compliance query, or company law matter.',
    tags: ['SCN Reply', 'ITC Claim', 'FDI Advisory', 'ROC Filing'],
  },
  {
    num: '02', icon: Cpu,
    title: 'LETA TEC Retrieves & Reasons',
    desc: 'The engine cross-references 14M+ statutory provisions, circulars, notifications, tribunal orders, and HC/SC judgments to build a reasoned position.',
    tags: ['14M+ References', 'HC / SC Judgments', 'Live Circulars'],
  },
  {
    num: '03', icon: FileCheck,
    title: 'Precise, Citable Advisory',
    desc: 'Receive a structured advisory with section references, risk exposure flags, draft reply blocks, and confidence scores — ready to present to a client.',
    tags: ['Draft Ready', 'Risk Flags', 'Citation-Backed'],
  },
];

const SovereignTrust = () => (
  <section style={{
    padding: '90px 0 0',
    background: '#000',
    position: 'relative', overflow: 'hidden',
    borderTop: '1px solid rgba(255,255,255,0.03)',
  }}>

    <div aria-hidden style={{
      position: 'absolute', inset: 0, pointerEvents: 'none',
      background: 'radial-gradient(ellipse 70% 50% at 50% 100%, rgba(79,183,197,0.06) 0%, transparent 70%)',
    }} />

    <div className="section-container" style={{ position: 'relative', zIndex: 10 }}>

      {/* Header */}
      <div className="section-header">
        <p className="section-eyebrow">// How It Works</p>
        <h2 className="section-headline">From Question to<br />Advisory in Seconds.</h2>
        <p className="section-subhead" style={{ maxWidth: 520 }}>
          No forms. No waiting. LETA TEC reasons across India's full statutory
          corpus — GST, Income Tax, FEMA, and Company Law — and hands you
          a cite-ready position instantly.
        </p>
      </div>

      {/* 3-step flow */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 0, marginBottom: 1, position: 'relative',
      }}>
        <div aria-hidden style={{
          position: 'absolute', top: 52, left: '16.66%', right: '16.66%', height: 1,
          background: 'linear-gradient(to right, rgba(79,183,197,0.25), rgba(79,183,197,0.08))',
          pointerEvents: 'none', zIndex: 0,
        }} />

        {STEPS.map((step, i) => {
          const Icon = step.icon;
          return (
            <div key={i} style={{
              padding: 'clamp(28px,3.5vw,48px)',
              background: 'linear-gradient(145deg, #0a0f18 0%, #04080e 100%)',
              border: '1px solid rgba(255,255,255,0.05)',
              borderRight: i < 2 ? '1px solid rgba(255,255,255,0.04)' : '1px solid rgba(255,255,255,0.05)',
              position: 'relative', overflow: 'hidden',
            }}>
              <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, height: 1,
                background: i === 0
                  ? 'linear-gradient(90deg, #4FB7C5, rgba(79,183,197,0.3) 80%, transparent)'
                  : i === 1
                  ? 'linear-gradient(90deg, rgba(79,183,197,0.3), rgba(79,183,197,0.5), rgba(79,183,197,0.2))'
                  : 'linear-gradient(90deg, rgba(79,183,197,0.1), rgba(79,183,197,0.4))',
              }} />

              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: '50%',
                  border: '1px solid rgba(79,183,197,0.25)',
                  background: 'rgba(79,183,197,0.05)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>
                  <Icon size={16} style={{ color: '#4FB7C5' }} />
                </div>
                <span style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: 32, fontWeight: 700, lineHeight: 1,
                  color: 'rgba(79,183,197,0.14)', letterSpacing: '-0.04em',
                }}>
                  {step.num}
                </span>
              </div>

              <h3 style={{
                fontFamily: "'Inter Tight', sans-serif",
                fontSize: 'clamp(14px, 1.3vw, 17px)', fontWeight: 700,
                letterSpacing: '-0.01em', color: '#F4F7FA', margin: '0 0 10px',
              }}>
                {step.title}
              </h3>

              <p style={{
                fontFamily: "'Inter', sans-serif", fontSize: 13, fontWeight: 300,
                lineHeight: 1.70, color: 'rgba(167,179,194,0.65)', margin: '0 0 20px',
              }}>
                {step.desc}
              </p>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {step.tags.map(tag => (
                  <span key={tag} style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: 7.5, fontWeight: 700, letterSpacing: '0.14em',
                    textTransform: 'uppercase', padding: '3px 8px',
                    border: '1px solid rgba(79,183,197,0.2)',
                    color: 'rgba(79,183,197,0.65)',
                    background: 'rgba(79,183,197,0.04)',
                  }}>
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* CTA bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 24,
        padding: 'clamp(28px, 3vw, 44px) clamp(28px, 3.5vw, 52px)',
        background: 'linear-gradient(135deg, #0a1520 0%, #040c14 100%)',
        border: '1px solid rgba(79,183,197,0.15)',
        borderTop: '1px solid rgba(79,183,197,0.25)',
        marginBottom: 1,
      }}>
        <div>
          <p style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: 9, fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: '0.22em',
            color: 'rgba(79,183,197,0.6)', margin: '0 0 8px',
          }}>
            Ready when you are
          </p>
          <h3 style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            fontSize: 'clamp(20px, 2.2vw, 30px)', fontWeight: 400,
            color: '#E8DDD0', margin: 0, letterSpacing: '0.01em',
          }}>
            Your first advisory takes&nbsp;
            <span style={{ color: '#4FB7C5' }}>30 seconds.</span>
          </h3>
        </div>

        <Link to="/gst" style={{ textDecoration: 'none', flexShrink: 0 }}>
          <motion.button
            whileHover={{ boxShadow: '0 0 40px rgba(79,183,197,0.35)', y: -2 }}
            whileTap={{ scale: 0.97 }}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 12,
              padding: '14px 28px',
              background: 'linear-gradient(135deg, #4FB7C5 0%, #67E8F9 100%)',
              color: '#000', border: 'none', cursor: 'pointer',
              fontFamily: "'Inter Tight', sans-serif", fontWeight: 700,
              fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase',
            }}
          >
            Enter Command Center
            <ArrowRight size={14} />
          </motion.button>
        </Link>
      </div>

    </div>
  </section>
);

export default SovereignTrust;
