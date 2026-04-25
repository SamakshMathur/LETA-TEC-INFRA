import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { registerApi } from '../../../services/auth';
import { ROUTES } from '../../../constants/routes';

const SignupPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await registerApi({ email, username, password });
      setSuccess(true);
      // Wait 2 seconds before redirecting to login
      setTimeout(() => {
        navigate(ROUTES.LOGIN);
      }, 2000);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const errorMessage = typeof detail === 'string' 
        ? detail 
        : Array.isArray(detail) 
          ? detail[0]?.msg || JSON.stringify(detail)
          : detail?.message || 'Registration failed. Please try again.';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface relative overflow-hidden px-6">
      {/* Background effect */}
      <div className="absolute inset-0 bg-noise opacity-20 pointer-events-none" />
      
      <div className="relative z-20 w-full max-w-md">
        <div className="bg-[#0a0a0a]/80 backdrop-blur-3xl p-10 rounded-2xl border border-white/10 shadow-2xl">
          <div className="mb-8 text-center">
            <h1 className="font-display font-bold text-3xl text-white mb-2 uppercase tracking-tight">
              LETA <span className="text-primary">TITAN</span>
            </h1>
            <p className="text-xs font-mono text-white/40 uppercase tracking-widest">
              Account Setup Initialization
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="p-3 rounded bg-red-500/10 border border-red-500/20 text-red-500 text-xs font-medium text-center">
                {error}
              </div>
            )}

            {success && (
              <div className="p-4 rounded-xl bg-sentinel-green/10 border border-sentinel-green/30 text-sentinel-green text-sm font-medium text-center animate-pulse">
                Registration Successful! Redirecting to login portal...
              </div>
            )}
            
            <div className="space-y-2">
              <label htmlFor="email" className="block text-[10px] font-black uppercase tracking-[0.15em] text-white/60 ml-1">
                Command Identity (Email)
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={success}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white placeholder-white/20 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all disabled:opacity-50"
                placeholder="Enter email"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="username" className="block text-[10px] font-black uppercase tracking-[0.15em] text-white/60 ml-1">
                Username (Atlas ID)
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                disabled={success}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white placeholder-white/20 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all disabled:opacity-50"
                placeholder="Choose a username"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="block text-[10px] font-black uppercase tracking-[0.15em] text-white/60 ml-1">
                Clearance Key (Password)
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={success}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-white placeholder-white/20 focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all disabled:opacity-50"
                placeholder="Choose a secure password"
              />
            </div>

            {!success && (
              <button 
                type="submit" 
                disabled={loading}
                className="w-full py-4 bg-primary text-surface font-black uppercase tracking-[0.2em] text-xs rounded-lg hover:bg-primary-hover active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(78,222,163,0.15)] mt-4"
              >
                {loading ? 'Processing...' : 'Complete Setup'}
              </button>
            )}

            {!success && (
              <div className="text-center mt-6">
                <p className="text-[10px] font-bold uppercase tracking-wider text-white/30">
                  Already have an account?{' '}
                  <Link to={ROUTES.LOGIN} className="text-primary hover:text-primary-hover transition-colors">
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
