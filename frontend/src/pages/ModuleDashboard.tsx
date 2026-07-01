import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Clock, Zap, CheckCircle2, ArrowRight, Scale, Building2, TrendingUp, Globe } from 'lucide-react';
import { BASE_URL } from '../config/api';
import { useAuth } from '../context/AuthContext';

// ── Module definitions ─────────────────────────────────────────────────────────
const MODULES = [
  {
    id: 'gst',
    label: 'GST',
    fullName: 'Goods & Services Tax',
    tagline: 'Comprehensive indirect tax intelligence',
    route: '/gst/leta',
    icon: TrendingUp,
    color: '#67E8F9',
    glow: 'rgba(103,232,249,0.15)',
    border: 'rgba(103,232,249,0.2)',
    features: ['Section-level retrieval', 'Notice drafting', 'ITC analysis', 'AAR case laws'],
  },
  {
    id: 'fema',
    label: 'FEMA',
    fullName: 'Foreign Exchange Management',
    tagline: 'Cross-border transaction compliance',
    route: '/fema/leta',
    icon: Globe,
    color: '#A78BFA',
    glow: 'rgba(167,139,250,0.15)',
    border: 'rgba(167,139,250,0.2)',
    features: ['RBI circulars', 'Compounding analysis', 'ODI/FDI compliance', 'FCRA advisory'],
  },
  {
    id: 'company-law',
    label: 'Company Law',
    fullName: 'Companies Act 2013',
    tagline: 'Corporate governance & compliance',
    route: '/company-law/leta',
    icon: Building2,
    color: '#FCD34D',
    glow: 'rgba(252,211,77,0.12)',
    border: 'rgba(252,211,77,0.2)',
    features: ['MCA filings', 'Board resolutions', 'NCLT procedures', 'ROC compliance'],
  },
  {
    id: 'income-tax',
    label: 'Income Tax',
    fullName: 'Income Tax Act 1961',
    tagline: 'Direct tax advisory & planning',
    route: '/income-tax/leta',
    icon: Scale,
    color: '#34D399',
    glow: 'rgba(52,211,153,0.12)',
    border: 'rgba(52,211,153,0.2)',
    features: ['ITR analysis', 'TDS/TCS compliance', 'Capital gains', 'Assessment orders'],
  },
];

const PLANS = [
  {
    id: '1hr',
    label: '1-Hour Access',
    price: '₹499',
    rawPrice: 49900,
    duration: '1 hour',
    badge: null,
    features: ['Full AI workspace', 'All documents & case laws', 'Advisory drafting', 'Export & save'],
  },
  {
    id: '3hr',
    label: '3-Hour Access',
    price: '₹999',
    rawPrice: 99900,
    duration: '3 hours',
    badge: 'Best Value',
    features: ['Full AI workspace', 'All documents & case laws', 'Advisory drafting', 'Export & save', 'Priority response'],
  },
];

