import { useEffect, useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Clock } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { ROUTES } from '../../constants/routes';

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

  const sessionEndMs = session?.tokens?.session_end_ms;
  const plan = session?.user?.plan as string | undefined;

  // On the checkout page, the OLD plan's clock hitting zero doesn't mean
  // "log this user out" — it's often exactly WHY they're here, buying a
  // new one. Without this, the countdown could reach zero mid-Razorpay
  // checkout (card entry + bank OTP genuinely takes a minute or two) and
  // force-navigate to /login right as /verify was about to succeed,
  // yanking the user off the success screen entirely.
  const onPaymentPage = location.pathname.startsWith(ROUTES.PAYMENT);

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

  return (
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
  );
};

export default SessionClock;
