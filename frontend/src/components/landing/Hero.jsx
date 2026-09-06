import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, ShieldCheck, Zap, CheckCircle } from 'lucide-react';

const METRICS = [
  { value: '94%',  label: 'Clause Accuracy' },
  { value: '2.3s', label: 'Avg Analysis' },
  { value: 'SOC2', label: 'Enterprise Secure' },
];

const Hero = () => {
  return (
    <div className="relative min-h-screen flex items-center pt-[140px] pb-[140px] overflow-hidden bg-[#000000]">

      {/* ── Layer 2: Ambient glow blobs (Subtle, muted dark teal/cyan) ─────────── */}
      <div className="absolute bottom-[-10%] left-[-8%] w-[600px] h-[500px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(103,232,249,0.03) 0%, transparent 75%)', filter: 'blur(100px)' }} />
      <div className="absolute top-[10%] right-[-8%] w-[400px] h-[400px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(103,232,249,0.02) 0%, transparent 75%)', filter: 'blur(100px)' }} />

      {/* ── Content ─────────────────────────────────────────────────────────── */}
      <div className="relative z-10 w-full px-10 lg:px-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

          {/* ── Left: Copy ──────────────────────────────────────────────────── */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          >
            {/* Status badge */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full"
              style={{
                border: '1px solid rgba(255,255,255,0.06)',
                background: 'rgba(255,255,255,0.03)',
                backdropFilter: 'blur(10px)',
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: '#67E8F9' }} />
              <span className="text-[10px] font-mono font-bold uppercase tracking-[0.25em]" style={{ color: '#67E8F9' }}>
                Sovereign System Online
              </span>
            </motion.div>

            {/* ── FIXED: Tighter vertical headline stack ───────────────────── */}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.7 }}
              className="font-display font-bold uppercase tracking-tight mb-6 text-[#F5F7FA]"
              style={{ fontSize: 'clamp(44px, 6vw, 72px)', lineHeight: '0.95', letterSpacing: '-0.04em' }}
            >
              Sovereign <br />
              Legal Intelligence
            </motion.h1>

            {/* Subtitle — enterprise-focused */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="font-body text-[18px] font-normal mb-8 max-w-lg leading-[1.7]"
              style={{ color: '#A1AAB8' }}
            >
              Enterprise-grade intelligence for statutory analysis, compliance workflows, and structured sovereign reasoning.
            </motion.p>

            {/* ── Metrics chips ────────────────────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.55 }}
              className="flex items-center gap-3 mb-8 flex-wrap"
            >
              {METRICS.map(({ value, label }) => (
                <div
                  key={label}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
                  style={{
                    background: '#10141B',
                    border: '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  <span className="text-[13px] font-bold font-mono" style={{ color: '#67E8F9' }}>{value}</span>
                  <span className="text-[10px] font-mono uppercase tracking-[0.1em]" style={{ color: '#6B7280' }}>{label}</span>
                </div>
              ))}
            </motion.div>

            {/* ── CTAs — enterprise copy ───────────────────────────────────── */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.62 }}
              className="flex flex-wrap items-center gap-3"
            >
              <Link to="/dashboard">
                <button
                  className="flex items-center gap-2 px-7 py-3.5 rounded-xl font-semibold text-[14px] text-black transition-all duration-200"
                  style={{
                    background: '#67E8F9',
                    boxShadow: 'var(--glow-primary)',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = '#5EEAD4';
                    e.currentTarget.style.transform = 'translateY(-1px)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = '#67E8F9';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  Launch Workspace <ArrowRight size={15} />
                </button>
              </Link>

              <Link to="/about">
                <button
                  className="px-7 py-3.5 rounded-xl font-semibold text-[14px] transition-all duration-200"
                  style={{
                    border: '1px solid rgba(255,255,255,0.06)',
                    color: '#A1AAB8',
                    background: 'transparent',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.borderColor = 'rgba(103,232,249,0.3)';
                    e.currentTarget.style.color = '#F5F7FA';
                    e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)';
                    e.currentTarget.style.color = '#A1AAB8';
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  Explore Platform
                </button>
              </Link>
            </motion.div>

            {/* Trust indicators */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8 }}
              className="flex items-center gap-5 mt-10"
            >
              {[
                { icon: ShieldCheck, label: 'SOC 2 Compliant' },
                { icon: CheckCircle, label: 'CGST Act Aligned' },
                { icon: Zap,         label: 'Sub-3s Response' },
              ].map(({ icon: Icon, label }) => (
                <div key={label} className="flex items-center gap-1.5">
                  <Icon size={12} style={{ color: '#67E8F9' }} />
                  <span className="text-[11px] font-mono tracking-wide" style={{ color: '#52525B' }}>{label}</span>
                </div>
              ))}
            </motion.div>
          </motion.div>

          {/* ── Layer 3: Right card — high contrast operating window ─────────── */}
          <motion.div
            initial={{ opacity: 0, x: 30, y: 10 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            transition={{ duration: 0.9, delay: 0.35, ease: 'easeOut' }}
            className="hidden lg:block relative"
          >
            {/* Card anchor glow (subtle) */}
            <div className="absolute -inset-8 rounded-3xl pointer-events-none"
              style={{
                background: 'radial-gradient(circle, rgba(103,232,249,0.04) 0%, transparent 70%)',
                filter: 'blur(20px)',
              }} />

            {/* Connector line */}
            <div className="absolute top-1/2 -left-12 -translate-y-1/2 w-10 h-[1px] pointer-events-none"
              style={{ background: 'linear-gradient(to right, transparent, rgba(255,255,255,0.06))' }} />

            {/* Main card */}
            <div
              className="relative rounded-leta overflow-hidden bg-[#151922]"
              style={{
                border: '1px solid rgba(255,255,255,0.06)',
                boxShadow: 'var(--card-shadow)',
              }}
            >
              {/* Card top bar */}
              <div className="px-5 py-3.5 flex items-center gap-2 bg-white/[0.02]"
                style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                <span className="ml-3 text-[11px] font-mono uppercase tracking-[0.1em]" style={{ color: '#52525B' }}>
                  LETA_TEC // STATUTORY_OPERATING_SYSTEM
                </span>
              </div>

              <div className="p-8 space-y-5">
                {/* Query */}
                <div className="rounded-xl p-5 bg-white/[0.03]"
                  style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
                  <p className="text-[10px] font-mono mb-2 uppercase tracking-[0.15em]" style={{ color: '#67E8F9' }}>
                    &gt; INTERROGATION_QUERY
                  </p>
                  <p className="text-[13px] font-medium" style={{ color: '#F5F7FA' }}>
                    Is ITC available on works contract for factory construction?
                  </p>
                </div>

                {/* Response */}
                <div className="rounded-xl p-5 space-y-2.5 bg-[#67E8F9]/[0.02]"
                  style={{ border: '1px solid rgba(103,232,249,0.12)' }}>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: '#67E8F9' }} />
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider" style={{ color: '#67E8F9' }}>
                      LETA TEC Response — Confidence 94%
                    </span>
                  </div>
                  {[
                    'Section 17(5)(c) blocks ITC on works contract.',
                    'Exception: plant & machinery installation.',
                    'Circular 177/09/2022 clarifies scope.',
                  ].map((line, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="mt-1 text-[9px] font-bold" style={{ color: '#67E8F9' }}>▸</span>
                      <p className="text-[13px] leading-relaxed" style={{ color: '#A1AAB8' }}>{line}</p>
                    </div>
                  ))}
                </div>

                {/* Source badges */}
                <div className="flex flex-wrap gap-2 pt-1">
                  {['CGST Act §17(5)', 'Circular 177/2022', 'AAR 2023'].map(src => (
                    <span key={src} className="px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold bg-white/[0.03]"
                      style={{ color: '#A1AAB8', border: '1px solid rgba(255,255,255,0.06)' }}>
                      {src}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
};

export default Hero;
