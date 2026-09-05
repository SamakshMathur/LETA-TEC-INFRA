import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Clock, Zap, CheckCircle2, ArrowRight, Scale, Building2, Globe } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { DashboardParticles } from '../components/effects';

const B = {
  accent:  '#4FB7C5',
  glow:    'rgba(79,183,197,0.12)',
  border:  'rgba(79,183,197,0.12)',
  borderH: 'rgba(79,183,197,0.45)',
  iconBg:  'rgba(79,183,197,0.07)',
};

// ── Modules ───────────────────────────────────────────────────────────────────
const MODULES = [
  {
    id: 'gst',
    num: '01',
    label: 'GST',
    fullName: 'Goods & Services Tax',
    tagline: 'Comprehensive indirect tax intelligence',
    route: '/gst',
    iconEl: () => <span style={{ fontSize: '22px', lineHeight: 1 }}>📚</span>,
    status: 'LIVE',
    features: ['Section-level retrieval', 'Notice drafting', 'ITC analysis', 'AAR case laws'],
  },
  {
    id: 'fema',
    num: '02',
    label: 'FEMA',
    fullName: 'Foreign Exchange Management',
    tagline: 'Cross-border transaction compliance',
    route: '/fema',
    iconEl: () => <Globe size={22} color={B.accent} />,
    status: 'COMING_SOON',
    features: ['RBI circulars', 'Compounding analysis', 'ODI/FDI compliance', 'FCRA advisory'],
  },
  {
    id: 'company-law',
    num: '03',
    label: 'Company Law',
    fullName: 'Companies Act 2013',
    tagline: 'Corporate governance & compliance',
    route: '/company-law',
    iconEl: () => <Building2 size={22} color={B.accent} />,
    status: 'COMING_SOON',
    features: ['MCA filings', 'Board resolutions', 'NCLT procedures', 'ROC compliance'],
  },
  {
    id: 'income-tax',
    num: '04',
    label: 'Income Tax',
    fullName: 'Income Tax Act 1961',
    tagline: 'Direct tax advisory & planning',
    route: '/income-tax',
    iconEl: () => <Scale size={22} color={B.accent} />,
    status: 'COMING_SOON',
    features: ['ITR analysis', 'TDS/TCS compliance', 'Capital gains', 'Assessment orders'],
  },
];

// ── Plans ─────────────────────────────────────────────────────────────────────
type Feature = string | { label: string; items: string[] };

const ACCESS_DOCS: Feature = {
  label: 'Access to',
  items: ['Bare Act', 'Rules', 'Notifications', 'Case Laws', 'Circulars', 'Other documents'],
};

const PLANS: Array<{
  id: string; label: string; price: string; duration: string;
  badge: string | null; features: Feature[];
}> = [
  {
    id: '1hr',
    label: '1-Hour Access',
    price: '₹499',
    duration: '1 hour',
    badge: null,
    features: ['Full AI workspace', ACCESS_DOCS, 'Advisory & Research', 'Appeal and notice reply drafting', 'Export & save'],
  },
  {
    id: '3hr',
    label: '3-Hour Access',
    price: '₹999',
    duration: '3 hours',
    badge: 'Best Value',
    features: ['Full AI workspace', ACCESS_DOCS, 'Advisory & Research', 'Appeal and notice reply drafting', 'Export & save', 'Priority response'],
  },
];

// ── Pricing Modal ─────────────────────────────────────────────────────────────
interface PricingModalProps {
  module: typeof MODULES[0] | null;
  onClose: () => void;
}

