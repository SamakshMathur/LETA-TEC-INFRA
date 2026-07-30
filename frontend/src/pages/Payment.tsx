import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft, ArrowRight, CheckCircle2, Clock, Lock,
  ShieldCheck, Zap,
} from 'lucide-react';
import { BASE_URL } from '../config/api';
import { useAuth } from '../hooks/useAuth';

const B = {
  accent: '#4FB7C5',
  glow:   'rgba(79,183,197,0.12)',
  border: 'rgba(79,183,197,0.14)',
  iconBg: 'rgba(79,183,197,0.07)',
};

const MODULE_MAP: Record<string, { fullName: string; route: string; label: string }> = {
  gst:           { fullName: 'Goods & Services Tax',       route: '/gst',         label: 'GST' },
  fema:          { fullName: 'Foreign Exchange Management', route: '/fema',        label: 'FEMA' },
  'company-law': { fullName: 'Companies Act 2013',          route: '/company-law', label: 'Company Law' },
  'income-tax':  { fullName: 'Income Tax Act 1961',         route: '/income-tax',  label: 'Income Tax' },
};

type Feature = string | { label: string; items: string[] };

const ACCESS_DOCS: Feature = {
  label: 'Access to',
  items: ['Bare Act', 'Rules', 'Notifications', 'Case Laws', 'Circulars', 'Other documents'],
};

const PLANS: Array<{
  id: string; label: string; price: string; rawAmount: number; duration: string;
  badge: string | null; features: Feature[];
}> = [
  {
    id: '1hr',
    label: '1-Hour Access',
    price: '₹499',
    rawAmount: 499,
    duration: '1 hour',
    badge: null,
    features: ['Full AI workspace', ACCESS_DOCS, 'Advisory & Research', 'Appeal and notice reply drafting', 'Export & save'],
  },
  {
    id: '3hr',
    label: '3-Hour Access',
    price: '₹999',
    rawAmount: 999,
    duration: '3 hours',
    badge: 'Best Value',
    features: ['Full AI workspace', ACCESS_DOCS, 'Advisory & Research', 'Appeal and notice reply drafting', 'Export & save', 'Priority response'],
  },
];

