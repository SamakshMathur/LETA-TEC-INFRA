import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { registerApi } from '../../../services/auth';
import { ROUTES } from '../../../constants/routes';
import { ChevronDown } from 'lucide-react';

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

const GENDERS = ['Male', 'Female', 'Other', 'Prefer not to say'];

const inputCls =
  'w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white placeholder-white/20 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all disabled:opacity-50';

const labelCls =
  'block text-[10px] font-black uppercase tracking-[0.15em] text-white/60 ml-1';

const SelectField = ({
  id, value, onChange, disabled, placeholder, children,
}: {
  id: string; value: string;
  onChange: React.ChangeEventHandler<HTMLSelectElement>;
  disabled?: boolean; placeholder: string; children: React.ReactNode;
}) => (
  <div className="relative">
    <select
      id={id} value={value} onChange={onChange}
      required disabled={disabled}
      className={`${inputCls} appearance-none cursor-pointer pr-10`}
    >
      <option value="" disabled className="bg-[#0a0a0a] text-white/40">{placeholder}</option>
      {children}
    </select>
    <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none" />
  </div>
);

interface FormState {
  full_name: string;
  phone: string;
  profession: string;
  gender: string;
}

const SignupPage: React.FC = () => {
  const [form, setForm] = useState<FormState>({ full_name: '', phone: '', profession: '', gender: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const navigate = useNavigate();

  const set = (field: keyof FormState) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
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
        typeof detail === 'string' ? detail
          : Array.isArray(detail) ? (detail[0]?.msg ?? JSON.stringify(detail))
          : 'Registration failed. Please try again.',
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface relative overflow-hidden px-6 py-12">
      <div className="absolute inset-0 bg-noise opacity-20 pointer-events-none" />

      <div className="relative z-20 w-full max-w-md">
        <div className="bg-[#0a0a0a]/80 backdrop-blur-3xl p-10 rounded-2xl border border-white/10 shadow-2xl">

          <div className="mb-8 text-center">
            <h1 className="font-display font-bold text-3xl text-white mb-2 uppercase tracking-tight">
              LETA <span className="text-primary">TITAN</span>
            </h1>
            <p className="text-xs font-mono text-white/40 uppercase tracking-widest">
              Account Setup
            </p>
          </div>

          {error && (
            <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium text-center">
              {error}
            </div>
          )}
          {success && (
            <div className="mb-6 p-4 rounded-xl bg-primary/10 border border-primary/30 text-primary text-sm font-medium text-center animate-pulse">
              Account created! Redirecting to login...
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">

            <div className="space-y-2">
              <label htmlFor="full_name" className={labelCls}>Full Name</label>
              <input
                id="full_name" type="text" value={form.full_name}
                onChange={set('full_name')} required disabled={success}
                className={inputCls} placeholder="e.g. Samaksh Mathur"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="phone" className={labelCls}>Mobile Number</label>
              <input
                id="phone" type="tel" value={form.phone}
                onChange={set('phone')} required disabled={success}
                className={inputCls} placeholder="10-digit mobile number"
                maxLength={15}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="profession" className={labelCls}>Profession</label>
              <SelectField
                id="profession" value={form.profession}
                onChange={set('profession')} disabled={success}
                placeholder="Select your profession"
              >
                {PROFESSIONS.map(p => (
                  <option key={p} value={p} className="bg-[#0a0a0a] text-white">{p}</option>
                ))}
              </SelectField>
            </div>

            <div className="space-y-2">
              <label htmlFor="gender" className={labelCls}>Gender</label>
              <SelectField
                id="gender" value={form.gender}
                onChange={set('gender')} disabled={success}
                placeholder="Select gender"
              >
                {GENDERS.map(g => (
                  <option key={g} value={g} className="bg-[#0a0a0a] text-white">{g}</option>
                ))}
              </SelectField>
            </div>

            {!success && (
              <button
                type="submit" disabled={loading}
                className="w-full py-4 bg-primary text-surface font-black uppercase tracking-[0.2em] text-xs rounded-lg hover:bg-primary/90 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(78,222,163,0.15)] mt-2"
              >
                {loading ? 'Setting up...' : 'Setup Account'}
              </button>
            )}

            {!success && (
              <div className="text-center pt-1">
                <p className="text-[10px] font-bold uppercase tracking-wider text-white/30">
                  Already have an account?{' '}
                  <Link to={ROUTES.LOGIN} className="text-primary hover:text-primary/80 transition-colors">
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