const PricingModal: React.FC<PricingModalProps> = ({ module, onClose }) => {
  const [selected, setSelected] = useState('3hr');
  const navigate = useNavigate();
  const { user } = useAuth();

  if (!module) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-0 sm:p-6"
        style={{ background: 'rgba(0,0,0,0.88)', backdropFilter: 'blur(12px)' }}
        onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      >
        <motion.div
          initial={{ opacity: 0, y: 60, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 40, scale: 0.97 }}
          transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          className="w-full sm:max-w-2xl rounded-t-3xl sm:rounded-2xl overflow-hidden"
          style={{ background: '#080A10', border: `1px solid ${B.border}` }}
        >
          {/* Header */}
          <div className="relative px-7 pt-7 pb-5"
            style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: `radial-gradient(ellipse at top left, ${B.glow} 0%, transparent 55%)` }}>
            <button onClick={onClose}
              className="absolute top-5 right-5 p-2 rounded-xl transition-colors"
              style={{ color: '#334155' }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#94A3B8'; (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.05)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = '#334155'; (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
              <X size={15} />
            </button>
            <div className="flex items-center gap-2.5 mb-1">
              <module.iconEl />
              <span className="text-[10px] font-mono font-bold tracking-[0.2em] uppercase ml-1" style={{ color: B.accent }}>
                {module.label}
              </span>
            </div>
            <h2 className="text-xl font-display font-bold text-white mt-2">Choose your access plan</h2>
            <p className="text-xs mt-1" style={{ color: '#475569' }}>
              Full {module.fullName} workspace — advisory, documents, and AI drafting
            </p>
          </div>

          {/* Plans */}
          <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {PLANS.map(plan => {
              const isSelected = selected === plan.id;
              return (
                <button key={plan.id} onClick={() => setSelected(plan.id)}
                  className="relative text-left p-5 rounded-xl transition-all duration-150"
                  style={{
                    background: isSelected ? B.iconBg : 'rgba(255,255,255,0.015)',
                    border: `1.5px solid ${isSelected ? B.accent : 'rgba(255,255,255,0.06)'}`,
                    boxShadow: isSelected ? `0 0 28px ${B.glow}` : 'none',
                  }}>
                  {plan.badge && (
                    <span className="absolute top-4 right-4 text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full font-mono"
                      style={{ background: B.accent, color: '#000' }}>
                      {plan.badge}
                    </span>
                  )}
                  <div className="flex items-center gap-2 mb-3">
                    <Clock size={12} style={{ color: isSelected ? B.accent : '#334155' }} />
                    <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color: isSelected ? B.accent : '#334155' }}>
                      {plan.duration}
                    </span>
                  </div>
                  <div className="mb-0.5">
                    <span className="text-3xl font-display font-bold text-white">{plan.price}</span>
                  </div>
                  <p className="text-[11px] mb-4" style={{ color: '#475569' }}>{plan.label}</p>
                  <ul className="space-y-1.5">
                    {plan.features.map((f, fi) => {
                      if (typeof f === 'string') {
                        return (
                          <li key={fi} className="flex items-center gap-2 text-[11px]" style={{ color: isSelected ? '#94A3B8' : '#334155' }}>
                            <CheckCircle2 size={10} style={{ color: isSelected ? B.accent : '#1E293B', flexShrink: 0 }} />
                            {f}
                          </li>
                        );
                      }
                      return (
                        <li key={fi}>
                          <div className="flex items-center gap-2 text-[11px]" style={{ color: isSelected ? '#94A3B8' : '#334155' }}>
                            <CheckCircle2 size={10} style={{ color: isSelected ? B.accent : '#1E293B', flexShrink: 0 }} />
                            {f.label}
                          </div>
                          <ul className="mt-1 ml-[18px] space-y-0.5">
                            {f.items.map(item => (
                              <li key={item} className="flex items-center gap-1.5 text-[10px]" style={{ color: isSelected ? '#64748B' : '#1E293B' }}>
                                <span className="w-[2px] h-[2px] rounded-full flex-shrink-0" style={{ background: isSelected ? B.accent : '#334155', opacity: 0.6 }} />
                                {item}
                              </li>
                            ))}
                          </ul>
                        </li>
                      );
                    })}
                  </ul>
                </button>
              );
            })}
          </div>

          {/* CTA */}
          <div className="px-6 pb-7">
            <button
              onClick={() => {
                onClose();
                if (user?.role === 'admin') {
                  navigate(`/${module!.id}/leta`);
                } else {
                  navigate(`/payment?module=${module!.id}&plan=${selected}`);
                }
              }}
              className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200"
              style={{ background: B.accent, color: '#000', boxShadow: `0 0 30px ${B.glow}` }}>
              <Zap size={14} />
              {user?.role === 'admin' ? 'Enter Workspace' : 'Continue to Payment'}
              <ArrowRight size={13} />
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

