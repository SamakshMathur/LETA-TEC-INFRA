import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, User, Mail, Phone, Clock, Save, Loader2, CheckCircle2, FileText, ChevronRight } from 'lucide-react';
import { AXIOS_INSTANCE as axios } from '../utils/api';
import { BASE_URL } from '../config/api';
import { useAuth } from '../hooks/useAuth';
import { getAuthHeaders } from '../utils/authHeaders';
import { ROUTES } from '../constants/routes';

const B = {
  accent: '#4FB7C5',
  glow:   'rgba(79,183,197,0.12)',
  border: 'rgba(79,183,197,0.14)',
};

// The only nav entry pointing at a settings page 404'd — there was no way
// for any user to view or edit their own account details at all. Built
// specifically to close that, plus the concrete gap it caused: a
// phone-only signup had no way to ever add an email, which is why
// payment receipt emails render blank for most users.
const Settings: React.FC = () => {
  const navigate = useNavigate();
  const { user, session, login } = useAuth();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail]       = useState(user?.email || '');
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [saved, setSaved]       = useState(false);

  const nameChanged  = fullName.trim() !== (user?.full_name || '');
  const emailChanged = email.trim() !== (user?.email || '');
  const dirty = nameChanged || emailChanged;

  const activeUntilMs = session?.tokens?.session_end_ms;
  const hasActivePlan = !!activeUntilMs && activeUntilMs > Date.now();

  const handleSave = async () => {
    if (!dirty || saving) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const body: { full_name?: string; email?: string } = {};
      if (nameChanged) body.full_name = fullName.trim();
      if (emailChanged) body.email = email.trim();

      const res = await axios.patch(`${BASE_URL}/api/auth/me`, body, { headers: getAuthHeaders() });
      const updated = res.data;

      if (session) {
        login({
          ...session,
          user: { ...session.user, full_name: updated.full_name, email: updated.email },
        }, true);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not save changes. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="min-h-screen pt-24 pb-16 px-4 sm:px-8"
      style={{ background: 'linear-gradient(160deg, #05070E 0%, #060910 60%, #040611 100%)' }}
    >
      <div className="max-w-2xl mx-auto">
        <motion.button
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 text-xs mb-8 transition-colors"
          style={{ color: '#475569' }}
          onMouseEnter={e => (e.currentTarget.style.color = B.accent)}
          onMouseLeave={e => (e.currentTarget.style.color = '#475569')}
        >
          <ArrowLeft size={13} /> Back to dashboard
        </motion.button>

        <h1 className="text-2xl font-bold text-white mb-1" style={{ letterSpacing: '-0.02em' }}>
          Account Settings
        </h1>
        <p className="text-sm mb-8" style={{ color: '#475569' }}>
          Manage your profile details
        </p>

        {/* Profile card */}
        <div className="rounded-2xl overflow-hidden mb-6" style={{ background: '#080A10', border: `1px solid ${B.border}` }}>
          <div className="px-6 py-5" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <h2 className="text-sm font-bold text-white">Profile</h2>
          </div>

          <div className="px-6 py-5 space-y-5">
            <div>
              <label className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest mb-2" style={{ color: '#334155' }}>
                <User size={11} /> Full Name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                className="w-full px-4 py-3 rounded-xl text-sm bg-black/30 outline-none transition-colors"
                style={{ border: `1px solid ${B.border}`, color: '#F4F7FA' }}
                onFocus={e => (e.currentTarget.style.borderColor = B.accent)}
                onBlur={e => (e.currentTarget.style.borderColor = B.border)}
              />
            </div>

            <div>
              <label className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest mb-2" style={{ color: '#334155' }}>
                <Mail size={11} /> Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-4 py-3 rounded-xl text-sm bg-black/30 outline-none transition-colors"
                style={{ border: `1px solid ${B.border}`, color: '#F4F7FA' }}
                onFocus={e => (e.currentTarget.style.borderColor = B.accent)}
                onBlur={e => (e.currentTarget.style.borderColor = B.border)}
              />
              {!user?.email && (
                <p className="text-[11px] mt-2" style={{ color: '#475569' }}>
                  Add an email to receive payment receipts — your account doesn't have one on file yet.
                </p>
              )}
            </div>

            <div>
              <label className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest mb-2" style={{ color: '#334155' }}>
                <Phone size={11} /> Mobile Number
              </label>
              <div className="w-full px-4 py-3 rounded-xl text-sm" style={{ border: `1px solid ${B.border}`, color: '#64748B', background: 'rgba(255,255,255,0.01)' }}>
                {user?.phone ? `+91 ${user.phone}` : '—'}
              </div>
              <p className="text-[11px] mt-2" style={{ color: '#475569' }}>
                Contact support to change the mobile number linked to your account.
              </p>
            </div>
          </div>

          <div className="px-6 py-5" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
            {error && (
              <p className="text-xs mb-3" style={{ color: '#F87171' }}>{error}</p>
            )}
            <button
              onClick={handleSave}
              disabled={!dirty || saving}
              className="px-5 py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed"
              style={{ background: B.accent, color: '#000' }}
            >
              {saving ? (
                <><Loader2 size={14} className="animate-spin" /> Saving…</>
              ) : saved ? (
                <><CheckCircle2 size={14} /> Saved</>
              ) : (
                <><Save size={14} /> Save Changes</>
              )}
            </button>
          </div>
        </div>

        {/* Plan card */}
        <div className="rounded-2xl overflow-hidden" style={{ background: '#080A10', border: `1px solid ${B.border}` }}>
          <div className="px-6 py-5" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <h2 className="text-sm font-bold text-white">Plan</h2>
          </div>
          <div className="px-6 py-5 flex items-center gap-3">
            <Clock size={14} style={{ color: hasActivePlan ? B.accent : '#475569' }} />
            {hasActivePlan ? (
              <span className="text-sm" style={{ color: '#F4F7FA' }}>
                Active until {new Date(activeUntilMs!).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
              </span>
            ) : (
              <span className="text-sm" style={{ color: '#64748B' }}>No active plan right now</span>
            )}
          </div>
          <button
            onClick={() => navigate(ROUTES.INVOICES)}
            className="w-full px-6 py-4 flex items-center justify-between gap-3 text-left transition-colors"
            style={{ borderTop: '1px solid rgba(255,255,255,0.05)', color: '#F4F7FA' }}
          >
            <span className="flex items-center gap-2 text-sm">
              <FileText size={14} style={{ color: '#475569' }} /> Invoice History
            </span>
            <ChevronRight size={14} style={{ color: '#475569' }} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;
