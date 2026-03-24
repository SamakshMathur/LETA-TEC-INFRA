import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const BASE_URL = import.meta.env.PROD ? '/api_proxy' : 'http://localhost:8000';

// ─── Small reusable pieces ────────────────────────────────────────────────────
const Field = ({ label, id, type = 'text', value, onChange, placeholder, required, pattern, title }) => (
  <div>
    <label htmlFor={id} className="block text-sm font-medium text-gray-400 mb-1">{label}</label>
    <input
      id={id} type={type} value={value} required={required} pattern={pattern} title={title}
      onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
      className="w-full px-3 py-3 border border-white/10 bg-black/50 text-white placeholder-gray-600 rounded-lg focus:outline-none focus:border-sentinel-green transition-colors text-sm"
    />
  </div>
);

const MethodButton = ({ active, onClick, icon, label }) => (
  <button type="button" onClick={onClick}
    className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-lg border text-sm font-medium transition-all ${
      active
        ? 'border-sentinel-green bg-sentinel-green/10 text-sentinel-green'
        : 'border-white/10 bg-black/30 text-gray-500 hover:text-gray-300 hover:border-white/20'
    }`}>
    <span>{icon}</span> {label}
  </button>
);

const SubmitButton = ({ loading, label }) => (
  <button type="submit" disabled={loading}
    className={`w-full py-3 px-4 rounded-lg text-sm font-semibold text-white transition-all shadow-lg ${
      loading ? 'bg-gray-700 cursor-not-allowed' : 'bg-sentinel-green hover:bg-[#096646] shadow-sentinel-green/20 hover:shadow-sentinel-green/30'
    }`}>
    {loading ? (
      <span className="flex items-center justify-center gap-2">
        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
        Processing...
      </span>
    ) : label}
  </button>
);

// ─── Main Component ───────────────────────────────────────────────────────────
const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  // mode: 'login' | 'register'
  const [mode, setMode] = useState('login');

  // Register fields
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPhone, setRegPhone] = useState('');
  const [regGender, setRegGender] = useState('male');

  // Shared OTP state
  const [contact, setContact] = useState('');
  const [otpMethod, setOtpMethod] = useState('email');
  const [otp, setOtp] = useState('');
  const [otpPreview, setOtpPreview] = useState('');

  // Steps: register → 1(details) 2(method+send) 3(verify) | login → 1(contact+method) 2(verify)
  const [step, setStep] = useState(1);

  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const reset = () => {
    setStep(1); setError(''); setInfo('');
    setRegUsername(''); setRegEmail(''); setRegPhone(''); setRegGender('male');
    setContact(''); setOtpMethod('email'); setOtp(''); setOtpPreview('');
  };

  const switchMode = (m) => { reset(); setMode(m); };

  // ─── Register Step 1: save details → /register ───────────────────────────
  const handleRegisterDetails = async (e) => {
    e.preventDefault(); setError(''); setIsLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: regUsername, email: regEmail, phone: regPhone, gender: regGender }),
      });
      const data = await res.json();
      if (res.ok) { setContact(regEmail); setOtpMethod('email'); setStep(2); }
      else setError(data.detail || 'Registration failed');
    } catch { setError('Network error. Please try again.'); }
    finally { setIsLoading(false); }
  };

  // ─── Send OTP ─────────────────────────────────────────────────────────────
  const handleSendOtp = async (e) => {
    e.preventDefault(); setError(''); setInfo(''); setIsLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/api/auth/send-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contact, method: otpMethod }),
      });
      const data = await res.json();
      if (res.ok) {
        setOtpPreview(data.otp_preview || '');
        setInfo(`OTP sent${data.otp_preview ? ` — Dev preview: ${data.otp_preview}` : ''}`);
        setStep(mode === 'register' ? 3 : 2);
      } else setError(data.detail || 'Failed to send OTP');
    } catch { setError('Network error. Please try again.'); }
    finally { setIsLoading(false); }
  };

  // ─── Verify OTP ───────────────────────────────────────────────────────────
  const handleVerifyOtp = async (e) => {
    e.preventDefault(); setError(''); setIsLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/api/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ contact, otp }),
      });
      const data = await res.json();
      if (res.ok) { login(data.access_token, data.user_info); navigate('/'); }
      else setError(data.detail || 'Invalid OTP. Try again.');
    } catch { setError('Network error. Please try again.'); }
    finally { setIsLoading(false); }
  };

  const totalSteps = mode === 'register' ? 3 : 2;
  const stepLabels = mode === 'register'
    ? ['Your Details', 'Send OTP', 'Verify']
    : ['Contact', 'Verify OTP'];

  return (
    <div className="min-h-[80vh] flex items-center justify-center bg-sentinel-dark py-12 px-4">
      <div className="max-w-md w-full space-y-6 bg-white/5 p-10 rounded-2xl shadow-xl border border-white/10 backdrop-blur-md">

        {/* Header */}
        <div className="text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-9 h-9 rounded-full bg-sentinel-green/20 border border-sentinel-green/40 flex items-center justify-center shadow-[0_0_20px_rgba(16,185,129,0.15)]">
              <span className="text-sentinel-green text-base font-bold">L</span>
            </div>
            <span className="text-white/50 text-xs tracking-[0.35em] uppercase font-semibold">LETA AI</span>
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">
            {mode === 'login' ? 'Welcome Back' : 'Create Account'}
          </h2>
          <p className="mt-1.5 text-sm text-gray-500">
            {mode === 'login'
              ? 'Sign in with OTP — no password needed'
              : 'Join the premier GST intelligence platform'}
          </p>
        </div>

        {/* Step Progress */}
        <div className="flex gap-2">
          {Array.from({ length: totalSteps }, (_, i) => (
            <div key={i} className="flex-1">
              <div className={`h-1 rounded-full transition-all duration-300 ${i + 1 <= step ? 'bg-sentinel-green' : 'bg-white/10'}`} />
              <p className={`text-[10px] mt-1.5 text-center truncate transition-colors ${i + 1 === step ? 'text-sentinel-green' : 'text-gray-700'}`}>
                {stepLabels[i]}
              </p>
            </div>
          ))}
        </div>

        {/* Alerts */}
        {error && (
          <div className="p-3 rounded-lg text-sm bg-red-500/10 border border-red-500/20 text-red-400">{error}</div>
        )}
        {info && !error && (
          <div className="p-3 rounded-lg text-sm bg-sentinel-green/10 border border-sentinel-green/20 text-sentinel-green">{info}</div>
        )}

        {/* ── REGISTER STEP 1: User Details ─────────────────────────────────── */}
        {mode === 'register' && step === 1 && (
          <form onSubmit={handleRegisterDetails} className="space-y-4">
            <Field label="Username" id="reg-username" value={regUsername} onChange={setRegUsername}
              placeholder="Samaksh Mathur" required />
            <Field label="Email Address" id="reg-email" type="email" value={regEmail} onChange={setRegEmail}
              placeholder="name@company.com" required />
            <Field label="Phone Number" id="reg-phone" type="tel" value={regPhone} onChange={setRegPhone}
              placeholder="+91 9876543210" required />

            {/* Gender Toggle */}
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Gender</label>
              <div className="flex rounded-lg overflow-hidden border border-white/10">
                {[['male', '♂ Male'], ['female', '♀ Female']].map(([val, lbl]) => (
                  <button key={val} type="button" onClick={() => setRegGender(val)}
                    className={`flex-1 py-2.5 text-sm font-medium transition-all ${
                      regGender === val
                        ? 'bg-sentinel-green text-white'
                        : 'bg-black/30 text-gray-500 hover:text-gray-300'
                    }`}>
                    {lbl}
                  </button>
                ))}
              </div>
            </div>

            <SubmitButton loading={isLoading} label="Continue →" />
          </form>
        )}

        {/* ── REGISTER STEP 2 / LOGIN STEP 1: Send OTP ─────────────────────── */}
        {((mode === 'register' && step === 2) || (mode === 'login' && step === 1)) && (
          <form onSubmit={handleSendOtp} className="space-y-4">
            {mode === 'login' ? (
              <Field label="Email or Phone Number" id="login-contact" value={contact} onChange={setContact}
                placeholder="name@company.com or 9876543210" required />
            ) : (
              <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                <p className="text-xs text-gray-500 mb-1">OTP will be sent to</p>
                <p className="text-sm text-white font-medium">{otpMethod === 'email' ? regEmail : regPhone}</p>
              </div>
            )}

            {/* OTP Delivery Method */}
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Receive OTP via</label>
              <div className="flex gap-3">
                <MethodButton active={otpMethod === 'email'} icon="✉" label="Email"
                  onClick={() => { setOtpMethod('email'); if (mode === 'register') setContact(regEmail); }} />
                <MethodButton active={otpMethod === 'phone'} icon="📱" label="SMS"
                  onClick={() => { setOtpMethod('phone'); if (mode === 'register') setContact(regPhone); }} />
              </div>
            </div>

            <SubmitButton loading={isLoading} label="Generate OTP" />
            {mode === 'register' && (
              <button type="button" onClick={() => setStep(1)}
                className="w-full text-xs text-gray-600 hover:text-gray-400 transition-colors py-1">
                ← Back to details
              </button>
            )}
          </form>
        )}

        {/* ── REGISTER STEP 3 / LOGIN STEP 2: Verify OTP ───────────────────── */}
        {((mode === 'register' && step === 3) || (mode === 'login' && step === 2)) && (
          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <div className="p-3 rounded-lg bg-white/5 border border-white/10 text-center">
              <p className="text-xs text-gray-500">OTP sent to</p>
              <p className="text-sm text-white font-medium mt-0.5">{contact}</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2 text-center">
                Enter 4-digit OTP
              </label>
              <input
                type="text" inputMode="numeric" maxLength={4}
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 4))}
                className="w-full text-center text-4xl tracking-[1.2rem] py-5 border border-white/10 bg-black/50 text-white rounded-xl focus:outline-none focus:border-sentinel-green transition-colors font-mono placeholder-gray-700"
                placeholder="····"
                required
              />
              {otpPreview && (
                <p className="text-xs text-yellow-500/70 text-center mt-2">
                  Dev Mode — OTP: <span className="font-bold text-yellow-400 tracking-widest">{otpPreview}</span>
                </p>
              )}
            </div>

            <SubmitButton loading={isLoading} label="Verify & Sign In" />
            <button type="button"
              onClick={() => { setStep(mode === 'register' ? 2 : 1); setInfo(''); setOtp(''); setOtpPreview(''); }}
              className="w-full text-xs text-gray-600 hover:text-gray-400 transition-colors py-1">
              ← Resend OTP
            </button>
          </form>
        )}

        {/* Mode Toggle */}
        <div className="text-center pt-2 border-t border-white/5">
          <button onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
            className="text-sm text-gray-500 hover:text-white transition-colors">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <span className="text-sentinel-green font-medium hover:underline">
              {mode === 'login' ? 'Sign up free' : 'Sign in'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default Login;