// ── Module Card ───────────────────────────────────────────────────────────────
const ModuleCard: React.FC<{
  mod: typeof MODULES[0];
  index: number;
  onClick: () => void;
}> = ({ mod, index, onClick }) => {
  const [hovered, setHovered] = useState(false);
  const isComingSoon = mod.status === 'COMING_SOON';

  return (
    <motion.button
      initial={{ opacity: 0, y: 28 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.42, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
      onClick={isComingSoon ? undefined : onClick}
      onMouseEnter={() => !isComingSoon && setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="group relative flex flex-col text-left w-full overflow-hidden"
      style={{
        background: isComingSoon ? '#070910' : (hovered ? '#0C0F18' : '#090B12'),
        border: `1px solid ${isComingSoon ? 'rgba(255,255,255,0.04)' : (hovered ? B.borderH : 'rgba(255,255,255,0.06)')}`,
        borderRadius: '14px',
        boxShadow: hovered ? `0 0 60px ${B.glow}` : '0 1px 0 rgba(255,255,255,0.02) inset',
        transition: 'background 0.22s, border-color 0.22s, box-shadow 0.28s',
        minHeight: '340px',
        cursor: isComingSoon ? 'default' : 'pointer',
        opacity: isComingSoon ? 0.6 : 1,
      }}
    >
      {/* Top glow edge */}
      <div style={{
        position: 'absolute', top: 0, left: '15%', right: '15%', height: '1px',
        background: `linear-gradient(90deg, transparent, ${B.accent}, transparent)`,
        opacity: hovered ? 0.7 : 0,
        transition: 'opacity 0.25s',
      }} />

      {/* Left accent strip */}
      <div style={{
        position: 'absolute', top: '18%', bottom: '18%', left: 0, width: '2px',
        background: `linear-gradient(to bottom, transparent, ${B.accent}, transparent)`,
        opacity: hovered ? 0.55 : 0,
        transition: 'opacity 0.25s',
        borderRadius: '0 2px 2px 0',
      }} />

      {/* ── Top section ── */}
      <div style={{ padding: '22px 22px 0' }}>

        {/* Number + Status */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '22px' }}>
          <span style={{
            fontFamily: 'monospace',
            fontSize: '11px',
            fontWeight: 700,
            letterSpacing: '0.06em',
            color: hovered ? B.accent : 'rgba(255,255,255,0.18)',
            transition: 'color 0.22s',
          }}>
            {mod.num}
          </span>
          {isComingSoon ? (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              padding: '3px 8px',
              borderRadius: '4px',
              border: '1px solid rgba(255,255,255,0.05)',
              background: 'transparent',
            }}>
              <span style={{
                width: '5px', height: '5px', borderRadius: '50%',
                background: '#374151',
                display: 'inline-block',
              }} />
              <span style={{
                fontSize: '8px', fontWeight: 800,
                fontFamily: 'monospace',
                letterSpacing: '0.16em',
                color: '#374151',
              }}>
                COMING SOON
              </span>
            </div>
          ) : (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '5px',
              padding: '3px 8px',
              borderRadius: '4px',
              border: `1px solid ${hovered ? B.border : 'rgba(255,255,255,0.06)'}`,
              background: hovered ? B.iconBg : 'transparent',
              transition: 'all 0.22s',
            }}>
              <span style={{
                width: '5px', height: '5px', borderRadius: '50%',
                background: B.accent,
                display: 'inline-block',
                boxShadow: hovered ? `0 0 6px ${B.accent}` : 'none',
                transition: 'box-shadow 0.22s',
              }} />
              <span style={{
                fontSize: '8px', fontWeight: 800,
                fontFamily: 'monospace',
                letterSpacing: '0.16em',
                color: hovered ? B.accent : '#475569',
                transition: 'color 0.22s',
              }}>
                LIVE
              </span>
            </div>
          )}
        </div>

        {/* Icon */}
        <div style={{ marginBottom: '18px' }}>
          <mod.iconEl />
        </div>

        {/* Label tag */}
        <span style={{
          fontSize: '9px', fontWeight: 800, textTransform: 'uppercase',
          letterSpacing: '0.24em', fontFamily: 'monospace',
          color: B.accent, display: 'block', marginBottom: '5px',
        }}>
          {mod.label}
        </span>

        {/* Module name */}
        <h3 style={{
          fontSize: '15px', fontWeight: 700, lineHeight: 1.25,
          letterSpacing: '-0.018em',
          color: '#F1F5F9',
          marginBottom: '6px',
          fontFamily: 'var(--font-display, "Inter Tight", sans-serif)',
        }}>
          {mod.fullName}
        </h3>

        {/* Tagline */}
        <p style={{ fontSize: '11px', color: '#475569', lineHeight: 1.55, marginBottom: '18px' }}>
          {mod.tagline}
        </p>
      </div>

      {/* Divider */}
      <div style={{ height: '1px', background: 'rgba(255,255,255,0.04)', margin: '0 22px' }} />

      {/* Features */}
      <div style={{ padding: '16px 22px', flex: 1 }}>
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '9px' }}>
          {mod.features.map(f => (
            <li key={f} style={{
              display: 'flex', alignItems: 'center', gap: '9px',
              fontSize: '11px',
              color: hovered ? '#8B9BB4' : '#3D4F66',
              transition: 'color 0.22s',
            }}>
              <span style={{
                width: '4px', height: '4px', borderRadius: '50%', flexShrink: 0,
                background: hovered ? B.accent : '#243044',
                transition: 'background 0.22s',
              }} />
              {f}
            </li>
          ))}
        </ul>
      </div>

      {/* Divider */}
      <div style={{ height: '1px', background: 'rgba(255,255,255,0.04)', margin: '0 22px' }} />

      {/* CTA row */}
      <div style={{
        padding: '14px 22px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        {isComingSoon ? (
          <span style={{
            fontSize: '11px', fontWeight: 500,
            color: '#1E293B',
            letterSpacing: '0.01em',
            fontStyle: 'italic',
          }}>
            Available soon
          </span>
        ) : (
          <>
            <span style={{
              fontSize: '12px', fontWeight: 600,
              color: hovered ? B.accent : '#334155',
              transition: 'color 0.22s',
              letterSpacing: '0.01em',
            }}>
              Get Access
            </span>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: '28px', height: '28px', borderRadius: '7px',
              background: hovered ? B.accent : 'rgba(255,255,255,0.04)',
              border: `1px solid ${hovered ? 'transparent' : 'rgba(255,255,255,0.07)'}`,
              transition: 'all 0.22s',
            }}>
              <ArrowRight
                size={12}
                style={{
                  color: hovered ? '#000' : '#3D4F66',
                  transform: hovered ? 'translateX(1px)' : 'none',
                  transition: 'all 0.2s',
                }}
              />
            </div>
          </>
        )}
      </div>
    </motion.button>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────
