import { useEffect, useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Clock, X } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { ROUTES } from '../../constants/routes';

// How far ahead of expiry to show the renewal warning toast. The small
// badge color (amber/red) was the ONLY advance notice before this — easy
// to miss in a corner while composing a message — and the moment of
// expiry itself was a silent, instant logout+redirect with zero warning,
// including mid-stream or mid-upload. This doesn't stop that hard cutoff
// (the plan really has expired, and the backend now enforces that too —
// see _verify_plan_active), but it gives a real chance to finish up or
// go renew before it happens instead of finding out only afterward.
const WARNING_THRESHOLD_SEC = 120;

const fmt = (s: number) => {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0
    ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
};

const SessionClock = () => {
  const { session, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [remaining, setRemaining] = useState<number | null>(null);
  const expiredRef = useRef(false);
  const [toastDismissed, setToastDismissed] = useState(false);

  const sessionEndMs = session?.tokens?.session_end_ms;
  const plan = session?.user?.plan as string | undefined;

  // On the checkout page, the OLD plan's clock hitting zero doesn't mean
  // "log this user out" — it's often exactly WHY they're here, buying a
  // new one. Without this, the countdown could reach zero mid-Razorpay
  // checkout (card entry + bank OTP genuinely takes a minute or two) and
  // force-navigate to /login right as /verify was about to succeed,
  // yanking the user off the success screen entirely.
  const onPaymentPage = location.pathname.startsWith(ROUTES.PAYMENT);

  // A fresh purchase hands out a new sessionEndMs — don't carry a dismissal
  // from the PREVIOUS expiry window into the new one.
  useEffect(() => {
    setToastDismissed(false);
  }, [sessionEndMs]);

  useEffect(() => {
    if (!sessionEndMs || onPaymentPage) return;

    const tick = () => {
      const left = Math.max(0, Math.floor((sessionEndMs - Date.now()) / 1000));
      setRemaining(left);

      if (left === 0 && !expiredRef.current) {
        expiredRef.current = true;
        logout();
        navigate('/login?reason=session_expired', { replace: true });
      }
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [sessionEndMs, logout, navigate, onPaymentPage]);

  // Admin, no session_end, or on the payment page itself → no clock
  if (!sessionEndMs || remaining === null || onPaymentPage) return null;

  const urgent  = remaining <= 5 * 60;   // last 5 min → red
  const warning = remaining <= 10 * 60;  // last 10 min → amber

  const color = urgent
    ? '#EF4444'
    : warning
    ? '#F59E0B'
    : '#4FB7C5';

  const planLabel = plan === 'pro' ? 'Pro · 3hr' : 'Basic · 1hr';
  const showWarningToast = remaining > 0 && remaining <= WARNING_THRESHOLD_SEC && !toastDismissed;

  return (
    <>
      <div
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl select-none"
        style={{
          border: `1px solid ${color}30`,
          background: `${color}0D`,
          transition: 'border-color 0.6s, background 0.6s',
        }}
        title={`${planLabel} plan — session expires in ${fmt(remaining)}`}
      >
        <Clock size={12} style={{ color, flexShrink: 0 }} />
        <span
          className="font-mono text-[12px] font-semibold tabular-nums"
          style={{ color, letterSpacing: '0.04em' }}
        >
          {fmt(remaining)}
        </span>
        {urgent && (
          <span
            className="text-[9px] font-bold uppercase tracking-wider hidden sm:inline"
            style={{ color }}
          >
            Expiring
          </span>
        )}
      </div>

      {showWarningToast && (
        <div
          role="alert"
          className="fixed bottom-5 right-5 z-[60] flex items-start gap-3 rounded-xl px-4 py-3 shadow-2xl max-w-xs"
          style={{ background: '#0B0E16', border: '1px solid #EF444440' }}
        >
          <Clock size={16} style={{ color: '#EF4444', flexShrink: 0, marginTop: 2 }} />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-white mb-1">
              Session ends in {fmt(remaining)}
            </p>
            <p className="text-[11px] mb-2.5" style={{ color: '#94A3B8' }}>
              Finish up or save your work — you'll be signed out when the clock hits zero.
            </p>
            <button
              onClick={() => navigate(ROUTES.PAYMENT)}
              className="text-[11px] font-semibold px-3 py-1.5 rounded-lg"
              style={{ background: '#EF4444', color: '#fff' }}
            >
              Renew now
            </button>
          </div>
          <button
            onClick={() => setToastDismissed(true)}
            aria-label="Dismiss"
            className="flex-shrink-0"
            style={{ color: '#64748B' }}
          >
            <X size={14} />
          </button>
        </div>
      )}
    </>
  );
};

export default SessionClock;
