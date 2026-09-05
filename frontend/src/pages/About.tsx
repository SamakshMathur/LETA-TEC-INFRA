import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { BookOpen, Globe, Building2, Scale, ArrowRight } from 'lucide-react';

// ─── Content ────────────────────────────────────────────────────────────────
// "Our AI Modules" pulls its copy directly from MODULES in ModuleDashboard.tsx
// rather than restating it independently — one source of truth for what each
// module actually covers, so this page can't quietly drift out of sync with
// the product itself.
const MODULES = [
  {
    num: '01',
    icon: BookOpen,
    label: 'GST',
    fullName: 'Goods & Services Tax',
    tagline: 'Comprehensive indirect tax intelligence',
    status: 'Live',
    features: ['Section-level retrieval', 'Notice drafting', 'ITC analysis', 'AAR case laws'],
  },
  {
    num: '02',
    icon: Globe,
    label: 'FEMA',
    fullName: 'Foreign Exchange Management',
    tagline: 'Cross-border transaction compliance',
    status: 'Coming soon',
    features: ['RBI circulars', 'Compounding analysis', 'ODI/FDI compliance', 'FCRA advisory'],
  },
  {
    num: '03',
    icon: Building2,
    label: 'Company Law',
    fullName: 'Companies Act 2013',
    tagline: 'Corporate governance & compliance',
    status: 'Coming soon',
    features: ['MCA filings', 'Board resolutions', 'NCLT procedures', 'ROC compliance'],
  },
  {
    num: '04',
    icon: Scale,
    label: 'Income Tax',
    fullName: 'Income Tax Act 1961',
    tagline: 'Direct tax advisory & planning',
    status: 'Coming soon',
    features: ['ITR analysis', 'TDS/TCS compliance', 'Capital gains', 'Assessment orders'],
  },
];

const SOURCE_LAYERS = [
  'Statutes and Acts',
  'Rules and Regulations',
  'Case Laws and Judicial Precedents',
  'Circulars and Notifications',
  'Government and Regulatory Clarifications',
  'Orders and Decisions',
  'Departmental Guidance',
  'Legislative and Regulatory Developments',
];

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-80px' },
  transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
};

const SectionLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex items-center gap-3 mb-5">
    <span className="w-6 h-px bg-[#4FB7C5]/50" />
    <span
      className="text-[11px] font-mono uppercase tracking-[0.22em]"
      style={{ color: '#4FB7C5' }}
    >
      {children}
    </span>
  </div>
);

