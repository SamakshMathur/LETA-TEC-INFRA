import { Link } from 'react-router-dom';
import { AskLetaWidget } from '../leta';
import { DocumentLibrary } from '../documents';
import { FileText, TrendingUp, AlertCircle } from 'lucide-react';

interface LawDashboardProps {
  title: string;
  domainId: string;
  contextDesc: string;
  definition?: string;
  implDate?: string;
}

const LawDashboard: React.FC<LawDashboardProps> = ({ title, domainId, contextDesc, definition, implDate }) => {
  return (
    <div className="min-h-screen pb-20" style={{ backgroundColor: 'var(--surface)' }}>

      {/* ── Page Header — Level 1 surface (tonal shift, no border) ──────── */}
      <div
        className="pt-32 pb-20 px-4 sm:px-6 lg:px-8"
        style={{ backgroundColor: 'var(--surface-container-low)' }}
      >
        <div className="max-w-7xl mx-auto">

          {/* Meta row */}
          <div className="flex flex-wrap items-center gap-2.5 mb-5">
            <span className="badge-active">
              <span
                className="w-1.5 h-1.5 rounded-full animate-pulse"
                style={{ backgroundColor: '#4F46E5' }}
              />
              Secure Access
            </span>
            {implDate && (
              <span className="text-xs font-mono" style={{ color: '#9a9a9a' }}>
                Effective{' '}
                <span style={{ color: '#e5e2e1', fontWeight: 500 }}>{implDate}</span>
              </span>
            )}
          </div>

          {/* h1 — Orbitron */}
          <h1
            className="font-display font-bold text-3xl md:text-4xl tracking-tight mb-5"
            style={{ color: '#e5e2e1' }}
          >
            {title}
          </h1>

          {/* Definition — accent bar instead of border-l */}
          {definition && (
            <div className="flex gap-3 max-w-3xl">
              <div
                className="w-1 flex-shrink-0 rounded-full"
                style={{ backgroundColor: 'var(--primary-container)' }}
              />
              <p className="text-base font-light leading-relaxed" style={{ color: '#9a9a9a' }}>
                {definition}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Main grid — Level 0 canvas, 2.5 gap (No-Line Rule) ──────────── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-2.5">
        <div className="flex flex-col gap-2.5">

          {/* Top Row: Equal width interaction widgets */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {/* Litigation banner — Level 2 card */}
            {domainId === 'gst' && (
              <div
                className="rounded-leta p-6 relative overflow-hidden group transition-all duration-300 flex flex-col justify-center"
                style={{
                  backgroundColor: 'var(--surface-container)'
                }}
              >
                <div
                  className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none rounded-leta"
                  style={{
                    background: 'radial-gradient(circle at top right, rgba(79, 70, 229, 0.1) 0%, transparent 70%)',
                  }}
                />
                <div className="relative z-10">
                  <h2
                    className="text-lg font-bold uppercase tracking-wide flex items-center gap-2 mb-2"
                    style={{ color: '#4F46E5' }}
                  >
                    <FileText className="w-5 h-5" />
                    Litigation Support
                  </h2>
                  <p className="text-sm font-light leading-relaxed mb-6" style={{ color: '#9a9a9a' }}>
                    Access 500+ litigation templates, notices, refunds, and appeals.
                    Match your scenario instantly.
                  </p>
                  <Link to="/responses" className="btn-primary inline-block text-center w-full py-3 text-xs tracking-widest">
                    OPEN LITIGATION SUPPORT
                  </Link>
                </div>
              </div>
            )}

            {/* Leta Console Widget */}
            <AskLetaWidget domain={domainId} contextDesc={contextDesc} />
          </div>

          {/* Bottom Row: Full-width Document Library */}
          <div
            className="rounded-leta overflow-hidden"
            style={{ backgroundColor: 'var(--surface-container-low)' }}
          >
            <DocumentLibrary domainId={domainId} />
          </div>

        </div>
      </div>
    </div>
  );
};

export default LawDashboard;
