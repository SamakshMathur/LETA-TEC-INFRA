import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, Shield, Zap, Lock } from 'lucide-react';

const Hero = () => {
  return (
    <div className="relative min-h-screen flex items-center pt-24 pb-16 overflow-hidden"
      style={{ background: 'transparent' }}>

      {/* ── Ambient glow blobs ─────────────────────────────────────────────── */}
      <div className="absolute bottom-0 left-[-10%] w-[700px] h-[500px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(124,58,237,0.2) 0%, transparent 70%)', filter: 'blur(80px)' }} />
      <div className="absolute top-1/4 right-[-5%] w-[500px] h-[500px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(96,165,250,0.1) 0%, transparent 70%)', filter: 'blur(100px)' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[500px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(ellipse, rgba(124,58,237,0.06) 0%, transparent 60%)', filter: 'blur(60px)' }} />

      {/* ── Grid pattern ───────────────────────────────────────────────────── */}
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(to right, #7C3AED 1px, transparent 1px), linear-gradient(to bottom, #7C3AED 1px, transparent 1px)',
          backgroundSize: '48px 48px',
        }} />

      {/* ── Content ────────────────────────────────────────────────────────── */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

          {/* Left: Copy & CTA */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          >
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full"
              style={{
                border: '1px solid rgba(124,58,237,0.35)',
                background: 'rgba(124,58,237,0.08)',
                backdropFilter: 'blur(10px)',
              }}
            >
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: '#A78BFA' }} />
              <span className="text-[10px] font-mono font-bold uppercase tracking-[0.25em]" style={{ color: '#A78BFA' }}>
                Sovereign Layer 0
              </span>
            </motion.div>

            {/* Headline */}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.7 }}
              className="font-display font-bold text-6xl md:text-7xl lg:text-8xl uppercase tracking-tight mb-6"
              style={{ lineHeight: '1.05' }}
            >
              <span className="text-white block">Revolutionizing</span>
              <span className="block" style={{
                background: 'linear-gradient(135deg, #7C3AED 0%, #A78BFA 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>
                Digital
              </span>
              <span className="block" style={{
                background: 'linear-gradient(135deg, #60A5FA 0%, #7C3AED 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>
                Transactions
              </span>
            </motion.h1>

            {/* Subtitle */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="font-body text-lg mb-10 max-w-lg leading-relaxed"
              style={{ color: '#94A3B8' }}
            >
              Advanced cryptographic frameworks for institutional compliance,
              real-time GST intelligence, and cross-border FEMA regulatory automation.
            </motion.p>

            {/* CTAs */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="flex flex-wrap items-center gap-4"
            >
              <Link to="/gst">
                <button
                  className="flex items-center gap-2 px-7 py-3.5 rounded-xl font-bold text-[15px] text-white transition-all duration-200"
                  style={{
                    background: 'linear-gradient(135deg, #7C3AED, #5B21B6)',
                    boxShadow: '0 0 20px rgba(124,58,237,0.45)',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.boxShadow = '0 0 40px rgba(124,58,237,0.65)';
                    e.currentTarget.style.transform = 'translateY(-1px)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.boxShadow = '0 0 20px rgba(124,58,237,0.45)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  Initiate Protocol <ArrowRight size={16} />
                </button>
              </Link>
              <Link to="/docs">
                <button
                  className="px-7 py-3.5 rounded-xl font-bold text-[15px] transition-all duration-200"
                  style={{
                    border: '1px solid rgba(255,255,255,0.12)',
                    color: '#CBD5E1',
                    backdropFilter: 'blur(10px)',
                    background: 'rgba(255,255,255,0.04)',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.borderColor = 'rgba(124,58,237,0.4)';
                    e.currentTarget.style.color = '#FFFFFF';
                    e.currentTarget.style.boxShadow = '0 0 20px rgba(124,58,237,0.15)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)';
                    e.currentTarget.style.color = '#CBD5E1';
                    e.currentTarget.style.boxShadow = 'none';
                  }}
                >
                  Read Whitepaper
                </button>
              </Link>
            </motion.div>

            {/* Trust indicators */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.8 }}
              className="flex items-center gap-6 mt-10"
            >
              {[
                { icon: Shield, label: 'SOC 2 Compliant' },
                { icon: Lock,   label: '256-bit AES' },
                { icon: Zap,    label: 'Sub-30s Response' },
              ].map(({ icon: Icon, label }) => (
                <div key={label} className="flex items-center gap-1.5">
                  <Icon size={13} style={{ color: '#7C3AED' }} />
                  <span className="text-[11px] font-mono" style={{ color: '#475569' }}>
                    {label}
                  </span>
                </div>
              ))}
            </motion.div>
          </motion.div>

          {/* Right: Product preview card */}
          <motion.div
            initial={{ opacity: 0, x: 30, y: 10 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            transition={{ duration: 0.9, delay: 0.3, ease: 'easeOut' }}
            className="hidden lg:block relative"
          >
            {/* Outer glow ring */}
            <div className="absolute -inset-4 rounded-3xl pointer-events-none"
              style={{ background: 'radial-gradient(ellipse at center, rgba(124,58,237,0.15) 0%, transparent 70%)' }} />

            {/* Main card */}
            <div
              className="relative rounded-2xl overflow-hidden"
              style={{
                border: '1px solid rgba(124,58,237,0.2)',
                background: 'rgba(255,255,255,0.04)',
                backdropFilter: 'blur(20px)',
                boxShadow: '0 40px 80px rgba(0,0,0,0.6), 0 0 60px rgba(124,58,237,0.12)',
              }}
            >
              {/* Card header bar */}
              <div className="px-5 py-3 flex items-center gap-2"
                style={{ borderBottom: '1px solid rgba(124,58,237,0.12)', background: 'rgba(124,58,237,0.05)' }}>
                <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
                <span className="ml-4 text-[11px] font-mono" style={{ color: 'rgba(203,213,225,0.3)' }}>
                  LETA_TITAN // GST_INTELLIGENCE_V3
                </span>
              </div>

              {/* Mock UI content */}
              <div className="p-6 space-y-4">
                {/* Query box */}
                <div className="rounded-xl p-4"
                  style={{ background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.15)' }}>
                  <p className="text-[11px] font-mono mb-2" style={{ color: 'rgba(167,139,250,0.7)' }}>
                    &gt; QUERY_INPUT
                  </p>
                  <p className="text-[13px] font-medium" style={{ color: '#E2E8F0' }}>
                    Is ITC available on works contract for factory construction?
                  </p>
                </div>

                {/* Response preview */}
                <div className="rounded-xl p-4 space-y-2"
                  style={{ background: 'rgba(96,165,250,0.04)', border: '1px solid rgba(96,165,250,0.12)' }}>
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: '#A78BFA' }} />
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider" style={{ color: '#A78BFA' }}>
                      LETA Response — Confidence 94%
                    </span>
                  </div>
                  {['Section 17(5)(c) blocks ITC on works contract.', 'Exception: plant & machinery installation.', 'Circular 177/09/2022 clarifies scope.'].map((line, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <span className="mt-0.5 text-[10px] font-bold" style={{ color: '#A78BFA' }}>▸</span>
                      <p className="text-[12px] leading-relaxed" style={{ color: '#94A3B8' }}>{line}</p>
                    </div>
                  ))}
                </div>

                {/* Source badges */}
                <div className="flex flex-wrap gap-2">
                  {['CGST Act §17(5)', 'Circular 177/2022', 'AAR 2023'].map(src => (
                    <span key={src} className="px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold"
                      style={{ background: 'rgba(124,58,237,0.1)', color: 'rgba(167,139,250,0.8)', border: '1px solid rgba(124,58,237,0.2)' }}>
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
