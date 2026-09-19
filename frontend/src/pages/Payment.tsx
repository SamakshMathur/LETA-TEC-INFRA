import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft, ArrowRight, CheckCircle2, Clock, Lock,
  ShieldCheck, Zap, Download, Loader2, MapPin,
} from 'lucide-react';
import { BASE_URL } from '../config/api';
import { AXIOS_INSTANCE } from '../utils/api';
import { useAuth } from '../hooks/useAuth';
import { LIVE_MODULE_IDS } from '../constants/routes';
import { getStoredAuthSession } from '../lib/auth-storage';
import { INDIAN_STATES } from '../constants/indianStates';
import { CONTACT_EMAIL } from '../constants/contact';
import type { Session } from '../types/auth';
import { getAuthHeaders as getAuthHeader } from '../utils/authHeaders';

export function classifyPaymentVerifyResult(
  status: number
): 'success' | 'duplicate' | 'session-expired' | 'failed' {
  if (status === 200) return 'success';
  if (status === 409) return 'duplicate';
  if (status === 401) return 'session-expired';
  return 'failed';
}

export function wasCreditedWhileModalWasOpen(
  previousSessionEndMs: number | undefined,
  newSessionEnd: string | null | undefined
): number | null {
  if (!newSessionEnd) return null;
  const newEndMs = new Date(newSessionEnd).getTime();
  if (!Number.isFinite(newEndMs)) return null;
  if (previousSessionEndMs && newEndMs <= previousSessionEndMs) return null;
  return newEndMs;
}

