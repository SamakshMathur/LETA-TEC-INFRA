import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Clock, Zap, CheckCircle2, ArrowRight, Scale, Building2, TrendingUp, Globe } from 'lucide-react';
import { BASE_URL } from '../config/api';
import { useAuth } from '../context/AuthContext';
import DashboardParticles from '../components/effects/DashboardParticles';

// ── Brand — single accent color matching the rest of the site ─────────────────
const B = {
  accent:  '#4FB7C5',
  glow:    'rgba(79,183,197,0.10)',
  border:  'rgba(79,183,197,0.13)',
  borderH: 'rgba(79,183,197,0.35)',
  iconBg:  'rgba(79,183,197,0.08)',
};

// ── Modules ───────────────────────────────────────────────────────────────────
const MODULES = [
  {
    id: 'gst',
    label: 'GST',
    fullName: 'Goods & Services Tax',
    tagline: 'Comprehensive indirect tax intelligence',
    route: '/gst/leta',
    icon: TrendingUp,
    features: ['Section-level retrieval', 'Notice drafting', 'ITC analysis', 'AAR case laws'],
  },
  {
    id: 'fema',
    label: 'FEMA',
    fullName: 'Foreign Exchange Management',
    tagline: 'Cross-border transaction compliance',
    route: '/fema/leta',
    icon: Globe,
    features: ['RBI circulars', 'Compounding analysis', 'ODI/FDI compliance', 'FCRA advisory'],
  },
  {
    id: 'company-law',
    label: 'Company Law',
    fullName: 'Companies Act 2013',
    tagline: 'Corporate governance & compliance',
    route: '/company-law/leta',
    icon: Building2,
    features: ['MCA filings', 'Board resolutions', 'NCLT procedures', 'ROC compliance'],
  },
  {
    id: 'income-tax',
    label: 'Income Tax',
    fullName: 'Income Tax Act 1961',
    tagline: 'Direct tax advisory & planning',
    route: '/income-tax/leta',
    icon: Scale,
    features: ['ITR analysis', 'TDS/TCS compliance', 'Capital gains', 'Assessment orders'],
  },
];

// ── Plans ─────────────────────────────────────────────────────────────────────
const PLANS = [
  {
    id: '1hr',
    label: '1-Hour Access',
    price: '₹499',
    duration: '1 hour',
    badge: null as string | null,
    features: ['Full AI workspace', 'Access to: Bare Act, Rules, Notifications, Case Laws, Circulars, Other documents', 'Advisory & Research', 'Appeal and notice reply drafting', 'Export & save'],
  },
  {
    id: '3hr',
    label: '3-Hour Access',
    price: '₹999',
    duration: '3 hours',
    badge: 'Best Value' as string | null,
    features: ['Full AI workspace', 'Access to: Bare Act, Rules, Notifications, Case Laws, Circulars, Other documents', 'Advisory & Research', 'Appeal and notice reply drafting', 'Export & save', 'Priority response'],
  },
];

