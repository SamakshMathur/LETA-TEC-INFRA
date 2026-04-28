import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { registerApi } from '../../../services/auth';
import { ROUTES } from '../../../constants/routes';

const PROFESSIONS = [
  'Advocate / Lawyer',
  'Chartered Accountant (CA)',
  'Company Secretary (CS)',
  'Tax Consultant',
  'Business Owner',
  'Finance Professional',
  'Government Official',
  'Student',
  'Other',
];

const INDIAN_STATES = [
  'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
  'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
  'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
  'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
  'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
  'Andaman & Nicobar Islands', 'Chandigarh', 'Dadra & Nagar Haveli and Daman & Diu',
  'Delhi', 'Jammu & Kashmir', 'Ladakh', 'Lakshadweep', 'Puducherry',
];

const inputClass =
  'w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white placeholder-white/20 focus:outline-none focus:border-sentinel-green/50 focus:ring-1 focus:ring-sentinel-green/20 transition-all disabled:opacity-50';

const labelClass =
  'block text-[10px] font-black uppercase tracking-[0.15em] text-white/60 ml-1 mb-1';

const SignupPage: React.FC = () => {
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    password: '',
    profession: '',
    city: '',
    state: '',
    pincode: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const navigate = useNavigate();

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await registerApi(form);
      setSuccess(true);
      setTimeout(() => navigate(ROUTES.LOGIN), 2000);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
          ? detail[0]?.msg || JSON.stringify(detail)
          : 'Registration failed. Please try again.',
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface relative overflow-hidden px-6 py-12">
      <div className="absolute inset-0 bg-noise opacity-20 pointer-events-none" />

      <div className="relative z-20 w-full max-w-xl">
        <div className="bg-[#0a0a0a]/80 backdrop-blur-3xl p-10 rounded-2xl border border-white/10 shadow-2xl">
          {/* Header */}
          <div className="mb-8 text-center">
            <h1 className="font-display font-bold text-3xl text-white mb-2 uppercase tracking-tight">
              LETA <span className="text-sentinel-green">TITAN</span>
            </h1>
            <p className="text-xs font-mono text-white/40 uppercase tracking-widest">
              Account Setup Initialization
            </p>
          </div>

          {error && (
            <div className="mb-6 p-3 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium text-center">
              {error}
            </div>
          )}
          {success && (
            <div className="mb-6 p-4 rounded-xl bg-sentinel-green/10 border border-sentinel-green/30 text-sentinel-green text-sm font-medium text-center animate-pulse">
              Registration Successful! Redirecting to login portal...
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Full Name */}
            <div>
              <label className={labelClass}>Full Name</label>
              <input
                type="text"
                value={form.full_name}
                onChange={set('full_name')}
                required
                disabled={success}
                className={inputClass}
                placeholder="e.g. Samaksh Mathur"
              />
            </div>

            {/* Email */}
            <div>
              <label className={labelClass}>Email ID</label>
              <input
                type="email"
                value={form.email}
                onChange={set('email')}
                required
                disabled={success}
                className={inputClass}
                placeholder="you@example.com"
              />
            </div>

            {/* Phone */}
            <div>
              <label className={labelClass}>Phone Number</label>
              <input
                type="tel"
                value={form.phone}
                onChange={set('phone')}
                required
                disabled={success}
                className={inputClass}
                placeholder="10-digit mobile number"
                maxLength={15}
              />
            </div>

            {/* Password */}
            <div>
              <label className={labelClass}>Password</label>
              <input
                type="password"
                value={form.password}
                onChange={set('password')}
                required
                disabled={success}
                className={inputClass}
                placeholder="Choose a secure password"
                minLength={6}
              />
            </div>

            {/* Profession */}
            <div>
              <label className={labelClass}>Profession</label>
              <select
                value={form.profession}
                onChange={set('profession')}
                required
                disabled={success}
                className={inputClass}
              >
                <option value="" disabled>Select your profession</option>
                {PROFESSIONS.map(p => (
                  <option key={p} value={p} className="bg-[#0a0a0a] text-white">{p}</option>
                ))}
              </select>
            </div>

            {/* City + State + Pincode */}
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 sm:col-span-1">
                <label className={labelClass}>City</label>
                <input
                  type="text"
                  value={form.city}
                  onChange={set('city')}
                  required
                  disabled={success}
                  className={inputClass}
                  placeholder="e.g. Mumbai"
                />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label className={labelClass}>Pincode</label>
                <input
                  type="text"
                  value={form.pincode}
                  onChange={set('pincode')}
                  required
                  disabled={success}
                  className={inputClass}
                  placeholder="6-digit pincode"
                  maxLength={6}
                  pattern="\d{6}"
                />
              </div>
            </div>

            <div>
              <label className={labelClass}>State</label>
              <select
                value={form.state}
                onChange={set('state')}
                required
                disabled={success}
                className={inputClass}
              >
                <option value="" disabled>Select your state</option>
                {INDIAN_STATES.map(s => (
                  <option key={s} value={s} className="bg-[#0a0a0a] text-white">{s}</option>
                ))}
              </select>
            </div>

            {!success && (
              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-sentinel-green text-[#050A10] font-black uppercase tracking-[0.2em] text-xs rounded-lg hover:bg-sentinel-green/90 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(78,222,163,0.15)] mt-2"
              >
                {loading ? 'Processing...' : 'Complete Setup'}
              </button>
            )}

            {!success && (
              <div className="text-center mt-4">
                <p className="text-[10px] font-bold uppercase tracking-wider text-white/30">
                  Already have an account?{' '}
                  <Link to={ROUTES.LOGIN} className="text-sentinel-green hover:text-white transition-colors">
                    Login here
                  </Link>
                </p>
              </div>
            )}
          </form>
        </div>

        <p className="mt-8 text-center text-[10px] font-mono text-white/20 uppercase tracking-[0.1em]">
          &copy; 2026 LETA / Sovereign Compliance Systems
        </p>
      </div>
    </div>
  );
};

export default SignupPage;
