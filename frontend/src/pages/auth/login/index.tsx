import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../../hooks/useAuth';
import { sendOtpApi, verifyOtpApi } from '../../../services/auth';
import { ROUTES } from '../../../constants/routes';

type Method = 'phone' | 'email';
type Step = 'contact' | 'otp';

const LoginPage: React.FC = () => {
  const [method, setMethod] = useState<Method>('phone');
  const [contact, setContact] = useState('');
  const [step, setStep] = useState<Step>('contact');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [countdown, setCountdown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const fromLocation = (location.state as any)?.from;
  const from = fromLocation
    ? `${fromLocation.pathname || '/dashboard'}${fromLocation.search || ''}${fromLocation.hash || ''}`
    : '/dashboard';
  const sessionExpired = new URLSearchParams(location.search).get('reason') === 'session_expired';
  const switchMethod = (m: Method) => { setMethod(m); setContact(''); setError(null); };

  useEffect(() => {
    if (countdown <= 0) return;
    const id = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(id);
  }, [countdown]);

  useEffect(() => {
    if (step === 'otp') inputRefs.current[0]?.focus();
  }, [step]);

  const handleSendOtp = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    setLoading(true); setError(null);
    try {
      const data = await sendOtpApi(contact.trim(), method);
      if (data?.otp_preview) {
        const session = await verifyOtpApi(contact.trim(), data.otp_preview);
        login(session, false);
        navigate(from, { replace: true });
      } else {
        const cd = data?.cooldown_seconds || 60;
        setStep('otp'); setOtp(['', '', '', '', '', '']); setCountdown(cd);
      }
    } catch (err: any) {
      const d = err.response?.data?.detail;
      if (typeof d === 'string') setError(d);
      else if (err.response) setError(`Server error ${err.response.status}: ${JSON.stringify(err.response.data)}`);
      else if (err.request) setError(`Cannot reach server — check connection. (${err.message})`);
      else setError(err.message || 'Failed to send OTP. Please try again.');
      console.error('[Login] Send OTP error:', err.response?.status, err.response?.data, err.message);
    } finally { setLoading(false); }
  };

  const handleResend = async () => {
    if (countdown > 0) return;
    setLoading(true); setError(null);
    try {
      const data = await sendOtpApi(contact.trim(), method);
      const cd = data?.cooldown_seconds || 60;
      setOtp(['', '', '', '', '', '']); setCountdown(cd);
    } catch (err: any) {
      const d = err.response?.data?.detail;
      if (typeof d === 'string') setError(d);
      else setError('Failed to resend OTP. Please try again.');
    } finally { setLoading(false); }
  };


  const handleVerify = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    const otpString = otp.join('');
    if (otpString.length < 6) { setError('Please enter the full 6-digit OTP.'); return; }
    setLoading(true); setError(null);
    try {
      const session = await verifyOtpApi(contact.trim(), otpString);
      login(session, false);
      navigate(from, { replace: true });
    } catch (err: any) {
      const d = err.response?.data?.detail;
      if (typeof d === 'string') setError(d);
      else if (err.response) setError(`Server error ${err.response.status}: ${JSON.stringify(err.response.data)}`);
      else if (err.request) setError(`Cannot reach server — check connection. (${err.message})`);
      else setError(err.message || 'Invalid OTP. Please try again.');
      console.error('[Login] Verify OTP error:', err.response?.status, err.response?.data, err.message);
      setOtp(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
    } finally { setLoading(false); }
  };

  const handleOtpChange = (i: number, val: string) => {
    if (!/^\d*$/.test(val)) return;
    const next = [...otp];
    next[i] = val.slice(-1);
    setOtp(next);
    if (val && i < 5) inputRefs.current[i + 1]?.focus();
  };

  const handleOtpKeyDown = (i: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[i] && i > 0) inputRefs.current[i - 1]?.focus();
  };

  const handleOtpPaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const digits = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    const next = ['', '', '', '', '', ''];
    digits.split('').forEach((d, i) => { next[i] = d; });
    setOtp(next);
    inputRefs.current[Math.min(digits.length, 5)]?.focus();
  };

  return (
    <div className="auth-page py-0">
      <div className="absolute inset-0 bg-noise opacity-20 pointer-events-none" />

      <div className="relative z-20 w-full max-w-md">
        <div className="auth-card">

          <div className="mb-8 text-center">
            <h1 className="font-display font-bold text-3xl text-leta-gray-900 mb-2 uppercase tracking-tight">
              LETA<span className="text-leta-primary">TEC AI</span>
            </h1>
            <p className="text-xs font-mono text-leta-gray-500 uppercase tracking-widest">
              {step === 'contact' ? 'Sovereign Access Portal' : 'Verify Identity'}
            </p>
          </div>

          {sessionExpired && (
            <div className="mb-4 p-3 rounded-leta bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-medium text-center">
              Your session has expired. Please log in again.
            </div>
          )}

          {error && (
            <div className="mb-6 p-3 rounded-leta bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium text-center">
              {error}
            </div>
          )}

          {/* ── Step 1: Phone number entry ── */}
          {step === 'contact' && (
            <form onSubmit={handleSendOtp} className="space-y-6">
              {/* Method toggle */}
              <div className="flex rounded-leta border border-leta-gray-200 overflow-hidden">
                {(['phone', 'email'] as Method[]).map(m => (
                  <button key={m} type="button" onClick={() => switchMethod(m)}
                    className={`flex-1 py-2.5 text-[10px] font-black uppercase tracking-[0.15em] transition-colors ${method === m ? 'bg-leta-primary text-surface' : 'text-leta-gray-500 hover:text-leta-gray-900/70'
                      }`}>
                    {m === 'phone' ? 'Mobile' : 'Email'}
                  </button>
                ))}
              </div>

              <div className="space-y-2">
                <label htmlFor="contact" className="label-auth">
                  {method === 'phone' ? 'Mobile Number' : 'Email Address'}
                </label>
                <input
                  id="contact"
                  type={method === 'phone' ? 'tel' : 'email'}
                  value={contact}
                  onChange={e => setContact(e.target.value)}
                  required
                  className="input-auth"
                  placeholder={method === 'phone' ? '10-digit mobile number' : 'you@example.com'}
                  maxLength={method === 'phone' ? 15 : undefined}
                  autoFocus
                />
              </div>

              <button type="submit" disabled={loading || !contact.trim()} className="btn-auth-primary">
                {loading ? 'Sending OTP...' : 'Send OTP'}
              </button>

              <div className="text-center">
                <p className="text-[10px] font-bold uppercase tracking-wider text-leta-gray-900/30">
                  Don't have an account?{' '}
                  <Link to={ROUTES.SIGNUP} className="text-leta-primary hover:text-leta-primary/80 transition-colors">
                    Set up now
                  </Link>
                </p>
              </div>
            </form>
          )}

          {/* ── Step 2: OTP entry ── */}
          {step === 'otp' && (
            <form onSubmit={handleVerify} className="space-y-6">
              <p className="text-center text-xs text-leta-gray-900/50">
                OTP sent to <span className="text-leta-primary font-bold">+91 ••••••{contact.slice(-4)}</span>
              </p>

              <div className="flex gap-2 justify-center">
                {otp.map((digit, i) => (
                  <input key={i} ref={el => { inputRefs.current[i] = el; }}
                    type="text" inputMode="numeric" maxLength={1} value={digit}
                    onChange={e => handleOtpChange(i, e.target.value)}
                    onKeyDown={e => handleOtpKeyDown(i, e)}
                    onPaste={i === 0 ? handleOtpPaste : undefined}
                    disabled={loading}
                    className="w-11 h-14 text-center text-xl font-bold text-leta-gray-900 bg-leta-gray-50 border border-leta-gray-200 rounded-leta focus:outline-none focus:border-leta-primary/60 focus:ring-1 focus:ring-leta-primary/30 transition-colors disabled:opacity-50 caret-transparent"
                  />
                ))}
              </div>

              <button id="verify-btn" type="submit"
                disabled={loading || otp.join('').length < 6} className="btn-auth-primary">
                {loading ? 'Verifying...' : 'Verify & Login'}
              </button>

              <div className="flex items-center justify-between text-[10px] uppercase tracking-wider font-bold">
                <button type="button"
                  onClick={() => { setStep('contact'); setError(null); setOtp(['', '', '', '', '', '']); }}
                  className="btn-auth-secondary">
                  ← Change number
                </button>
                <button type="button" onClick={handleResend}
                  disabled={countdown > 0 || loading}
                  className="text-leta-primary disabled:text-leta-gray-900/30 transition-colors disabled:cursor-not-allowed text-[10px] font-bold uppercase tracking-wider">
                  {countdown > 0 ? `Resend in ${countdown}s` : 'Resend OTP'}
                </button>
              </div>
            </form>
          )}
        </div>

        <p className="mt-8 text-center text-[10px] font-mono text-leta-gray-900/20 uppercase tracking-[0.1em]">
          &copy; 2026 LETATEC AI / Sovereign Compliance Systems
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