const ACCEPTED_METHODS = [
  { name: 'VISA',       bg: '#1A1F71' },
  { name: 'Mastercard', bg: '#252525' },
  { name: 'RuPay',      bg: '#166534' },
  { name: 'UPI',        bg: '#7C3AED' },
  { name: 'Netbanking', bg: '#0369A1' },
  { name: 'Wallets',    bg: '#0F766E' },
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

const getAuthHeader = (): Record<string, string> => {
  try {
    const raw = localStorage.getItem('pro.auth.session');
    if (!raw) return {};
    const token = JSON.parse(raw)?.tokens?.accessToken;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch { return {}; }
};

// ── Main component ────────────────────────────────────────────────────────────

const Payment: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate       = useNavigate();
  const { user, session, login } = useAuth();

  const moduleId = searchParams.get('module') || 'gst';
  const planId   = searchParams.get('plan')   || '3hr';
  const mod      = MODULE_MAP[moduleId] || MODULE_MAP.gst;
  const plan     = PLANS.find(p => p.id === planId) || PLANS[1];

  const [loading,  setLoading]  = useState(false);
  const [payError, setPayError] = useState<string | null>(null);
  const [success,  setSuccess]  = useState(false);
  const [rzConfig, setRzConfig] = useState<{ key_id: string; configured: boolean } | null>(null);

  useEffect(() => {
    if (user?.role === 'admin') navigate(`/${moduleId}/leta`, { replace: true });
  }, [user, moduleId, navigate]);

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

      const authHeader = getAuthHeader();
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

      new (window as any).Razorpay({
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
            try {
              const verifyData = await verifyRes.json();
              if (session && verifyData.session_end_ms) {
                login({
                  ...session,
                  tokens: { ...session.tokens, session_end_ms: verifyData.session_end_ms },
                  user:   { ...session.user,   plan: verifyData.plan_name ?? session.user?.plan },
                }, true);
              }
            } catch {}
            setSuccess(true);
          } else {
            setPayError('Payment verification failed. Please contact support.');
            setLoading(false);
          }
        },
        modal: { ondismiss: () => setLoading(false) },
      }).open();
    } catch (err: any) {
      setPayError(err.message || 'Something went wrong. Please try again.');
      setLoading(false);
    }
  };

  // ── Success state ────────────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="min-h-screen bg-[#05070E] flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.94 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="text-center max-w-sm w-full"
        >
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.1, type: 'spring', stiffness: 300, damping: 20 }}
            className="flex items-center justify-center w-20 h-20 rounded-full mx-auto mb-6"
            style={{ background: B.iconBg, border: `1.5px solid ${B.border}`, boxShadow: `0 0 40px ${B.glow}` }}
          >
            <CheckCircle2 size={36} style={{ color: B.accent }} />
          </motion.div>
          <h2 className="text-2xl font-bold text-white mb-2" style={{ letterSpacing: '-0.02em' }}>
            Payment Successful
          </h2>
          <p className="text-sm mb-2" style={{ color: '#64748B' }}>
            Your {plan.duration} access to {mod.fullName} is now active.
          </p>
          <p className="text-xs mb-8 font-mono" style={{ color: '#334155' }}>
            A confirmation has been sent to {user?.email}
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

  // ── Checkout page ─────────────────────────────────────────────────────────────
  return (
    <div
      className="min-h-screen pt-20 pb-16 px-4 sm:px-8"
      style={{ background: 'linear-gradient(160deg, #05070E 0%, #060910 60%, #040611 100%)' }}
    >
      <div className="pointer-events-none fixed top-0 left-1/2 -translate-x-1/2 w-[700px] h-[320px] rounded-full opacity-[0.04]"
        style={{ background: `radial-gradient(ellipse, ${B.accent}, transparent 70%)`, filter: 'blur(60px)' }} />

      <div className="max-w-5xl mx-auto relative">

        <motion.button
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 text-xs mb-10 transition-colors"
          style={{ color: '#475569' }}
          onMouseEnter={e => (e.currentTarget.style.color = B.accent)}
          onMouseLeave={e => (e.currentTarget.style.color = '#475569')}
        >
          <ArrowLeft size={13} /> Back to dashboard
        </motion.button>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-10 lg:gap-14 items-start">

          {/* ── Left: Order summary ─────────────────────────────────────────────── */}
          <motion.div
            className="lg:col-span-3 space-y-6"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <div>
              <span className="text-[9px] font-mono font-bold tracking-[0.22em] uppercase block mb-2" style={{ color: B.accent }}>
                {mod.label}
              </span>
              <h1 className="text-[28px] sm:text-[34px] font-bold text-white mb-1.5"
                style={{ letterSpacing: '-0.025em' }}>
                {mod.fullName}
              </h1>
              <p className="text-sm" style={{ color: '#475569' }}>
                Review your order before completing payment
              </p>
            </div>

            {/* Plan card */}
            <div className="rounded-2xl overflow-hidden" style={{ background: '#080A10', border: `1px solid ${B.border}` }}>
              <div className="px-6 pt-5 pb-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', background: `radial-gradient(ellipse at top left, ${B.glow} 0%, transparent 60%)` }}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <Clock size={11} style={{ color: B.accent }} />
                      <span className="text-[10px] font-mono uppercase tracking-widest" style={{ color: B.accent }}>
                        {plan.duration}
                      </span>
                      {plan.badge && (
                        <span className="text-[8px] font-black uppercase tracking-widest px-2 py-0.5 rounded-full font-mono"
                          style={{ background: B.accent, color: '#000' }}>
                          {plan.badge}
                        </span>
                      )}
                    </div>
                    <p className="text-base font-semibold text-white">{plan.label}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-white">{plan.price}</p>
                    <p className="text-[10px] font-mono mt-0.5" style={{ color: '#334155' }}>incl. all taxes</p>
                  </div>
                </div>
              </div>

              <div className="px-6 py-5">
                <p className="text-[10px] font-mono uppercase tracking-widest mb-4" style={{ color: '#334155' }}>
                  What's included
                </p>
                <ul className="space-y-2.5">
                  {plan.features.map((f, fi) => {
                    if (typeof f === 'string') {
                      return (
                        <li key={fi} className="flex items-center gap-2.5 text-xs" style={{ color: '#94A3B8' }}>
                          <CheckCircle2 size={11} style={{ color: B.accent, flexShrink: 0 }} />
                          {f}
                        </li>
                      );
                    }
                    return (
                      <li key={fi}>
                        <div className="flex items-center gap-2.5 text-xs" style={{ color: '#94A3B8' }}>
                          <CheckCircle2 size={11} style={{ color: B.accent, flexShrink: 0 }} />
                          {f.label}
                        </div>
                        <ul className="mt-1.5 ml-5 space-y-1">
                          {f.items.map(item => (
                            <li key={item} className="flex items-center gap-2 text-[10px]" style={{ color: '#4A5568' }}>
                              <span className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: B.accent, opacity: 0.5 }} />
                              {item}
                            </li>
                          ))}
                        </ul>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>

            {/* Accepted methods */}
            <div className="rounded-xl px-5 py-4" style={{ background: '#080A10', border: '1px solid rgba(255,255,255,0.05)' }}>
              <p className="text-[10px] font-mono uppercase tracking-widest mb-3" style={{ color: '#334155' }}>
                Accepted payment methods
              </p>
              <div className="flex flex-wrap items-center gap-2">
                {ACCEPTED_METHODS.map(m => (
                  <div
                    key={m.name}
                    className="flex items-center justify-center rounded-md text-[10px] font-bold px-2.5 py-1.5"
                    style={{ background: m.bg, color: '#fff', minWidth: 44, letterSpacing: '0.03em' }}
                  >
                    {m.name}
                  </div>
                ))}
              </div>
            </div>

            {/* Trust signals */}
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
              {[
                { Icon: ShieldCheck, txt: 'Secured by Razorpay' },
                { Icon: Lock,        txt: '256-bit SSL encryption' },
                { Icon: ShieldCheck, txt: 'No recurring charges' },
              ].map(({ Icon, txt }) => (
                <div key={txt} className="flex items-center gap-1.5">
                  <Icon size={11} style={{ color: B.accent }} />
                  <span className="text-[10px] font-mono" style={{ color: '#334155' }}>{txt}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* ── Right: Pay panel ─────────────────────────────────────────────────── */}
          <motion.div
            className="lg:col-span-2 lg:sticky lg:top-24"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.07, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="rounded-2xl overflow-hidden" style={{ background: '#080A10', border: `1px solid ${B.border}` }}>

              {/* Price summary */}
              <div className="px-6 pt-6 pb-5" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs text-white font-semibold">{plan.label}</span>
                  <span className="text-xs text-white font-semibold">{plan.price}</span>
                </div>
                <div className="flex justify-between items-center mb-4">
                  <span className="text-[10px] font-mono" style={{ color: '#334155' }}>GST (18%)</span>
                  <span className="text-[10px] font-mono" style={{ color: '#334155' }}>Inclusive</span>
                </div>
                <div className="flex justify-between items-center pt-4" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                  <span className="text-sm font-bold text-white">Total</span>
                  <span className="text-2xl font-bold" style={{ color: B.accent }}>{plan.price}</span>
                </div>
              </div>

              {/* Error */}
              {payError && (
                <div className="mx-6 mt-5 p-3 rounded-xl text-xs font-medium"
                  style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#F87171' }}>
                  {payError}
                </div>
              )}

              {/* CTA */}
              <div className="px-6 pb-6 pt-5">
                <button
                  onClick={rzConfig?.configured ? handlePay : () => navigate(mod.route)}
                  disabled={loading}
                  className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed"
                  style={{ background: B.accent, color: '#000', boxShadow: `0 0 28px ${B.glow}` }}
                >
                  {loading ? (
                    <>
                      <span className="animate-spin w-4 h-4 border-2 border-black/30 border-t-black rounded-full" />
                      Processing...
                    </>
                  ) : (
                    <>
                      {rzConfig?.configured ? <Lock size={13} /> : <Zap size={14} />}
                      {rzConfig?.configured ? `Pay ${plan.price}` : 'Enter Workspace'}
                      <ArrowRight size={13} />
                    </>
                  )}
                </button>

                {!rzConfig?.configured && (
                  <p className="text-center text-[9px] font-mono mt-2.5" style={{ color: '#1E293B' }}>
                    Payment system coming soon — free access during beta
                  </p>
                )}

                <p className="text-center text-[9px] font-mono mt-3" style={{ color: '#1E293B' }}>
                  By continuing you agree to our{' '}
                  <span
                    className="underline cursor-pointer"
                    style={{ color: '#334155' }}
                    onClick={() => navigate('/legal')}
                  >
                    Terms of Service
                  </span>
                </p>
              </div>
            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
};

export default Payment;