// ── Razorpay loader ───────────────────────────────────────────────────────────
function loadRazorpay(): Promise<boolean> {
  return new Promise(resolve => {
    if ((window as any).Razorpay) { resolve(true); return; }
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

// ── Pricing Modal ─────────────────────────────────────────────────────────────
interface PricingModalProps {
  module: typeof MODULES[0] | null;
  onClose: () => void;
}

const PricingModal: React.FC<PricingModalProps> = ({ module, onClose }) => {
  const [selected, setSelected] = useState('3hr');
  const [loading, setLoading] = useState(false);
  const [rzConfig, setRzConfig] = useState<{ key_id: string; configured: boolean } | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetch(`${BASE_URL}/api/payments/config`)
      .then(r => r.json())
      .then(setRzConfig)
      .catch(() => {});
  }, []);

  const handlePay = async () => {
    if (!module) return;
    setLoading(true);
    try {
      const loaded = await loadRazorpay();
      if (!loaded) throw new Error('Razorpay SDK failed to load');

      const orderRes = await fetch(`${BASE_URL}/api/payments/create-order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_id: selected, module: module.id }),
      });
      if (!orderRes.ok) {
        const err = await orderRes.json();
        throw new Error(err.detail || 'Could not create order');
      }
      const order = await orderRes.json();
      const plan = PLANS.find(p => p.id === selected)!;

      const options = {
        key: rzConfig?.key_id || '',
        amount: order.amount,
        currency: order.currency,
        name: 'LETA — Legal Intelligence',
        description: `${module.fullName} · ${plan.label}`,
        order_id: order.order_id,
        prefill: { email: user?.email || '' },
        theme: { color: B.accent },
        handler: async (response: any) => {
          const verifyRes = await fetch(`${BASE_URL}/api/payments/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              plan_id: selected,
              module: module.id,
            }),
          });
          if (verifyRes.ok) { onClose(); navigate(module.route); }
          else alert('Payment verification failed. Please contact support.');
        },
        modal: { ondismiss: () => setLoading(false) },
      };
      new (window as any).Razorpay(options).open();
    } catch (err: any) {
      alert(err.message || 'Something went wrong. Please try again.');
      setLoading(false);
    }
  };

  if (!module) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-0 sm:p-6"
        style={{ background: 'rgba(0,0,0,0.88)', backdropFilter: 'blur(10px)' }}
        onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      >
        <motion.div
          initial={{ opacity: 0, y: 60, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 40, scale: 0.97 }}
          transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          className="w-full sm:max-w-2xl rounded-t-3xl sm:rounded-2xl overflow-hidden"
          style={{ background: '#060608', border: `1px solid ${B.border}` }}
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
              <module.icon size={15} style={{ color: B.accent }} />
              <span className="text-[10px] font-mono font-bold tracking-[0.2em] uppercase" style={{ color: B.accent }}>
                {module.label}
              </span>
            </div>
            <h2 className="text-xl font-display font-bold text-white">Choose your access plan</h2>
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
                    {plan.features.map(f => (
                      <li key={f} className="flex items-center gap-2 text-[11px]" style={{ color: isSelected ? '#94A3B8' : '#334155' }}>
                        <CheckCircle2 size={10} style={{ color: isSelected ? B.accent : '#1E293B', flexShrink: 0 }} />
                        {f}
                      </li>
                    ))}
                  </ul>
                </button>
              );
            })}
          </div>

          {/* CTA */}
          <div className="px-6 pb-7">
            {!rzConfig?.configured && (
              <p className="text-center text-[10px] font-mono mb-3" style={{ color: '#475569' }}>
                Payment system not yet configured — Razorpay keys pending
              </p>
            )}
            <button
              onClick={handlePay}
              disabled={loading || !rzConfig?.configured}
              className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed"
              style={{
                background: rzConfig?.configured ? B.accent : 'rgba(255,255,255,0.06)',
                color: rzConfig?.configured ? '#000' : '#334155',
                boxShadow: rzConfig?.configured ? `0 0 30px ${B.glow}` : 'none',
              }}>
              {loading
                ? <><span className="animate-spin w-4 h-4 border-2 border-black/30 border-t-black rounded-full" /> Processing...</>
                : <><Zap size={14} /> Get {PLANS.find(p => p.id === selected)?.label} — {PLANS.find(p => p.id === selected)?.price} <ArrowRight size={13} /></>
              }
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────
const ModuleDashboard: React.FC = () => {
  const [activeModule, setActiveModule] = useState<typeof MODULES[0] | null>(null);
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-[#000000] pt-24 pb-20 px-6 sm:px-12 lg:px-20">
      <DashboardParticles />

      <div className="max-w-6xl mx-auto relative" style={{ zIndex: 1 }}>
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }} className="mb-14">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full mb-6"
            style={{ background: B.iconBg, border: `1px solid ${B.border}` }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: B.accent }} />
            <span className="text-[9px] font-mono font-black tracking-[0.25em] uppercase" style={{ color: B.accent }}>
              LETA Platform
            </span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-display font-bold text-white mb-3 tracking-tight">
            Welcome{user?.firstName ? `, ${user.firstName}` : ''}.
          </h1>
          <p className="text-sm" style={{ color: '#64748B' }}>
            Select a practice area to begin your session.
          </p>
        </motion.div>

        {/* Module Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {MODULES.map((mod, i) => (
            <motion.button
              key={mod.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: i * 0.07 }}
              onClick={() => setActiveModule(mod)}
              className="group relative flex flex-col text-left p-7 rounded-2xl transition-all duration-250 overflow-hidden"
              style={{ background: '#060608', border: `1px solid ${B.border}`, minHeight: '300px' }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.borderColor = B.borderH;
                (e.currentTarget as HTMLElement).style.boxShadow = `0 0 40px ${B.glow}`;
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.borderColor = B.border;
                (e.currentTarget as HTMLElement).style.boxShadow = 'none';
              }}
            >
              {/* Subtle top glow on hover */}
              <div className="absolute top-0 left-0 right-0 h-px opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{ background: `linear-gradient(90deg, transparent, ${B.accent}, transparent)` }} />

              {/* Icon */}
              <div className="mb-6 p-3 rounded-xl w-fit"
                style={{ background: B.iconBg, border: `1px solid ${B.border}` }}>
                <mod.icon size={20} style={{ color: B.accent }} />
              </div>

              {/* Text */}
              <div className="flex-1">
                <span className="text-[9px] font-mono font-black tracking-[0.22em] uppercase mb-2 block" style={{ color: B.accent }}>
                  {mod.label}
                </span>
                <h3 className="text-base font-display font-bold text-white mb-2 leading-snug">{mod.fullName}</h3>
                <p className="text-[11px] mb-5" style={{ color: '#64748B' }}>{mod.tagline}</p>

                <ul className="space-y-1.5">
                  {mod.features.map(f => (
                    <li key={f} className="flex items-center gap-2 text-[11px]" style={{ color: '#94A3B8' }}>
                      <span className="w-[3px] h-[3px] rounded-full flex-shrink-0" style={{ background: B.accent }} />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>

              {/* CTA */}
              <div className="mt-6 flex items-center gap-1.5 text-xs font-semibold" style={{ color: B.accent }}>
                Get Access
                <ArrowRight size={11} className="group-hover:translate-x-1 transition-transform duration-200" />
              </div>
            </motion.button>
          ))}
        </div>

        {/* Footnote */}
        <motion.p
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.55 }}
          className="text-center text-[10px] font-mono mt-12"
          style={{ color: '#334155' }}
        >
          Sessions expire based on plan duration · No recurring charges · Secured by Razorpay
        </motion.p>
      </div>

      {activeModule && <PricingModal module={activeModule} onClose={() => setActiveModule(null)} />}
    </div>
  );
};

export default ModuleDashboard;
