import React from 'react';
import { Link } from 'react-router-dom';
import { AskLetaWidget } from '../leta';
import { DocumentLibrary } from '../documents';
import { FileText, Shield } from 'lucide-react';

interface LawDashboardProps {
  title: string;
  domainId: string;
  contextDesc: string;
  definition?: string;
  implDate?: string;
}

const DOMAIN_METADATA: Record<string, { title: string; subtitle: string }> = {
  gst: {
    title: 'GST Research & Advisory Intelligence',
    subtitle: 'Search notifications, circulars, rulings, litigation references, and compliance materials through a unified statutory workspace.',
  },
  'income-tax': {
    title: 'Income Tax Research & Statutory Jurisprudence',
    subtitle: 'Analyze direct tax circulars, case precedents, statutory notifications, and corporate filings under a unified advisory workspace.',
  },
  fema: {
    title: 'FEMA Compliance & Regulatory Expert System',
    subtitle: 'Search foreign exchange regulations, circulars, RBI Master Directions, and compliance filing references.',
  },
  'company-law': {
    title: 'Company Law & Corporate Jurisprudence Suite',
    subtitle: 'Navigate the Companies Act, central rules, MCA notifications, tribunal updates, and compliance filings.',
  },
};

const LawDashboard: React.FC<LawDashboardProps> = ({ title, domainId, contextDesc, definition, implDate }) => {
  const metadata = DOMAIN_METADATA[domainId] || {
    title: `${title} Intelligence Hub`,
    subtitle: definition || 'Access structured statutes, notifications, case laws, and compliance circulars through an enterprise statutory workspace.',
  };

  return (
    <div className="min-h-screen pb-24 bg-[#070B11] text-[#F4F7FA] selection:bg-[#4FB7C5]/25">
      {/* Soft, ultra-subtle ambient background radial leak (NO neon glow, 1% opacity) */}
      <div 
        className="absolute top-0 left-0 w-full h-[500px] pointer-events-none"
        style={{
          background: 'radial-gradient(circle at 50% 0%, rgba(79, 183, 197, 0.015) 0%, transparent 75%)',
        }}
      />

      {/* ── Editorial Hero Section ──────── */}
      <div className="pt-[160px] pb-12 px-6 sm:px-8 lg:px-12 relative z-10">
        <div className="max-w-[1400px] mx-auto">
          {/* Subtle Metadata Row */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[10px] font-mono uppercase tracking-[0.15em] text-[#6C7A99] mb-5">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#4FB7C5] animate-pulse" />
              Secure Statutory Access
            </span>
            <span className="hidden sm:inline text-white/[0.08]">•</span>
            <span>Updated Daily</span>
            <span className="hidden sm:inline text-white/[0.08]">•</span>
            <span>10,000+ References</span>
            <span className="hidden sm:inline text-white/[0.08]">•</span>
            <span>AI-Assisted Discovery</span>
            <span className="hidden sm:inline text-white/[0.08]">•</span>
            <span>Litigation-Ready Archives</span>
            {implDate && (
              <>
                <span className="hidden sm:inline text-white/[0.08]">•</span>
                <span>
                  Effective <span className="text-[#F4F7FA] font-medium">{implDate}</span>
                </span>
              </>
            )}
          </div>

          {/* Premium Title */}
          <h1 className="font-display font-bold text-3xl md:text-4xl lg:text-5xl tracking-tight mb-4 text-[#F4F7FA]">
            {metadata.title}
          </h1>

          {/* Subheading */}
          <p className="max-w-3xl text-sm md:text-base font-light leading-relaxed text-[#A7B3C2] mb-8">
            {metadata.subtitle}
          </p>

          <div className="h-px w-full bg-white/[0.05] mt-4" />
        </div>
      </div>

      {/* ── Main Layout Workspace ──────────── */}
      <div className="max-w-[1400px] mx-auto px-6 sm:px-8 lg:px-12 relative z-10">
        <div className="flex flex-col gap-12">
          
          {/* Top Grid: Equal height interactive support cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Litigation Banner */}
            {domainId === 'gst' ? (
              <div 
                className="rounded-xl p-8 relative overflow-hidden group transition-all duration-300 flex flex-col justify-between bg-[#0F1722] border border-white/[0.04] hover:border-[#4FB7C5]/20 shadow-lg"
              >
                <div>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="p-2.5 rounded-lg bg-[#4FB7C5]/5 border border-[#4FB7C5]/10 text-[#4FB7C5]">
                      <FileText className="w-5 h-5" />
                    </div>
                    <h3 className="text-base font-bold font-display uppercase tracking-wider text-white">
                      Litigation Support Suite
                    </h3>
                  </div>
                  <p className="text-xs md:text-sm font-light leading-relaxed text-[#A7B3C2] mb-6">
                    Access 500+ premium legal drafts, SCN response templates, refunds appeals, and statutory precedents. Instantly customized for your specific case facts.
                  </p>
                </div>
                <div>
                  <Link 
                    to="/responses" 
                    className="block text-center w-full py-3.5 text-[10px] font-mono uppercase tracking-[0.2em] bg-[#131D2B] border border-white/[0.05] hover:border-[#4FB7C5]/30 hover:bg-[#131D2B]/80 text-[#F4F7FA] rounded-lg transition-all"
                  >
                    Open Litigation Console
                  </Link>
                </div>
              </div>
            ) : (
              <div 
                className="rounded-xl p-8 relative overflow-hidden group transition-all duration-300 flex flex-col justify-between bg-[#0F1722] border border-white/[0.04] shadow-lg"
              >
                <div>
                  <div className="flex items-center gap-3 mb-4">
                    <div className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.05] text-[#6C7A99]">
                      <Shield className="w-5 h-5" />
                    </div>
                    <h3 className="text-base font-bold font-display uppercase tracking-wider text-white">
                      {title} Reference
                    </h3>
                  </div>
                  <p className="text-xs md:text-sm font-light leading-relaxed text-[#A7B3C2] mb-6">
                    Explore authoritative sections, expert interpretations, statutory circulars, and departmental briefs calibrated to current legal codes.
                  </p>
                </div>
                <div>
                  <button 
                    disabled
                    className="block text-center w-full py-3.5 text-[10px] font-mono uppercase tracking-[0.2em] bg-[#131D2B]/50 border border-white/[0.02] text-[#6C7A99] rounded-lg cursor-not-allowed"
                  >
                    Jurisdiction Calibrated
                  </button>
                </div>
              </div>
            )}

            {/* Leta Console Widget */}
            <AskLetaWidget domain={domainId} contextDesc={contextDesc} />
          </div>

          {/* Bottom Section: Full-width Document Library - No nesting wrappers, sits directly on the canvas */}
          <div className="w-full">
            <DocumentLibrary />
          </div>

        </div>
      </div>
    </div>
  );
};

export default LawDashboard;
