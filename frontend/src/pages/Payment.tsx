import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, ArrowRight, CheckCircle2, Clock, Lock,
  ShieldCheck, Zap, Smartphone, CreditCard, Building2, Wallet,
} from 'lucide-react';
import { BASE_URL } from '../config/api';
import { useAuth } from '../hooks/useAuth';

const B = {
  accent: '#4FB7C5',
  glow:   'rgba(79,183,197,0.12)',
  border: 'rgba(79,183,197,0.14)',
  iconBg: 'rgba(79,183,197,0.07)',
};

// ── Static data ───────────────────────────────────────────────────────────────

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

// ── Payment method config ─────────────────────────────────────────────────────

type MethodId = 'upi' | 'card' | 'netbanking' | 'wallet';

const METHODS: Array<{
  id: MethodId;
  label: string;
  Icon: React.ElementType;
  short: string;
}> = [
  { id: 'upi',        label: 'UPI',         Icon: Smartphone,  short: 'GPay, PhonePe & more' },
  { id: 'card',       label: 'Card',        Icon: CreditCard,  short: 'Visa, Mastercard, RuPay' },
  { id: 'netbanking', label: 'Net Banking', Icon: Building2,   short: '50+ banks supported' },
  { id: 'wallet',     label: 'Wallets',     Icon: Wallet,      short: 'Paytm, Amazon Pay & more' },
];

const POPULAR_BANKS = [
  { name: 'State Bank of India', short: 'SBI',     color: '#2563EB' },
  { name: 'HDFC Bank',           short: 'HDFC',    color: '#004C8F' },
  { name: 'ICICI Bank',          short: 'ICICI',   color: '#B02A30' },
  { name: 'Axis Bank',           short: 'Axis',    color: '#800000' },
  { name: 'Kotak Bank',          short: 'Kotak',   color: '#EF4444' },
  { name: 'Punjab National',     short: 'PNB',     color: '#7C3AED' },
  { name: 'Bank of Baroda',      short: 'BOB',     color: '#059669' },
  { name: 'Canara Bank',         short: 'Canara',  color: '#0369A1' },
];

const WALLETS = [
  { name: 'Paytm',       color: '#00BAF2' },
  { name: 'Amazon Pay',  color: '#FF9900' },
  { name: 'Jio Money',   color: '#0066B2' },
  { name: 'Airtel Money',color: '#E4002B' },
  { name: 'Mobikwik',    color: '#7C3AED' },
  { name: 'Freecharge',  color: '#059669' },
];

const UPI_APPS = [
  { name: 'GPay',     color: '#4285F4' },
  { name: 'PhonePe',  color: '#5F259F' },
  { name: 'Paytm',    color: '#00BAF2' },
  { name: 'BHIM',     color: '#E87722' },
  { name: 'Cred',     color: '#1A1A1A' },
  { name: 'iMobile',  color: '#B02A30' },
];