const About: React.FC = () => (
  <div className="min-h-screen bg-[#000000]">

    {/* ── Header ──────────────────────────────────────────────────────────── */}
    <div className="pt-[160px] pb-24 px-6 sm:px-8 text-center relative overflow-hidden">
      {/* Faint corner glow — consistent with the rest of the marketing site's
          restrained accent use, not a new visual device */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 60% 50% at 50% 0%, rgba(79,183,197,0.08), transparent 70%)',
        }}
      />
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-[11px] font-mono uppercase tracking-[0.3em] mb-6 relative"
        style={{ color: '#4FB7C5' }}
      >
        About LETA TEC
      </motion.p>
      <motion.h1
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="font-display font-normal mx-auto relative"
        style={{
          fontFamily: "'Playfair Display', Georgia, serif",
          fontSize: 'clamp(2.2rem, 5vw, 3.6rem)',
          lineHeight: 1.15,
          maxWidth: '820px',
          color: '#F8FAFC',
          letterSpacing: '-0.01em',
        }}
      >
        Statutory intelligence, engineered for
        {' '}<span style={{ color: '#67E8F9' }}>high-stakes</span> decisions.
      </motion.h1>
    </div>

    {/* ── Mission ─────────────────────────────────────────────────────────── */}
    <div className="max-w-3xl mx-auto px-6 sm:px-8 pb-24">
      <motion.div {...fadeUp}>
        <SectionLabel>Our Mission</SectionLabel>
        <p
          className="text-[#E4E4E7] font-light leading-relaxed mb-6"
          style={{ fontSize: 'clamp(1.05rem, 2vw, 1.25rem)', lineHeight: 1.7 }}
        >
          To democratize access to high-quality legal and regulatory intelligence by harnessing
          Artificial Intelligence to simplify complex Indian laws, regulations, and judicial
          precedents. Our mission is to empower businesses, legal professionals, tax
          practitioners, and compliance teams with intelligent tools for research, advisory,
          compliance, and litigation support — enabling faster, more informed decisions while
          reducing legal, tax, and regulatory risks.
        </p>
        <p className="text-base font-light leading-relaxed text-[#A7B3C2]">
          We aim to bridge the gap between the ever-growing complexity of Indian legislation and
          the need for timely, reliable, and actionable legal intelligence. Through specialized AI
          modules for GST, FEMA, Income Tax, and the Companies Act, we seek to make sophisticated
          legal research and statutory interpretation more accessible, scalable, and practical for
          businesses of every size.
        </p>
      </motion.div>
    </div>

    {/* ── Core Technology ─────────────────────────────────────────────────── */}
    <div className="border-t border-white/[0.04] bg-[#0A0F16]">
      <div className="max-w-3xl mx-auto px-6 sm:px-8 py-24">
        <motion.div {...fadeUp}>
          <SectionLabel>Core Technology</SectionLabel>
          <h2
            className="text-2xl sm:text-3xl font-semibold text-white mb-5 tracking-tight"
            style={{ fontFamily: "'Inter Tight', sans-serif" }}
          >
            AI-powered legal &amp; regulatory intelligence
          </h2>
          <p className="text-base font-light leading-relaxed text-[#A7B3C2] mb-5">
            Our core technology is an AI-driven legal and regulatory intelligence platform
            designed to understand, analyze, and interpret the complex framework of Indian laws
            and regulations.
          </p>
          <p className="text-base font-light leading-relaxed text-[#A7B3C2] mb-5">
            The platform brings together specialized AI modules for GST, FEMA, Income Tax, and the
            Companies Act, enabling users to conduct sophisticated legal and regulatory research
            across a wide range of business and professional requirements.
          </p>
          <p className="text-base font-light leading-relaxed text-[#A7B3C2] mb-10">
            Our technology is designed to work across multiple layers of legal information:
          </p>
        </motion.div>

        <motion.div
          {...fadeUp}
          className="grid grid-cols-1 sm:grid-cols-2 gap-x-10 gap-y-1"
        >
          {SOURCE_LAYERS.map((layer) => (
            <div key={layer} className="flex items-center gap-3 py-2.5 border-b border-white/[0.03]">
              <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: '#4FB7C5' }} />
              <span className="text-sm text-[#CBD5E1] font-light">{layer}</span>
            </div>
          ))}
        </motion.div>

        <motion.p
          {...fadeUp}
          className="text-base font-light leading-relaxed text-[#A7B3C2] mt-10"
        >
          By connecting these sources and interpreting them in their relevant context, our AI
          modules help users move beyond simple information retrieval toward reasoned legal and
          regulatory intelligence.
        </motion.p>
      </div>
    </div>

    {/* ── Our AI Modules ──────────────────────────────────────────────────── */}
    <div className="max-w-5xl mx-auto px-6 sm:px-8 py-24">
      <motion.div {...fadeUp}>
        <SectionLabel>Our AI Modules</SectionLabel>
        <h2
          className="text-2xl sm:text-3xl font-semibold text-white mb-3 tracking-tight"
          style={{ fontFamily: "'Inter Tight', sans-serif" }}
        >
          Four practice areas, one research engine.
        </h2>
        <p className="text-base font-light leading-relaxed text-[#A7B3C2] mb-12 max-w-2xl">
          Each module is purpose-built for its own statutory framework — not a generic legal
          chatbot stretched across domains.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        {MODULES.map((mod, i) => {
          const Icon = mod.icon;
          return (
            <motion.div
              key={mod.label}
              {...fadeUp}
              transition={{ ...fadeUp.transition, delay: i * 0.05 }}
              className="p-6 rounded-xl border border-white/[0.06] bg-[#0A0F16] hover:border-[#4FB7C5]/25 transition-colors duration-300"
            >
              <div className="flex items-start justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ background: 'rgba(79,183,197,0.08)', border: '1px solid rgba(79,183,197,0.15)' }}
                  >
                    <Icon size={18} style={{ color: '#4FB7C5' }} />
                  </div>
                  <div>
                    <p className="text-[10px] font-mono uppercase tracking-widest" style={{ color: '#4FB7C5' }}>
                      {mod.num} · {mod.label}
                    </p>
                    <h3 className="text-white font-semibold text-base tracking-tight">{mod.fullName}</h3>
                  </div>
                </div>
                <span
                  className="text-[9px] font-mono uppercase tracking-wider px-2 py-1 rounded-full flex-shrink-0"
                  style={{
                    color: mod.status === 'Live' ? '#67E8F9' : '#64748B',
                    background: mod.status === 'Live' ? 'rgba(103,232,249,0.08)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${mod.status === 'Live' ? 'rgba(103,232,249,0.25)' : 'rgba(255,255,255,0.06)'}`,
                  }}
                >
                  {mod.status}
                </span>
              </div>
              <p className="text-sm text-[#A7B3C2] font-light mb-5">{mod.tagline}</p>
              <div className="flex flex-wrap gap-2">
                {mod.features.map((f) => (
                  <span
                    key={f}
                    className="text-[11px] font-mono text-[#64748B] px-2.5 py-1 rounded-md border border-white/[0.05]"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>

    {/* ── Closing CTA ─────────────────────────────────────────────────────── */}
    <div className="border-t border-white/[0.04] py-20 px-6 text-center">
      <p className="text-lg font-light text-[#A7B3C2] mb-6 max-w-lg mx-auto">
        Ready to see reasoned legal intelligence at work on your own matters?
      </p>
      <Link
        to="/dashboard"
        className="inline-flex items-center gap-2 px-7 py-3 rounded-lg font-semibold text-[11px] uppercase tracking-wider transition-all duration-200"
        style={{ background: 'linear-gradient(135deg, #4FB7C5 0%, #67E8F9 100%)', color: '#000' }}
      >
        Enter
        <ArrowRight size={14} />
      </Link>
    </div>
  </div>
);

export default About;