const ModuleDashboard: React.FC = () => {
  const [activeModule, setActiveModule] = useState<typeof MODULES[0] | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#05070E] pt-24 pb-20 px-6 sm:px-12 lg:px-20">
      <DashboardParticles />

      <div className="max-w-6xl mx-auto relative" style={{ zIndex: 1 }}>

        {/* ── Header ── */}
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          style={{ marginBottom: '52px' }}
        >
          {/* Welcome heading */}
          <h1 style={{
            fontSize: 'clamp(32px, 5vw, 52px)',
            fontWeight: 800,
            color: '#F8FAFC',
            letterSpacing: '-0.03em',
            lineHeight: 1.05,
            fontFamily: 'var(--font-display, "Inter Tight", sans-serif)',
            marginBottom: '10px',
          }}>
            Welcome{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}.
          </h1>

          {/* Sub-line */}
          <p style={{ fontSize: '13px', color: '#475569', letterSpacing: '0.01em' }}>
            Select a practice area to begin your session.
          </p>

          {/* Metadata strip */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '18px',
            marginTop: '22px',
            paddingTop: '18px',
            borderTop: '1px solid rgba(255,255,255,0.05)',
          }}>
            {[
              { val: '4', label: 'Practice Areas' },
              { val: 'AI', label: 'Powered Research' },
              { val: '24×7', label: 'Availability' },
            ].map((item, i) => (
              <React.Fragment key={item.val}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: B.accent, fontFamily: 'monospace' }}>
                    {item.val}
                  </span>
                  <span style={{ fontSize: '10px', color: '#3D4F66' }}>{item.label}</span>
                </div>
                {i < 2 && <span style={{ width: '1px', height: '12px', background: 'rgba(255,255,255,0.06)', display: 'block' }} />}
              </React.Fragment>
            ))}
          </div>
        </motion.div>

        {/* ── Module Grid ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {MODULES.map((mod, i) => (
            <ModuleCard
              key={mod.id}
              mod={mod}
              index={i}
              onClick={() => setActiveModule(mod)}
            />
          ))}
        </div>

        {/* ── Footer note ── */}
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
          style={{
            marginTop: '40px',
            paddingTop: '20px',
            borderTop: '1px solid rgba(255,255,255,0.04)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
          }}
        >
          <span style={{ fontSize: '10px', fontFamily: 'monospace', color: '#273344', letterSpacing: '0.04em' }}>
            Sessions expire based on plan duration
          </span>
          <span style={{ color: '#1E2D3D', fontSize: '10px' }}>·</span>
          <span style={{ fontSize: '10px', fontFamily: 'monospace', color: '#273344', letterSpacing: '0.04em' }}>
            No recurring charges
          </span>
          <span style={{ color: '#1E2D3D', fontSize: '10px' }}>·</span>
          <span style={{ fontSize: '10px', fontFamily: 'monospace', color: '#273344', letterSpacing: '0.04em' }}>
            Secured by Razorpay
          </span>
        </motion.div>
      </div>

      {/* PricingModal reserved for when Razorpay keys are configured */}
      {activeModule && <PricingModal module={activeModule} onClose={() => setActiveModule(null)} />}
    </div>
  );
};

export default ModuleDashboard;