const CARD_NETWORKS = [
  { name: 'VISA',       bg: '#1A1F71', text: '#ffffff', style: 'italic font-bold tracking-tight' },
  { name: 'Mastercard', bg: '#252525', text: '#ffffff', style: 'font-bold' },
  { name: 'RuPay',      bg: '#166534', text: '#ffffff', style: 'font-bold' },
  { name: 'Amex',       bg: '#007CC3', text: '#ffffff', style: 'font-bold' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

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

// ── Sub-components ────────────────────────────────────────────────────────────

const Chip: React.FC<{ label: string; color: string }> = ({ label, color }) => (
  <div
    className="flex items-center justify-center rounded-md text-[10px] font-bold px-2.5 py-1.5 tracking-wide"
    style={{ background: color, color: '#fff', minWidth: 44, letterSpacing: '0.03em' }}
  >
    {label}
  </div>
);

const UpiMethod: React.FC<{ upiId: string; setUpiId: (v: string) => void }> = ({ upiId, setUpiId }) => (
  <div className="space-y-5">
    <div>
      <label className="block text-[10px] font-mono font-semibold uppercase tracking-widest mb-2" style={{ color: '#475569' }}>
        UPI ID
      </label>
      <div className="flex items-center rounded-xl overflow-hidden" style={{ border: `1.5px solid ${upiId ? B.accent : 'rgba(255,255,255,0.09)'}`, background: '#0B0D16', transition: 'border-color 0.2s' }}>
        <input
          type="text"
          placeholder="yourname@upi"
          value={upiId}
          onChange={e => setUpiId(e.target.value)}
          className="flex-1 bg-transparent px-4 py-3 text-sm text-white placeholder-[#334155] outline-none font-mono"
        />
        {upiId && (
          <div className="px-3">
            <CheckCircle2 size={14} style={{ color: B.accent }} />
          </div>
        )}
      </div>
      <p className="text-[10px] mt-1.5 font-mono" style={{ color: '#334155' }}>
        e.g. username@oksbi · username@paytm · username@ybl
      </p>
    </div>

    <div>
      <p className="text-[10px] font-mono uppercase tracking-widest mb-3" style={{ color: '#334155' }}>
        or pay via app
      </p>
      <div className="grid grid-cols-3 gap-2">
        {UPI_APPS.map(app => (
          <button
            key={app.name}
            type="button"
            onClick={() => setUpiId('')}
            className="flex items-center justify-center rounded-xl py-2.5 text-xs font-semibold transition-all duration-150"
            style={{ background: '#0B0D16', border: '1.5px solid rgba(255,255,255,0.07)', color: app.color }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = app.color + '66'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(255,255,255,0.07)'; }}
          >
            {app.name}
          </button>
        ))}
      </div>
    </div>
  </div>
);

const CardMethod: React.FC = () => (
  <div className="space-y-4">
    <div className="grid grid-cols-4 gap-2 mb-1">
      {CARD_NETWORKS.map(n => (
        <div
          key={n.name}
          className={`flex items-center justify-center rounded-md py-2 text-[10px] ${n.style}`}
          style={{ background: n.bg, color: n.text }}
        >
          {n.name}
        </div>
      ))}
    </div>

    <div>
      <label className="block text-[10px] font-mono font-semibold uppercase tracking-widest mb-2" style={{ color: '#475569' }}>
        Card Number
      </label>
      <div className="flex items-center rounded-xl px-4 py-3" style={{ background: '#0B0D16', border: '1.5px solid rgba(255,255,255,0.09)' }}>
        <input
          type="text"
          placeholder="1234  5678  9012  3456"
          maxLength={19}
          className="flex-1 bg-transparent text-sm text-white placeholder-[#334155] outline-none font-mono tracking-widest"
          onInput={e => {
            const v = (e.target as HTMLInputElement).value.replace(/\D/g, '').slice(0, 16);
            (e.target as HTMLInputElement).value = v.replace(/(.{4})/g, '$1  ').trim();
          }}
        />
        <CreditCard size={14} style={{ color: '#334155' }} />
      </div>
    </div>

    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="block text-[10px] font-mono font-semibold uppercase tracking-widest mb-2" style={{ color: '#475569' }}>
          Expiry
        </label>
        <input
          type="text"
          placeholder="MM / YY"
          maxLength={7}
          className="w-full rounded-xl px-4 py-3 text-sm text-white placeholder-[#334155] outline-none font-mono"
          style={{ background: '#0B0D16', border: '1.5px solid rgba(255,255,255,0.09)' }}
        />
      </div>
      <div>
        <label className="block text-[10px] font-mono font-semibold uppercase tracking-widest mb-2" style={{ color: '#475569' }}>
          CVV
        </label>
        <input
          type="password"
          placeholder="• • •"
          maxLength={4}
          className="w-full rounded-xl px-4 py-3 text-sm text-white placeholder-[#334155] outline-none font-mono"
          style={{ background: '#0B0D16', border: '1.5px solid rgba(255,255,255,0.09)' }}
        />
      </div>
    </div>

    <div>
      <label className="block text-[10px] font-mono font-semibold uppercase tracking-widest mb-2" style={{ color: '#475569' }}>
        Name on Card
      </label>
      <input
        type="text"
        placeholder="As printed on card"
        className="w-full rounded-xl px-4 py-3 text-sm text-white placeholder-[#334155] outline-none"
        style={{ background: '#0B0D16', border: '1.5px solid rgba(255,255,255,0.09)' }}
      />
    </div>

    <div className="flex items-center gap-2 rounded-xl px-3 py-2.5" style={{ background: 'rgba(79,183,197,0.05)', border: `1px solid ${B.border}` }}>
      <Lock size={11} style={{ color: B.accent, flexShrink: 0 }} />
      <p className="text-[10px] font-mono" style={{ color: '#475569' }}>
        Secured by 256-bit SSL encryption · Your card data is never stored
      </p>
    </div>
  </div>
);

const NetBankingMethod: React.FC<{
  selectedBank: string;
  setSelectedBank: (v: string) => void;
}> = ({ selectedBank, setSelectedBank }) => (
  <div className="space-y-4">
    <p className="text-[10px] font-mono uppercase tracking-widest" style={{ color: '#334155' }}>
      Popular banks
    </p>
    <div className="grid grid-cols-2 gap-2">
      {POPULAR_BANKS.map(bank => {
        const active = selectedBank === bank.short;
        return (
          <button
            key={bank.short}
            type="button"
            onClick={() => setSelectedBank(active ? '' : bank.short)}
            className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all duration-150"
            style={{
              background: active ? B.iconBg : '#0B0D16',
              border: `1.5px solid ${active ? B.accent : 'rgba(255,255,255,0.07)'}`,
            }}
          >
            <div className="w-7 h-7 rounded-lg flex items-center justify-center text-[9px] font-black" style={{ background: bank.color }}>
              <span className="text-white">{bank.short.slice(0, 3)}</span>
            </div>
            <span className="text-xs font-medium" style={{ color: active ? '#F1F5F9' : '#64748B' }}>
              {bank.name}
            </span>
          </button>
        );
      })}
    </div>
    <div>
      <label className="block text-[10px] font-mono font-semibold uppercase tracking-widest mb-2" style={{ color: '#475569' }}>
        Other banks
      </label>
      <select
        className="w-full rounded-xl px-4 py-3 text-sm outline-none appearance-none"
        style={{ background: '#0B0D16', border: '1.5px solid rgba(255,255,255,0.09)', color: selectedBank && !POPULAR_BANKS.find(b => b.short === selectedBank) ? '#F1F5F9' : '#334155' }}
        value={POPULAR_BANKS.find(b => b.short === selectedBank) ? '' : selectedBank}
        onChange={e => setSelectedBank(e.target.value)}
      >
        <option value="">Select your bank</option>
        {['Bank of India', 'Union Bank', 'Indian Bank', 'Central Bank', 'Bandhan Bank', 'IDBI Bank', 'Yes Bank', 'Federal Bank', 'South Indian Bank', 'Karnataka Bank'].map(b => (
          <option key={b} value={b}>{b}</option>
        ))}
      </select>
    </div>
  </div>
);

const WalletMethod: React.FC<{
  selectedWallet: string;
  setSelectedWallet: (v: string) => void;
}> = ({ selectedWallet, setSelectedWallet }) => (
  <div className="grid grid-cols-2 gap-2">
    {WALLETS.map(w => {
      const active = selectedWallet === w.name;
      return (
        <button
          key={w.name}
          type="button"
          onClick={() => setSelectedWallet(active ? '' : w.name)}
          className="flex items-center gap-3 rounded-xl px-3 py-3 text-left transition-all duration-150"
          style={{
            background: active ? B.iconBg : '#0B0D16',
            border: `1.5px solid ${active ? B.accent : 'rgba(255,255,255,0.07)'}`,
          }}
        >
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center text-[8px] font-black"
            style={{ background: w.color }}
          >
            <span className="text-white">{w.name.slice(0, 2).toUpperCase()}</span>
          </div>
          <span className="text-xs font-medium" style={{ color: active ? '#F1F5F9' : '#64748B' }}>
            {w.name}
          </span>
        </button>
      );
    })}
  </div>
);

// ── Main component ────────────────────────────────────────────────────────────

const Payment: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate       = useNavigate();
  const { user, session, login } = useAuth();

  const moduleId = searchParams.get('module') || 'gst';
  const planId   = searchParams.get('plan')   || '3hr';
  const mod      = MODULE_MAP[moduleId] || MODULE_MAP.gst;
  const plan     = PLANS.find(p => p.id === planId) || PLANS[1];

  const [activeMethod,    setActiveMethod]    = useState<MethodId>('upi');
  const [upiId,           setUpiId]           = useState('');
  const [selectedBank,    setSelectedBank]    = useState('');
  const [selectedWallet,  setSelectedWallet]  = useState('');
  const [loading,         setLoading]         = useState(false);
  const [payError,        setPayError]        = useState<string | null>(null);
  const [success,         setSuccess]         = useState(false);
  const [rzConfig,        setRzConfig]        = useState<{ key_id: string; configured: boolean } | null>(null);

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

      const prefill: Record<string, string> = { email: user?.email || '' };
      if (activeMethod === 'upi' && upiId.trim()) prefill.vpa = upiId.trim();

      const options: Record<string, any> = {
        key: rzConfig?.key_id || '',
        amount: order.amount,
        currency: order.currency,
        name: 'LETA — Legal Intelligence',
        description: `${mod.fullName} · ${plan.label}`,
        order_id: order.order_id,
        prefill,
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
            // Update session in React context (and localStorage) so SessionClock starts immediately
            try {
              const verifyData = await verifyRes.json();
              if (session && verifyData.session_end_ms) {
                const updatedSession = {
                  ...session,
                  tokens: { ...session.tokens, session_end_ms: verifyData.session_end_ms },
                  user:   { ...session.user,   plan: verifyData.plan_name ?? session.user?.plan },
                };
                login(updatedSession, true);
              }
            } catch {}
            setSuccess(true);
          } else {
            setPayError('Payment verification failed. Please contact support.');
            setLoading(false);
          }
        },
        modal: { ondismiss: () => setLoading(false) },
      };

      // Hint Razorpay toward the selected method
      if (activeMethod === 'upi')        options.method = { upi: true };
      if (activeMethod === 'card')       options.method = { card: true };
      if (activeMethod === 'netbanking') options.method = { netbanking: true };
      if (activeMethod === 'wallet')     options.method = { wallet: true };

      new (window as any).Razorpay(options).open();
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
  const methodContent: Record<MethodId, React.ReactNode> = {
    upi:        <UpiMethod upiId={upiId} setUpiId={setUpiId} />,
    card:       <CardMethod />,
    netbanking: <NetBankingMethod selectedBank={selectedBank} setSelectedBank={setSelectedBank} />,
    wallet:     <WalletMethod selectedWallet={selectedWallet} setSelectedWallet={setSelectedWallet} />,
  };

  const ctaLabel = rzConfig?.configured
    ? `Pay ${plan.price}`
    : 'Enter Workspace';

  return (
    <div
      className="min-h-screen pt-20 pb-16 px-4 sm:px-8"
      style={{ background: 'linear-gradient(160deg, #05070E 0%, #060910 60%, #040611 100%)' }}
    >
      {/* Subtle top glow */}
      <div className="pointer-events-none fixed top-0 left-1/2 -translate-x-1/2 w-[700px] h-[320px] rounded-full opacity-[0.04]"
        style={{ background: `radial-gradient(ellipse, ${B.accent}, transparent 70%)`, filter: 'blur(60px)' }} />

      <div className="max-w-5xl mx-auto relative">

        {/* Back */}
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
            {/* Header */}
            <div>
              <span className="text-[9px] font-mono font-bold tracking-[0.22em] uppercase block mb-2" style={{ color: B.accent }}>
                {mod.label}
              </span>
              <h1 className="text-[28px] sm:text-[34px] font-bold text-white mb-1.5"
                style={{ letterSpacing: '-0.025em', fontFamily: 'var(--font-display, "Inter Tight", sans-serif)' }}>
                {mod.fullName}
              </h1>
              <p className="text-sm" style={{ color: '#475569' }}>
                Review your order before completing payment
              </p>
            </div>

            {/* Plan card */}
            <div className="rounded-2xl overflow-hidden" style={{ background: '#080A10', border: `1px solid ${B.border}` }}>
              {/* Card header */}
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

              {/* Features */}
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

            {/* Accepted payment methods row */}
            <div className="rounded-xl px-5 py-4" style={{ background: '#080A10', border: '1px solid rgba(255,255,255,0.05)' }}>
              <p className="text-[10px] font-mono uppercase tracking-widest mb-3" style={{ color: '#334155' }}>
                Accepted payment methods
              </p>
              <div className="flex flex-wrap items-center gap-2">
                {[...CARD_NETWORKS.map(n => ({ name: n.name, bg: n.bg })),
                  { name: 'UPI', bg: '#7C3AED' },
                  { name: 'Netbanking', bg: '#0369A1' },
                  { name: 'Wallets', bg: '#0F766E' },
                ].map(m => (
                  <Chip key={m.name} label={m.name} color={m.bg} />
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

          {/* ── Right: Payment panel ─────────────────────────────────────────────── */}
          <motion.div
            className="lg:col-span-2 lg:sticky lg:top-24"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.07, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="rounded-2xl overflow-hidden" style={{ background: '#080A10', border: `1px solid ${B.border}` }}>

              {/* Order summary row */}
              <div className="px-6 pt-5 pb-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-xs text-white font-semibold">{plan.label}</span>
                  <span className="text-xs text-white font-semibold">{plan.price}</span>
                </div>
                <div className="flex justify-between items-center mb-3">
                  <span className="text-[10px] font-mono" style={{ color: '#334155' }}>GST (18%)</span>
                  <span className="text-[10px] font-mono" style={{ color: '#334155' }}>Inclusive</span>
                </div>
                <div className="flex justify-between items-center pt-3" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                  <span className="text-sm font-bold text-white">Total</span>
                  <span className="text-lg font-bold" style={{ color: B.accent }}>{plan.price}</span>
                </div>
              </div>

              {/* Method selector */}
              <div className="px-6 pt-5">
                <p className="text-[10px] font-mono uppercase tracking-widest mb-3" style={{ color: '#475569' }}>
                  Pay via
                </p>
                <div className="grid grid-cols-4 gap-1.5 mb-5">
                  {METHODS.map(m => {
                    const active = activeMethod === m.id;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => setActiveMethod(m.id)}
                        className="flex flex-col items-center gap-1 py-2.5 rounded-xl text-center transition-all duration-150"
                        style={{
                          background: active ? B.iconBg : 'transparent',
                          border: `1.5px solid ${active ? B.accent : 'rgba(255,255,255,0.07)'}`,
                        }}
                      >
                        <m.Icon
                          size={14}
                          style={{ color: active ? B.accent : '#475569', transition: 'color 0.15s' }}
                        />
                        <span className="text-[9px] font-mono leading-tight" style={{ color: active ? B.accent : '#475569' }}>
                          {m.label}
                        </span>
                      </button>
                    );
                  })}
                </div>

                {/* Method short description */}
                <p className="text-[10px] font-mono mb-4" style={{ color: '#334155' }}>
                  {METHODS.find(m => m.id === activeMethod)?.short}
                </p>

                {/* Method content */}
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeMethod}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.18 }}
                  >
                    {methodContent[activeMethod]}
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Error */}
              {payError && (
                <div className="mx-6 mt-4 p-3 rounded-xl text-xs font-medium"
                  style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#F87171' }}>
                  {payError}
                </div>
              )}

              {/* Pay button */}
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
                      {ctaLabel} <ArrowRight size={13} />
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