// ── Razorpay loader ────────────────────────────────────────────────────────────
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
  const [selected, setSelected] = useState<string>('3hr');
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
        theme: { color: module.color },
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
          if (verifyRes.ok) {
            onClose();
            navigate(module.route);
          } else {
            alert('Payment verification failed. Please contact support.');
          }
        },
        modal: { ondismiss: () => setLoading(false) },
      };

      const rz = new (window as any).Razorpay(options);
      rz.open();
    } catch (err: any) {
      alert(err.message || 'Something went wrong. Please try again.');
      setLoading(false);
    }
  };

  if (!module) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-6"
        style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)' }}
        onClick={e => { if (e.target === e.currentTarget) onClose(); }}
      >
        <motion.div
          initial={{ opacity: 0, y: 60, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 40, scale: 0.97 }}
          transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          className="w-full sm:max-w-2xl rounded-t-3xl sm:rounded-2xl overflow-hidden"
          style={{ background: '#080808', border: '1px solid rgba(255,255,255,0.08)' }}
        >
          {/* Header */}
          <div className="relative px-7 pt-7 pb-5"
            style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: `radial-gradient(ellipse at top left, ${module.glow} 0%, transparent 60%)` }}>
            <button onClick={onClose}
              className="absolute top-5 right-5 p-2 rounded-xl transition-colors"
              style={{ color: '#475569' }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#94A3B8'; (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.05)'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = '#475569'; (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
              <X size={16} />
            </button>
            <div className="flex items-center gap-3 mb-1">
              <module.icon size={18} style={{ color: module.color }} />
              <span className="text-xs font-mono font-bold tracking-widest uppercase" style={{ color: module.color }}>
                {module.label}
              </span>
            </div>
            <h2 className="text-xl font-bold text-white">Choose your access plan</h2>
            <p className="text-xs mt-1" style={{ color: '#64748B' }}>
              Full {module.fullName} workspace — advisory, documents, and AI drafting
            </p>
          </div>

          {/* Plans */}
          <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {PLANS.map(plan => {
              const isSelected = selected === plan.id;
              return (
                <button
                  key={plan.id}
                  onClick={() => setSelected(plan.id)}
                  className="relative text-left p-5 rounded-2xl transition-all duration-200"
                  style={{
                    background: isSelected ? `rgba(${module.color === '#67E8F9' ? '103,232,249' : module.color === '#A78BFA' ? '167,139,250' : module.color === '#FCD34D' ? '252,211,77' : '52,211,153'},0.06)` : 'rgba(255,255,255,0.02)',
                    border: `1.5px solid ${isSelected ? module.color : 'rgba(255,255,255,0.07)'}`,
                    boxShadow: isSelected ? `0 0 30px ${module.glow}` : 'none',
                  }}
                >
                  {plan.badge && (
                    <span className="absolute top-4 right-4 text-[9px] font-black uppercase tracking-widest px-2 py-1 rounded-full font-mono"
                      style={{ background: module.color, color: '#000' }}>
                      {plan.badge}
                    </span>
                  )}

                  <div className="flex items-center gap-2 mb-3">
                    <Clock size={13} style={{ color: isSelected ? module.color : '#475569' }} />
                    <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color: isSelected ? module.color : '#475569' }}>
                      {plan.duration}
                    </span>
                  </div>

                  <div className="mb-1">
                    <span className="text-3xl font-bold text-white">{plan.price}</span>
                  </div>
                  <p className="text-xs mb-4" style={{ color: '#64748B' }}>{plan.label}</p>

                  <ul className="space-y-1.5">
                    {plan.features.map(f => (
                      <li key={f} className="flex items-center gap-2 text-[11px]" style={{ color: isSelected ? '#CBD5E1' : '#475569' }}>
                        <CheckCircle2 size={10} style={{ color: isSelected ? module.color : '#334155', flexShrink: 0 }} />
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
              <p className="text-center text-[10px] font-mono mb-3" style={{ color: '#F59E0B' }}>
                ⚠ Payment system not yet configured — add Razorpay keys to activate
              </p>
            )}
            <button
              onClick={handlePay}
              disabled={loading || !rzConfig?.configured}
              className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                background: rzConfig?.configured ? module.color : 'rgba(255,255,255,0.08)',
                color: rzConfig?.configured ? '#000' : '#475569',
                boxShadow: rzConfig?.configured ? `0 0 32px ${module.glow}` : 'none',
              }}
            >
              {loading ? (
                <><span className="animate-spin w-4 h-4 border-2 border-black/30 border-t-black rounded-full" /> Processing...</>
              ) : (
                <><Zap size={15} /> Get {PLANS.find(p => p.id === selected)?.label} — {PLANS.find(p => p.id === selected)?.price} <ArrowRight size={13} /></>
              )}
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
      {/* Ambient background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden>
        <div className="absolute top-1/4 left-1/4 w-[600px] h-[600px] rounded-full opacity-[0.03]"
          style={{ background: 'radial-gradient(circle, #67E8F9 0%, transparent 70%)', filter: 'blur(80px)' }} />
        <div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] rounded-full opacity-[0.03]"
          style={{ background: 'radial-gradient(circle, #A78BFA 0%, transparent 70%)', filter: 'blur(80px)' }} />
      </div>

      <div className="max-w-6xl mx-auto relative">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-14"
        >
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full mb-6"
            style={{ background: 'rgba(103,232,249,0.06)', border: '1px solid rgba(103,232,249,0.15)' }}>
            <span className="w-1.5 h-1.5 rounded-full bg-[#67E8F9] animate-pulse" />
            <span className="text-[9px] font-mono font-black tracking-[0.25em] uppercase text-[#67E8F9]">
              LETA Platform
            </span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold text-white mb-3 tracking-tight">
            Welcome{user?.firstName ? `, ${user.firstName}` : ''}.
          </h1>
          <p className="text-sm" style={{ color: '#475569' }}>
            Select a practice area to begin your session.
          </p>
        </motion.div>

        {/* Module Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {MODULES.map((mod, i) => (
            <motion.button
              key={mod.id}
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: i * 0.08 }}
              onClick={() => setActiveModule(mod)}
              className="group relative flex flex-col text-left p-7 rounded-2xl transition-all duration-300 overflow-hidden"
              style={{
                background: '#07070A',
                border: `1px solid ${mod.border}`,
                minHeight: '300px',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = `0 0 48px ${mod.glow}, inset 0 0 40px ${mod.glow.replace('0.15', '0.04').replace('0.12', '0.04')}`;
                (e.currentTarget as HTMLElement).style.borderColor = mod.color.replace(')', ', 0.5)').replace('rgb', 'rgba');
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = 'none';
                (e.currentTarget as HTMLElement).style.borderColor = mod.border;
              }}
            >
              {/* Glow blob */}
              <div className="absolute top-0 right-0 w-32 h-32 rounded-full pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                style={{ background: `radial-gradient(circle, ${mod.glow} 0%, transparent 70%)`, filter: 'blur(20px)' }} />

              {/* Icon */}
              <div className="mb-6 p-3 rounded-xl w-fit"
                style={{ background: mod.glow, border: `1px solid ${mod.border}` }}>
                <mod.icon size={22} style={{ color: mod.color }} />
              </div>

              {/* Text */}
              <div className="flex-1">
                <span className="text-[9px] font-mono font-black tracking-[0.25em] uppercase mb-2 block" style={{ color: mod.color }}>
                  {mod.label}
                </span>
                <h3 className="text-lg font-bold text-white mb-2 leading-tight">{mod.fullName}</h3>
                <p className="text-xs mb-5" style={{ color: '#475569' }}>{mod.tagline}</p>

                <ul className="space-y-1.5">
                  {mod.features.map(f => (
                    <li key={f} className="flex items-center gap-2 text-[10px]" style={{ color: '#334155' }}>
                      <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: mod.color, opacity: 0.6 }} />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>

              {/* CTA */}
              <div className="mt-6 flex items-center gap-1.5 text-xs font-bold transition-all duration-200"
                style={{ color: mod.color }}>
                Get Access
                <ArrowRight size={12} className="group-hover:translate-x-1 transition-transform" />
              </div>
            </motion.button>
          ))}
        </div>

        {/* Footnote */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="text-center text-[10px] font-mono mt-12"
          style={{ color: '#1E293B' }}
        >
          Sessions expire based on plan duration · No recurring charges · Secure payment via Razorpay
        </motion.p>
      </div>

      {/* Pricing Modal */}
      {activeModule && (
        <PricingModal module={activeModule} onClose={() => setActiveModule(null)} />
      )}
    </div>
  );
};

export default ModuleDashboard;