// Pulled out as a pure function (same reasoning as the others above) so
// the mailto link's exact shape — including that the payment ID is
// actually embedded in the body, not just told to the user to type
// themselves — is unit-tested without mounting the full page.
export function buildSupportMailtoHref(paymentId: string): string {
  const subject = encodeURIComponent('Payment issue — need help');
  const body = encodeURIComponent(
    `My payment did not go through correctly.\n\nPayment ID: ${paymentId}`
  );
  return `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;
}

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
    // TEMPORARY: ₹10 for live testing instead of the real ₹199 — must stay
    // in sync with rag-backend/app/api/payments.py's PLANS["1hr"]["amount"],
    // the actual amount Razorpay charges. Revert both once testing is done.
    price: '₹10',
    rawAmount: 10,
    duration: '1 hour',
    badge: null,
    features: ['Full AI workspace', ACCESS_DOCS, 'Advisory & Research', 'Appeal and notice reply drafting', 'Export & save'],
  },
  {
    id: '3hr',
    label: '3-Hour Access',
    price: '₹399',
    rawAmount: 399,
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

export const refreshAccessToken = async (
  login: (session: Session, persist: boolean) => void
): Promise<void> => {
  try {
    const stored = getStoredAuthSession();
    const refreshToken = stored?.tokens?.refreshToken;
    if (!stored || !refreshToken) return;
    const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (res.ok) {
      const data = await res.json();
      login({ ...stored, tokens: { ...stored.tokens, ...data.tokens } }, true);
    }
  } catch { /* non-fatal — existing token used as fallback */ }
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
  // Set only for a GENUINE payment failure (Razorpay actually charged the
  // card, and our own /verify rejected it) — not for a session-expiry or
  // duplicate/already-credited case, where the money is already accounted
  // for. This is the one moment a customer most needs a way to reach a
  // human directly, and previously had none — the only support contact in
  // the whole product lived three clicks away in Terms & Conditions.
  const [failedPaymentId, setFailedPaymentId] = useState<string | null>(null);
  const [success,  setSuccess]  = useState(false);
  const [paidPaymentId, setPaidPaymentId] = useState<string | null>(null);
  const [invoiceDownloading, setInvoiceDownloading] = useState(false);
  const [rzConfig, setRzConfig] = useState<{ key_id: string; configured: boolean } | null>(null);
  const [checkingAfterDismiss, setCheckingAfterDismiss] = useState(false);
  const [selectedStateCode, setSelectedStateCode] = useState<string>(''); // Required: no default
  const [customerType, setCustomerType] = useState<'B2C' | 'B2B'>('B2C');
  const [businessLegalName, setBusinessLegalName] = useState<string>('');
  const [customerGstin, setCustomerGstin] = useState<string>('');
  const [billingAddress, setBillingAddress] = useState<string>('');
  const [billingCity, setBillingCity] = useState<string>('');
  const preCheckoutSessionEndMsRef = useRef<number | undefined>(undefined);

  const activeUntilMs = session?.tokens?.session_end_ms;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!activeUntilMs || activeUntilMs <= Date.now()) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [activeUntilMs]);
  const hasActivePlan = !!activeUntilMs && activeUntilMs > now;
  const activeRemainingSec = hasActivePlan ? Math.max(0, Math.floor((activeUntilMs! - now) / 1000)) : 0;
  const fmtRemaining = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return h > 0
      ? `${h}h ${String(m).padStart(2, '0')}m`
      : `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  };

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
    setPayError(null);
    setFailedPaymentId(null);

    // Validate B2B fields if B2B is selected
    if (customerType === 'B2B') {
      if (!businessLegalName.trim()) {
        setPayError('Please enter your Legal Business Name for B2B tax invoice.');
        return;
      }
      const cleanGstin = customerGstin.trim().toUpperCase();
      if (!cleanGstin) {
        setPayError('Please enter your 15-character GSTIN for B2B tax invoice.');
        return;
      }
      if (cleanGstin.length !== 15) {
        setPayError('GSTIN format must be exactly 15 alphanumeric characters (e.g. 08AAGCL9166P1ZL).');
        return;
      }
    }

    // Place of Supply is required for correct tax invoice generation
    if (!selectedStateCode) {
      setPayError('Please select your Billing State (Place of Supply) to proceed with payment.');
      return;
    }

    setLoading(true);
    try {
      const loaded = await loadRazorpay();
      if (!loaded) throw new Error('Razorpay SDK failed to load');

      await refreshAccessToken(login);
      const authHeader = getAuthHeader();
      const stateObj = INDIAN_STATES.find(s => s.code === selectedStateCode);
      if (!stateObj) {
        throw new Error('Please select a valid Indian State / Union Territory.');
      }
      const customerState = stateObj.name;
      const customerStateCode = stateObj.code;

      const orderRes = await fetch(`${BASE_URL}/api/payments/create-order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({
          plan_id: planId,
          module: moduleId,
          customer_state: customerState,
          customer_state_code: customerStateCode,
          customer_type: customerType,
          business_legal_name: customerType === 'B2B' ? businessLegalName.trim() : undefined,
          customer_gstin: customerType === 'B2B' ? customerGstin.trim().toUpperCase() : undefined,
          billing_address: customerType === 'B2B' && billingAddress.trim() ? billingAddress.trim() : undefined,
          billing_city: customerType === 'B2B' && billingCity.trim() ? billingCity.trim() : undefined,
        }),
      });
      if (!orderRes.ok) {
        const err = await orderRes.json();
        throw new Error(err.detail || 'Could not create order');
      }
      const order = await orderRes.json();
      preCheckoutSessionEndMsRef.current = session?.tokens?.session_end_ms;

      const rzp = new (window as any).Razorpay({
        key: rzConfig?.key_id || (import.meta as any).env?.VITE_RAZORPAY_KEY_ID || '',
        amount: order.amount,
        currency: order.currency,
        name: 'LETA TEC — Legal Intelligence',
        description: `${mod.fullName} · ${plan.label}`,
        order_id: order.order_id,
        prefill: { email: user?.email || '' },
        theme: { color: B.accent },
        handler: async (response: any) => {
          const verifyHeader = getAuthHeader();
          const verifyRes = await fetch(`${BASE_URL}/api/payments/verify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...verifyHeader },
            body: JSON.stringify({
              razorpay_order_id:   response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature:  response.razorpay_signature,
              plan_id: planId,
              module:  moduleId,
              customer_state: customerState,
              customer_state_code: customerStateCode,
              customer_type: customerType,
              business_legal_name: customerType === 'B2B' ? businessLegalName.trim() : undefined,
              customer_gstin: customerType === 'B2B' ? customerGstin.trim().toUpperCase() : undefined,
              billing_address: customerType === 'B2B' && billingAddress.trim() ? billingAddress.trim() : undefined,
              billing_city: customerType === 'B2B' && billingCity.trim() ? billingCity.trim() : undefined,
            }),
          });
          const outcome = classifyPaymentVerifyResult(verifyRes.status);

          if (outcome === 'success') {
            try {
              const verifyData = await verifyRes.json();
              const latestSession = getStoredAuthSession() || session;
              if (latestSession && verifyData.session_end_ms) {
                login({
                  ...latestSession,
                  tokens: { ...latestSession.tokens, session_end_ms: verifyData.session_end_ms },
                  user:   { ...latestSession.user,   plan: verifyData.plan_name ?? latestSession.user?.plan },
                }, true);
              }
            } catch {}
            setPaidPaymentId(response.razorpay_payment_id);
            setSuccess(true);
          } else if (outcome === 'duplicate') {
            try {
              const meRes = await fetch(`${BASE_URL}/api/auth/me`, { headers: getAuthHeader() });
              if (meRes.ok) {
                const me = await meRes.json();
                const latestSession = getStoredAuthSession() || session;
                if (latestSession && me.session_end) {
                  login({
                    ...latestSession,
                    tokens: { ...latestSession.tokens, session_end_ms: new Date(me.session_end).getTime() },
                    user:   { ...latestSession.user,   plan: me.plan ?? latestSession.user?.plan },
                  }, true);
                }
              }
            } catch {}
            setPaidPaymentId(response.razorpay_payment_id);
            setSuccess(true);
          } else if (outcome === 'session-expired') {
            setPayError('Your session expired during checkout. Please log in again — your payment was received and will be credited once you log back in.');
            setLoading(false);
          } else {
            setPayError('Payment verification failed.');
            setFailedPaymentId(response.razorpay_payment_id);
            setLoading(false);
          }
        },
        modal: { ondismiss: handleModalDismiss },
      });

      rzp.on('payment.failed', (failRes: any) => {
        const desc = failRes?.error?.description || failRes?.error?.reason || 'Payment failed. Please try again.';
        setPayError(`Payment failed: ${desc}`);
        setLoading(false);
      });

      rzp.open();
    } catch (err: any) {
      setPayError(err.message || 'Something went wrong. Please try again.');
      setLoading(false);
    }
  };

  const handleModalDismiss = async () => {
    setCheckingAfterDismiss(true);
    try {
      await new Promise(resolve => setTimeout(resolve, 3000));
      const meRes = await fetch(`${BASE_URL}/api/auth/me`, { headers: getAuthHeader() });
      if (meRes.ok) {
        const me = await meRes.json();
        const newEndMs = wasCreditedWhileModalWasOpen(preCheckoutSessionEndMsRef.current, me.session_end);
        if (newEndMs) {
          if (session) {
            login({
              ...session,
              tokens: { ...session.tokens, session_end_ms: newEndMs },
              user:   { ...session.user,   plan: me.plan ?? session.user?.plan },
            }, true);
          }
          setSuccess(true);
          return;
        }
      }
    } catch {
    } finally {
      setCheckingAfterDismiss(false);
      setLoading(false);
    }
  };

  const handleDownloadInvoice = async () => {
    if (!paidPaymentId || invoiceDownloading) return;
    setInvoiceDownloading(true);
    setPayError(null);
    try {
      const res = await AXIOS_INSTANCE.get(`/api/payments/invoice/${paidPaymentId}`, {
        responseType: 'blob',
        headers: getAuthHeader(),
      });
      const blob = res.data;
      const disposition = (res.headers && (res.headers['content-disposition'] || res.headers['Content-Disposition'])) || '';
      const match = typeof disposition === 'string' ? disposition.match(/filename="?([^"]+)"?/) : null;
      const filename = match?.[1] || `LETA-TEC-invoice-${paidPaymentId}.pdf`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Invoice download failed:', err);
      setPayError('Could not download the invoice right now. It will still be available later — try again shortly.');
    } finally {
      setInvoiceDownloading(false);
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
          {/* #334155 measured ~1.4:1 against this near-black background —
              well under WCAG's 4.5:1 minimum for real body text. #64748B
              (already used one line above for the sibling "Your {duration}
              access..." text) is the same muted tone at a contrast that
              actually passes. */}
          <p className="text-xs mb-6 font-mono" style={{ color: '#64748B' }}>
            A confirmation has been sent to {user?.email}
          </p>

          {paidPaymentId && (
            <button
              onClick={handleDownloadInvoice}
              disabled={invoiceDownloading}
              className="w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all duration-200 mb-3 disabled:opacity-60"
              style={{ background: 'transparent', color: B.accent, border: `1.5px solid ${B.border}` }}
            >
              {invoiceDownloading
                ? <><Loader2 size={14} className="animate-spin" /> Preparing invoice…</>
                : <><Download size={14} /> Download Invoice</>}
            </button>
          )}
          {payError && (
            <p className="text-xs mb-3" style={{ color: '#EF4444' }}>{payError}</p>
          )}

          <button
            onClick={() => navigate(
              LIVE_MODULE_IDS.includes(moduleId) ? `/${moduleId}/leta` : mod.route
            )}
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
          style={{ color: '#64748B' }}
          onMouseEnter={e => (e.currentTarget.style.color = B.accent)}
          onMouseLeave={e => (e.currentTarget.style.color = '#64748B')}
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
              <p className="text-sm" style={{ color: '#64748B' }}>
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
                    <p className="text-[10px] font-mono mt-0.5" style={{ color: '#64748B' }}>incl. all taxes</p>
                  </div>
                </div>
              </div>

              <div className="px-6 py-5">
                <p className="text-[10px] font-mono uppercase tracking-widest mb-4" style={{ color: '#64748B' }}>
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
              <p className="text-[10px] font-mono uppercase tracking-widest mb-3" style={{ color: '#64748B' }}>
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
                  <span className="text-[10px] font-mono" style={{ color: '#64748B' }}>{txt}</span>
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

                {/* Customer type selection (B2C vs B2B) */}
                <div className="mt-3 mb-3 p-3 rounded-xl" style={{ background: '#05070E', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="flex items-center justify-between mb-2 text-[10px] font-mono">
                    <span style={{ color: '#94A3B8' }}>Invoice Recipient Type</span>
                    <span className="text-[9px] font-mono" style={{ color: B.accent }}>
                      {customerType === 'B2B' ? 'Business Invoice' : 'Individual'}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setCustomerType('B2C')}
                      className={`py-2 px-3 rounded-lg text-xs font-medium transition-all text-center border ${
                        customerType === 'B2C'
                          ? 'bg-[#080A10] text-white font-semibold'
                          : 'bg-transparent text-slate-400 hover:text-slate-200'
                      }`}
                      style={{ borderColor: customerType === 'B2C' ? B.accent : 'rgba(255,255,255,0.08)' }}
                    >
                      Individual (B2C)
                    </button>
                    <button
                      type="button"
                      onClick={() => setCustomerType('B2B')}
                      className={`py-2 px-3 rounded-lg text-xs font-medium transition-all text-center border ${
                        customerType === 'B2B'
                          ? 'bg-[#080A10] text-white font-semibold'
                          : 'bg-transparent text-slate-400 hover:text-slate-200'
                      }`}
                      style={{ borderColor: customerType === 'B2B' ? B.accent : 'rgba(255,255,255,0.08)' }}
                    >
                      Business (B2B)
                    </button>
                  </div>

                  {/* B2B Specific Fields */}
                  {customerType === 'B2B' && (
                    <div className="mt-3 space-y-2.5 pt-2.5" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <div>
                        <label className="block text-[10px] font-mono mb-1" style={{ color: '#94A3B8' }}>
                          Legal Business Name <span className="text-amber-400">*</span>
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. Acme Legal Tech Pvt Ltd"
                          value={businessLegalName}
                          onChange={e => setBusinessLegalName(e.target.value)}
                          className="w-full bg-[#080A10] text-xs text-white rounded-lg px-2.5 py-2 border outline-none placeholder:text-slate-600"
                          style={{ borderColor: businessLegalName.trim() ? B.border : 'rgba(255,255,255,0.1)' }}
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] font-mono mb-1" style={{ color: '#94A3B8' }}>
                          Customer GSTIN <span className="text-amber-400">*</span>
                        </label>
                        <input
                          type="text"
                          maxLength={15}
                          placeholder="15-character GSTIN (e.g. 08AAGCL9166P1ZL)"
                          value={customerGstin}
                          onChange={e => {
                            const val = e.target.value.toUpperCase();
                            setCustomerGstin(val);
                            if (val.length >= 2) {
                              const prefix = val.substring(0, 2);
                              if (INDIAN_STATES.some(s => s.code === prefix)) {
                                setSelectedStateCode(prefix);
                              }
                            }
                          }}
                          className="w-full bg-[#080A10] text-xs text-white rounded-lg px-2.5 py-2 border outline-none font-mono placeholder:text-slate-600 placeholder:font-sans"
                          style={{ borderColor: customerGstin.trim().length === 15 ? B.border : 'rgba(255,255,255,0.1)' }}
                        />
                        <p className="text-[9px] font-mono mt-1" style={{ color: '#64748B' }}>
                          Indian 15-character GSTIN for B2B tax credit.
                        </p>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-[10px] font-mono mb-1" style={{ color: '#64748B' }}>
                            Address (Optional)
                          </label>
                          <input
                            type="text"
                            placeholder="Street / Office"
                            value={billingAddress}
                            onChange={e => setBillingAddress(e.target.value)}
                            className="w-full bg-[#080A10] text-xs text-white rounded-lg px-2.5 py-1.5 border outline-none placeholder:text-slate-600"
                            style={{ borderColor: 'rgba(255,255,255,0.08)' }}
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-mono mb-1" style={{ color: '#64748B' }}>
                            City (Optional)
                          </label>
                          <input
                            type="text"
                            placeholder="City"
                            value={billingCity}
                            onChange={e => setBillingCity(e.target.value)}
                            className="w-full bg-[#080A10] text-xs text-white rounded-lg px-2.5 py-1.5 border outline-none placeholder:text-slate-600"
                            style={{ borderColor: 'rgba(255,255,255,0.08)' }}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Place of supply / billing state selector */}
                <div className="mt-2 mb-4 p-3 rounded-xl" style={{ background: '#05070E', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="flex items-center justify-between mb-1.5 text-[10px] font-mono">
                    <span className="flex items-center gap-1.5" style={{ color: '#94A3B8' }}>
                      <MapPin size={11} style={{ color: B.accent }} /> Billing State (Place of Supply)
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 font-medium">Required</span>
                  </div>
                  <select
                    value={selectedStateCode}
                    onChange={e => setSelectedStateCode(e.target.value)}
                    className="w-full bg-[#080A10] text-xs text-white rounded-lg px-2.5 py-2 border outline-none cursor-pointer"
                    style={{ borderColor: selectedStateCode ? B.border : 'rgba(245,158,11,0.3)' }}
                  >
                    <option value="" disabled className="bg-[#080A10] text-slate-500">
                      -- Select Billing State --
                    </option>
                    {INDIAN_STATES.map(st => (
                      <option key={st.code} value={st.code} className="bg-[#080A10] text-white">
                        {st.name} ({st.code})
                      </option>
                    ))}
                  </select>
                  <p className="text-[9px] font-mono mt-1.5" style={{ color: selectedStateCode ? '#475569' : '#F59E0B' }}>
                    {!selectedStateCode
                      ? 'Required for GST invoice classification (Intra/Inter-State)'
                      : selectedStateCode === '08'
                      ? 'Intra-State Supply (Rajasthan): CGST (9%) + SGST (9%)'
                      : 'Inter-State Supply: IGST (18%)'}
                  </p>
                </div>

                <div className="flex justify-between items-center mb-4">
                  <span className="text-[10px] font-mono" style={{ color: '#64748B' }}>GST (18%)</span>
                  <span className="text-[10px] font-mono" style={{ color: '#64748B' }}>Inclusive</span>
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
                  {failedPaymentId && (
                    <>
                      {' '}
                      <a
                        href={buildSupportMailtoHref(failedPaymentId)}
                        className="underline font-semibold"
                        style={{ color: '#F87171' }}
                      >
                        Contact support ({CONTACT_EMAIL})
                      </a>
                      <span className="block mt-1 font-mono text-[10px] opacity-70">
                        Payment ID: {failedPaymentId}
                      </span>
                    </>
                  )}
                </div>
              )}

              {/* CTA */}
              <div className="px-6 pb-6 pt-5">
                <button
                  onClick={hasActivePlan ? undefined : (rzConfig?.configured ? handlePay : () => navigate(mod.route))}
                  disabled={loading || hasActivePlan}
                  className="w-full py-4 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed"
                  style={{ background: B.accent, color: '#000', boxShadow: `0 0 28px ${B.glow}` }}
                >
                  {loading ? (
                    <>
                      <span className="animate-spin w-4 h-4 border-2 border-black/30 border-t-black rounded-full" />
                      {checkingAfterDismiss ? 'Checking payment status…' : 'Processing...'}
                    </>
                  ) : hasActivePlan ? (
                    <>
                      <Clock size={13} /> Active plan · {fmtRemaining(activeRemainingSec)} left
                    </>
                  ) : (
                    <>
                      {rzConfig?.configured ? <Lock size={13} /> : <Zap size={14} />}
                      {rzConfig?.configured ? `Pay ${plan.price}` : 'Enter Workspace'}
                      <ArrowRight size={13} />
                    </>
                  )}
                </button>

                {hasActivePlan && (
                  <p className="text-center text-[9px] font-mono mt-2.5" style={{ color: '#1E293B' }}>
                    You already have an active plan. You can buy a new plan once it expires.
                  </p>
                )}

                {!hasActivePlan && !rzConfig?.configured && (
                  <p className="text-center text-[9px] font-mono mt-2.5" style={{ color: '#1E293B' }}>
                    Payment system coming soon — free access during beta
                  </p>
                )}

                <p className="text-center text-[9px] font-mono mt-3" style={{ color: '#1E293B' }}>
                  By continuing you agree to our{' '}
                  <span
                    className="underline cursor-pointer"
                    style={{ color: '#64748B' }}
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
