import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { sendOtpApi, verifyOtpApi } from '../../../services/auth';
import { ROUTES } from '../../../constants/routes';

const inputCls =
  'w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white placeholder-white/20 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all disabled:opacity-50';

const labelCls =
  'block text-[10px] font-black uppercase tracking-[0.15em] text-white/60 ml-1';

type Method = 'phone' | 'email';
type Step = 'contact' | 'otp';

const LoginPage: React.FC = () => {
  const [method, setMethod]   = useState<Method>('phone');
  const [contact, setContact] = useState('');
  const [step, setStep]       = useState<Step>('contact');
  const [otp, setOtp]         = useState(['', '', '', '', '', '']);
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const { login } = useAuth();
  const navigate  = useNavigate();
  const location  = useLocation();
  const from = location.state?.from?.pathname || '/dashboard';

  // Countdown timer for resend
  useEffect(() => {
    if (countdown <= 0) return;
    const id = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(id);
  }, [countdown]);

  // Auto-focus first OTP box when step changes
  useEffect(() => {
    if (step === 'otp') inputRefs.current[0]?.focus();
  }, [step]);

  const handleMethodSwitch = (m: Method) => {
    setMethod(m);
    setContact('');
    setError(null);
  };

  const handleSendOtp = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await sendOtpApi(contact.trim(), method);
      setStep('otp');
      setOtp(['', '', '', '', '', '']);
      setCountdown(30);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to send OTP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (countdown > 0) return;
    setLoading(true);
    setError(null);
    try {
      await sendOtpApi(contact.trim(), method);
      setOtp(['', '', '', '', '', '']);
      setCountdown(30);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to resend OTP.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    const otpString = otp.join('');
    if (otpString.length < 6) {
      setError('Please enter the full 6-digit OTP.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const session = await verifyOtpApi(contact.trim(), otpString);
      login(session, false);
      navigate(from, { replace: true });
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Invalid OTP. Please try again.');
      setOtp(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;
    const next = [...otp];
    next[index] = value.slice(-1);
    setOtp(next);
    if (value && index < 5) inputRefs.current[index + 1]?.focus();
    // Auto-submit when last digit entered
    if (value && index === 5) {
      const full = next.join('');
      if (full.length === 6) {
        // Small delay so state settles before submit
        setTimeout(() => document.getElementById('verify-btn')?.click(), 50);
      }
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleOtpPaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const digits = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    const next = ['', '', '', '', '', ''];
    digits.split('').forEach((d, i) => { next[i] = d; });
    setOtp(next);
    inputRefs.current[Math.min(digits.length, 5)]?.focus();
  };

  const maskedContact = method === 'phone'
    ? `+91 ••••••${contact.slice(-4)}`
    : `${contact.slice(0, 3)}•••${contact.slice(contact.indexOf('@'))}`;

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface relative overflow-hidden px-6">
      <div className="absolute inset-0 bg-noise opacity-20 pointer-events-none" />

      <div className="relative z-20 w-full max-w-md">
        <div className="bg-[#0a0a0a]/80 backdrop-blur-3xl p-10 rounded-2xl border border-white/10 shadow-2xl">

          {/* Header */}
          <div className="mb-8 text-center">
            <h1 className="font-display font-bold text-3xl text-white mb-2 uppercase tracking-tight">
              LETA <span className="text-primary">TITAN</span>
            </h1>
            <p className="text-xs font-mono text-white/40 uppercase tracking-widest">
              {step === 'contact' ? 'Sovereign Access Portal' : 'Verify Identity'}
            </p>
          </div>

          {error && (
            <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium text-center">
              {error}
            </div>
          )}

          {/* ── Step 1: Contact entry ── */}
          {step === 'contact' && (
            <form onSubmit={handleSendOtp} className="space-y-6">

              {/* Method toggle */}
              <div className="flex rounded-lg border border-white/10 overflow-hidden">
                {(['phone', 'email'] as Method[]).map(m => (
                  <button
                    key={m} type="button"
                    onClick={() => handleMethodSwitch(m)}
                    className={`flex-1 py-2.5 text-[10px] font-black uppercase tracking-[0.15em] transition-all ${
                      method === m
                        ? 'bg-primary text-surface'
                        : 'text-white/40 hover:text-white/70'
                    }`}
                  >
                    {m === 'phone' ? 'Mobile' : 'Email'}
                  </button>
                ))}
              </div>

              <div className="space-y-2">
                <label htmlFor="contact" className={labelCls}>
                  {method === 'phone' ? 'Mobile Number' : 'Email Address'}
                </label>
                <input
                  id="contact"
                  type={method === 'phone' ? 'tel' : 'email'}
                  value={contact}
                  onChange={e => setContact(e.target.value)}
                  required
                  className={inputCls}
                  placeholder={method === 'phone' ? '10-digit mobile number' : 'you@example.com'}
                  maxLength={method === 'phone' ? 15 : undefined}
                />
              </div>

              <button
                type="submit" disabled={loading || !contact.trim()}
                className="w-full py-4 bg-primary text-surface font-black uppercase tracking-[0.2em] text-xs rounded-lg hover:bg-primary/90 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(78,222,163,0.15)]"
              >
                {loading ? 'Sending OTP...' : 'Send OTP'}
              </button>

              <div className="text-center">
                <p className="text-[10px] font-bold uppercase tracking-wider text-white/30">
                  Don't have an account?{' '}
                  <Link to={ROUTES.SIGNUP} className="text-primary hover:text-primary/80 transition-colors">
                    Set up now
                  </Link>
                </p>
              </div>
            </form>
          )}

          {/* ── Step 2: OTP entry ── */}
          {step === 'otp' && (
            <form onSubmit={handleVerify} className="space-y-6">

              <p className="text-center text-xs text-white/50">
                OTP sent to{' '}
                <span className="text-primary font-bold">{maskedContact}</span>
              </p>

              {/* 6-box OTP input */}
              <div className="flex gap-2 justify-center">
                {otp.map((digit, i) => (
                  <input
                    key={i}
                    ref={el => { inputRefs.current[i] = el; }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={e => handleOtpChange(i, e.target.value)}
                    onKeyDown={e => handleOtpKeyDown(i, e)}
                    onPaste={i === 0 ? handleOtpPaste : undefined}
                    disabled={loading}
                    className="w-11 h-14 text-center text-xl font-bold text-white bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all disabled:opacity-50 caret-transparent"
                  />
                ))}
              </div>

              <button
                id="verify-btn"
                type="submit"
                disabled={loading || otp.join('').length < 6}
                className="w-full py-4 bg-primary text-surface font-black uppercase tracking-[0.2em] text-xs rounded-lg hover:bg-primary/90 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(78,222,163,0.15)]"
              >
                {loading ? 'Verifying...' : 'Verify & Login'}
              </button>

              <div className="flex items-center justify-between text-[10px] uppercase tracking-wider font-bold">
                <button
                  type="button"
                  onClick={() => { setStep('contact'); setError(null); setOtp(['', '', '', '', '', '']); }}
                  className="text-white/30 hover:text-white/60 transition-colors"
                >
                  ← Change {method === 'phone' ? 'number' : 'email'}
                </button>
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={countdown > 0 || loading}
                  className="text-primary disabled:text-white/30 transition-colors disabled:cursor-not-allowed"
                >
                  {countdown > 0 ? `Resend in ${countdown}s` : 'Resend OTP'}
                </button>
              </div>
            </form>
          )}
        </div>

        <p className="mt-8 text-center text-[10px] font-mono text-white/20 uppercase tracking-[0.1em]">
          &copy; 2026 LETA / Sovereign Compliance Systems
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
