import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { registerApi } from '../../../services/auth';
import { ROUTES } from '../../../constants/routes';
import { ChevronDown } from 'lucide-react';

const PROFESSIONS = [
  'Advocate / Lawyer', 'Chartered Accountant (CA)', 'Company Secretary (CS)',
  'Tax Consultant', 'Business Owner', 'Finance Professional',
  'Government Official', 'Student', 'Other',
];

const GENDERS = ['Male', 'Female', 'Other', 'Prefer not to say'];

const SelectField = ({
  id, value, onChange, disabled, placeholder, children,
}: {
  id: string; value: string;
  onChange: React.ChangeEventHandler<HTMLSelectElement>;
  disabled?: boolean; placeholder: string; children: React.ReactNode;
}) => (
  <div className="relative">
    <select id={id} value={value} onChange={onChange} required disabled={disabled}
      className="select-auth">
      <option value="" disabled className="bg-[#0a0a0a] text-leta-gray-500">{placeholder}</option>
      {children}
    </select>
    <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-leta-gray-900/30 pointer-events-none" />
  </div>
);

interface FormState { full_name: string; phone: string; profession: string; gender: string; }

const SignupPage: React.FC = () => {
  const [form, setForm] = useState<FormState>({ full_name: '', phone: '', profession: '', gender: '' });
  const [loading, setLoading]  = useState(false);
  const [error, setError]      = useState<string | null>(null);
  const [success, setSuccess]  = useState(false);
  const navigate = useNavigate();

  const set = (field: keyof FormState) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm(prev => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e: React.SyntheticEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await registerApi(form);
      setSuccess(true);
      setTimeout(() => navigate(ROUTES.LOGIN), 2000);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail[0]?.msg ?? JSON.stringify(detail));
      } else if (err.response) {
        setError(`Server error ${err.response.status}: ${JSON.stringify(err.response.data)}`);
      } else if (err.request) {
        setError(`Cannot reach server — check your connection. (${err.message})`);
      } else {
        setError(err.message || 'Registration failed. Please try again.');
      }
      console.error('[Signup] Registration error:', err.response?.status, err.response?.data, err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="absolute inset-0 bg-noise opacity-20 pointer-events-none" />

      <div className="relative z-20 w-full max-w-md">
        <div className="auth-card">

          <div className="mb-8 text-center">
            <h1 className="font-display font-bold text-3xl text-leta-gray-900 mb-2 uppercase tracking-tight">
              LETA <span className="text-leta-primary">TEC</span>
            </h1>
            <p className="text-xs font-mono text-leta-gray-500 uppercase tracking-widest">Account Setup</p>
          </div>

          {error && (
            <div className="mb-6 p-3 rounded-leta bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium text-center">
              {error}
            </div>
          )}
          {success && (
            <div className="mb-6 p-4 rounded-leta bg-leta-primary/10 border border-leta-primary/30 text-leta-primary text-sm font-medium text-center animate-pulse">
              Account created! Redirecting to login...
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label htmlFor="full_name" className="label-auth">Full Name</label>
              <input id="full_name" type="text" value={form.full_name} onChange={set('full_name')}
                required disabled={success} className="input-auth" placeholder="Your name" />
            </div>

            <div className="space-y-2">
              <label htmlFor="phone" className="label-auth">Mobile Number</label>
              <input id="phone" type="tel" value={form.phone} onChange={set('phone')}
                required disabled={success} className="input-auth"
                placeholder="10-digit mobile number" maxLength={15} />
            </div>

            <div className="space-y-2">
              <label htmlFor="profession" className="label-auth">Profession</label>
              <SelectField id="profession" value={form.profession} onChange={set('profession')}
                disabled={success} placeholder="Select your profession">
                {PROFESSIONS.map(p => (
                  <option key={p} value={p} className="bg-[#0a0a0a] text-leta-gray-900">{p}</option>
                ))}
              </SelectField>
            </div>

            <div className="space-y-2">
              <label htmlFor="gender" className="label-auth">Gender</label>
              <SelectField id="gender" value={form.gender} onChange={set('gender')}
                disabled={success} placeholder="Select gender">
                {GENDERS.map(g => (
                  <option key={g} value={g} className="bg-[#0a0a0a] text-leta-gray-900">{g}</option>
                ))}
              </SelectField>
            </div>

            {!success && (
              <button type="submit" disabled={loading} className="btn-auth-primary mt-2">
                {loading ? 'Setting up...' : 'Setup Account'}
              </button>
            )}

            {!success && (
              <div className="text-center pt-1">
                <p className="text-[10px] font-bold uppercase tracking-wider text-leta-gray-900/30">
                  Already have an account?{' '}
                  <Link to={ROUTES.LOGIN} className="text-leta-primary hover:text-leta-primary/80 transition-colors">
                    Login here
                  </Link>
                </p>
              </div>
            )}
          </form>
        </div>

        <p className="mt-8 text-center text-[10px] font-mono text-leta-gray-900/20 uppercase tracking-[0.1em]">
          &copy; 2026 LETA / Sovereign Compliance Systems
        </p>
      </div>
    </div>
  );
};

export default SignupPage;
