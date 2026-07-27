import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft, ArrowRight, CheckCircle2, Clock,
  ShieldCheck, Zap,
} from 'lucide-react';
import { BASE_URL } from '../config/api';
import { useAuth } from '../hooks/useAuth';

const B = {
  accent: '#4FB7C5',
  glow:   'rgba(79,183,197,0.12)',
  border: 'rgba(79,183,197,0.12)',
  iconBg: 'rgba(79,183,197,0.07)',
};

const MODULE_MAP: Record<string, { fullName: string; route: string; label: string }> = {
  gst:          { fullName: 'Goods & Services Tax',       route: '/gst',          label: 'GST' },
  fema:         { fullName: 'Foreign Exchange Management', route: '/fema',         label: 'FEMA' },
  'company-law':{ fullName: 'Companies Act 2013',          route: '/company-law',  label: 'Company Law' },
  'income-tax': { fullName: 'Income Tax Act 1961',         route: '/income-tax',   label: 'Income Tax' },
};

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

function loadRazorpay(): Promise<boolean> {
  return new Promise(resolve => {
    if ((window as any).Razorpay) { resolve(true); return; }
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.onload  = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

const getPayAuthHeader = (): Record<string, string> => {
  try {
    const stored = localStorage.getItem('pro.auth.session');
    if (!stored) return {};
    const parsed = JSON.parse(stored);
    const token = parsed?.tokens?.accessToken;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch { return {}; }
};

const Payment: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuth();

  const moduleId = searchParams.get('module') || 'gst';
  const planId   = searchParams.get('plan')   || '3hr';
  const mod  = MODULE_MAP[moduleId] || MODULE_MAP.gst;
  const plan = PLANS.find(p => p.id === planId) || PLANS[1];

  const [loading,  setLoading]  = useState(false);
  const [payError, setPayError] = useState<string | null>(null);
  const [success,  setSuccess]  = useState(false);
  const [rzConfig, setRzConfig] = useState<{ key_id: string; configured: boolean } | null>(null);

  useEffect(() => {
    fetch(`${BASE_URL}/api/payments/config`)
      .then(r => r.json())
      .then(setRzConfig)
      .catch(() => setRzConfig({ key_id: '', configured: false }));
  }, []);

  const handlePay = async () => {
    setLoading(true);
    setPayError(null);
    try {
      const loaded = await loadRazorpay();
      if (!loaded) throw new Error('Razorpay SDK failed to load');

      const authHeader = getPayAuthHeader();
      const orderRes = await fetch(`${BASE_URL}/api/payments/create-order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({ plan_id: planId, module: moduleId }),
      });
      if (!orderRes.ok) {
        const err = await orderRes.json();
        throw new Error(err.detail || 'Could not create order');
      }
      const order = await orderRes.json();

      const options = {
        key: rzConfig?.key_id || '',
        amount: order.amount,
        currency: order.currency,
        name: 'LETA — Legal Intelligence',
        description: `${mod.fullName} · ${plan.label}`,
        order_id: order.order_id,
        prefill: { email: user?.email || '' },
        theme: { color: B.accent },
        handler: async (response: any) => {
          const verifyRes = await fetch(`${BASE_URL}/api/payments/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...authHeader },
            body: JSON.stringify({
              razorpay_order_id:   response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature:  response.razorpay_signature,
              plan_id: planId,
              module:  moduleId,
            }),
          });
          if (verifyRes.ok) {
            setSuccess(true);
          } else {
            setPayError('Payment verification failed. Please contact support.');
            setLoading(false);
          }
        },
        modal: { ondismiss: () => setLoading(false) },
      };
      new (window as any).Razorpay(options).open();
    } catch (err: any) {
      setPayError(err.message || 'Something went wrong. Please try again.');
      setLoading(false);
    }
  };

  // ── Success state ──────────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="min-h-screen bg-[#05070E] flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.94 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="text-center max-w-sm w-full"
        >
          <div
            className="flex items-center justify-center w-16 h-16 rounded-full mx-auto mb-6"
            style={{ background: B.iconBg, border: `1px solid ${B.border}` }}
          >
            <CheckCircle2 size={28} style={{ color: B.accent }} />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2" style={{ letterSpacing: '-0.02em' }}>
            Payment Successful
          </h2>
          <p className="text-sm mb-8" style={{ color: '#475569' }}>
            Your {plan.duration} access to {mod.fullName} is now active.
          </p>
          <button
            onClick={() => navigate(mod.route)}
            className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200"
            style={{ background: B.accent, color: '#000', boxShadow: `0 0 30px ${B.glow}` }}
          >
            <Zap size={14} /> Enter Workspace <ArrowRight size={13} />
          </button>
        </motion.div>
      </div>
    );
  }

  // ── Main checkout page ─────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#05070E] pt-20 pb-16 px-4 sm:px-8">
      <div className="max-w-5xl mx-auto">

        {/* Back */}
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 text-xs mb-10 transition-colors"
          style={{ color: '#475569' }}
          onMouseEnter={e => (e.currentTarget.style.color = B.accent)}
          onMouseLeave={e => (e.currentTarget.style.color = '#475569')}
        >
          <ArrowLeft size={13} /> Back to dashboard
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 lg:gap-12 items-start">

          {/* ── Left: Order summary ── */}
          <div className="lg:col-span-3">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            >
              {/* Page header */}
              <div className="mb-8">
                <span
                  className="text-[9px] font-mono font-bold tracking-[0.22em] uppercase block mb-3"
                  style={{ color: B.accent }}
                >
                  {mod.label}
                </span>
                <h1
                  className="text-3xl font-bold text-white mb-2"
                  style={{ letterSpacing: '-0.025em', fontFamily: 'var(--font-display, "Inter Tight", sans-serif)' }}
                >
                  {mod.fullName}
                </h1>
                <p className="text-sm" style={{ color: '#475569' }}>
                  Review your order before completing payment
                </p>
              </div>

              {/* Plan card */}
              <div
                className="rounded-2xl p-6 mb-6"
                style={{ background: '#080A10', border: `1px solid ${B.border}` }}
              >
                <div className="flex items-start justify-between mb-5">
                  <div>
                    <div className="flex items-center gap-2 mb-1.5">
                      <Clock size={11} style={{ color: B.accent }} />
                      <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color: B.accent }}>
                        {plan.duration}
                      </span>
                      {plan.badge && (
                        <span
                          className="text-[8px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full font-mono"
                          style={{ background: B.accent, color: '#000' }}
                        >
                          {plan.badge}
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-semibold text-white">{plan.label}</p>
                  </div>
                  <span className="text-2xl font-bold text-white">{plan.price}</span>
                </div>

                <div style={{ height: '1px', background: 'rgba(255,255,255,0.05)', marginBottom: '20px' }} />

                <ul className="space-y-2.5">
                  {plan.features.map((f, fi) => {
                    if (typeof f === 'string') {
                      return (
                        <li key={fi} className="flex items-center gap-2 text-xs" style={{ color: '#94A3B8' }}>
                          <CheckCircle2 size={10} style={{ color: B.accent, flexShrink: 0 }} />
                          {f}
                        </li>
                      );
                    }
                    return (
                      <li key={fi}>
                        <div className="flex items-center gap-2 text-xs" style={{ color: '#94A3B8' }}>
                          <CheckCircle2 size={10} style={{ color: B.accent, flexShrink: 0 }} />
                          {f.label}
                        </div>
                        <ul className="mt-1 ml-[18px] space-y-0.5">
                          {f.items.map(item => (
                            <li key={item} className="flex items-center gap-1.5 text-[10px]" style={{ color: '#64748B' }}>
                              <span
                                className="w-[2px] h-[2px] rounded-full flex-shrink-0"
                                style={{ background: B.accent, opacity: 0.6 }}
                              />
                              {item}
                            </li>
                          ))}
                        </ul>
                      </li>
                    );
                  })}
                </ul>
              </div>

              {/* Trust badges */}
              <div className="flex items-center gap-6 flex-wrap">
                {['Secured by Razorpay', 'No recurring charges', 'Instant access'].map(txt => (
                  <div key={txt} className="flex items-center gap-1.5">
                    <ShieldCheck size={11} style={{ color: B.accent }} />
                    <span className="text-[10px] font-mono" style={{ color: '#334155' }}>{txt}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>

          {/* ── Right: Payment panel ── */}
          <div className="lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
              className="rounded-2xl p-6 lg:sticky lg:top-24"
              style={{ background: '#080A10', border: `1px solid ${B.border}` }}
            >
              <h3 className="text-sm font-semibold text-white mb-1">Complete your order</h3>
              <p className="text-xs mb-6" style={{ color: '#334155' }}>
                {user?.email || 'Secure checkout'}
              </p>

              {/* Price breakdown */}
              <div className="space-y-2.5 mb-6">
                <div className="flex justify-between text-xs">
                  <span style={{ color: '#475569' }}>{plan.label}</span>
                  <span className="text-white font-medium">{plan.price}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: '#475569' }}>GST (18%)</span>
                  <span style={{ color: '#475569' }}>Inclusive</span>
                </div>
                <div style={{ height: '1px', background: 'rgba(255,255,255,0.05)' }} />
                <div className="flex justify-between text-sm font-bold">
                  <span className="text-white">Total</span>
                  <span style={{ color: B.accent }}>{plan.price}</span>
                </div>
              </div>

              {/* Error banner */}
              {payError && (
                <div
                  className="mb-4 p-3 rounded-xl text-xs font-medium"
                  style={{
                    background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.2)',
                    color: '#F87171',
                  }}
                >
                  {payError}
                </div>
              )}

              {/* CTA */}
              {rzConfig?.configured ? (
                <button
                  onClick={handlePay}
                  disabled={loading}
                  className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed"
                  style={{ background: B.accent, color: '#000', boxShadow: `0 0 30px ${B.glow}` }}
                >
                  {loading ? (
                    <>
                      <span className="animate-spin w-4 h-4 border-2 border-black/30 border-t-black rounded-full" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Zap size={14} /> Pay {plan.price} <ArrowRight size={13} />
                    </>
                  )}
                </button>
              ) : (
                <div className="space-y-3">
                  <p className="text-center text-[10px] font-mono" style={{ color: '#475569' }}>
                    Payment system coming soon — access your session now
                  </p>
                  <button
                    onClick={() => navigate(mod.route)}
                    className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200"
                    style={{ background: B.accent, color: '#000', boxShadow: `0 0 30px ${B.glow}` }}
                  >
                    <Zap size={14} /> Enter Workspace <ArrowRight size={13} />
                  </button>
                </div>
              )}

              <p className="text-center text-[10px] font-mono mt-4" style={{ color: '#1E293B' }}>
                By continuing you agree to our{' '}
                <span
                  style={{ color: '#334155', cursor: 'pointer' }}
                  onClick={() => navigate('/legal')}
                >
                  Terms of Service
                </span>
              </p>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Payment;
