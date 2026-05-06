import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FileText, Landmark, Globe, Briefcase, ChevronDown, Settings, LogOut, LayoutGrid } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';
import { ROUTES } from '../../constants/routes';

const MODULES = [
  { label: 'GST Intelligence',  path: '/gst',          icon: FileText,  status: 'LIVE' },
  { label: 'Income Tax',        path: '/income-tax',    icon: Landmark,  status: 'SOON' },
  { label: 'FEMA Advisory',     path: '/fema',          icon: Globe,     status: 'SOON' },
  { label: 'Company Law',       path: '/company-law',   icon: Briefcase, status: 'SOON' },
];

const NAV_LINKS = [
  { label: 'Intelligence', path: '/gst'   },
  { label: 'Compliance',   path: '/docs'  },
  { label: 'Expert',       path: '/about' },
  { label: 'Resources',    path: '/docs'  },
];

const getInitials = (name: string) => {
  const parts = name.trim().split(' ').filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return parts[0]?.[0]?.toUpperCase() || '?';
};

const Navbar = () => {
  const location  = useLocation();
  const navigate  = useNavigate();
  const { user, isLoggedIn, logout } = useAuth();

  const [scrolled,     setScrolled]     = useState(false);
  const [modulesOpen,  setModulesOpen]  = useState(false);
  const [userOpen,     setUserOpen]     = useState(false);

  const modulesRef = useRef<HTMLDivElement>(null);
  const userRef    = useRef<HTMLDivElement>(null);

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + '/');

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (modulesRef.current && !modulesRef.current.contains(e.target as Node))
        setModulesOpen(false);
      if (userRef.current && !userRef.current.contains(e.target as Node))
        setUserOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSignOut = () => {
    setUserOpen(false);
    logout();
    navigate(ROUTES.LOGIN);
  };

  const displayName = user?.full_name || user?.username || 'User';
  const initials    = getInitials(displayName);
  const subLabel    = user?.email || (user?.phone ? `+91 ${user.phone}` : '');

  return (
    <nav
      className="fixed top-0 left-0 w-full z-50 transition-all duration-300"
      style={{
        height: scrolled ? '60px' : '76px',
        background: scrolled
          ? 'rgba(6,8,22,0.92)'
          : 'transparent',
        backdropFilter: scrolled ? 'blur(24px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(24px)' : 'none',
        borderBottom: scrolled ? '1px solid rgba(124,58,237,0.15)' : '1px solid transparent',
      }}
    >
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center">

        {/* ── Logo ─────────────────────────────────────────────────────────── */}
        <div className="flex-1 flex justify-start">
          <Link to="/" className="flex items-center gap-1 group flex-shrink-0">
            <span className="font-display font-bold text-xl tracking-tight text-white">
              LETA
            </span>
            <span
              className="font-display font-bold text-xl tracking-tight"
              style={{ color: '#7C3AED' }}
            >
              TITAN
            </span>
          </Link>
        </div>

        {/* ── Center Nav ───────────────────────────────────────────────────── */}
        <div className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map(({ label, path }) => (
            <Link
              key={label}
              to={path}
              className="relative text-[13px] font-semibold transition-colors duration-200"
              style={{ color: isActive(path) ? '#A78BFA' : '#94A3B8' }}
              onMouseEnter={e => { if (!isActive(path)) e.currentTarget.style.color = '#CBD5E1'; }}
              onMouseLeave={e => { if (!isActive(path)) e.currentTarget.style.color = '#94A3B8'; }}
            >
              {label}
              {isActive(path) && (
                <motion.span
                  layoutId="activeNavIndicator"
                  className="absolute -bottom-1.5 left-0 right-0 h-[2px] rounded-full"
                  style={{ background: 'linear-gradient(90deg, #7C3AED, #8B5CF6)' }}
                />
              )}
            </Link>
          ))}

          {/* Modules dropdown */}
          <div className="relative" ref={modulesRef}>
            <button
              onClick={() => setModulesOpen(v => !v)}
              className="flex items-center gap-1.5 text-[13px] font-semibold transition-colors duration-200"
              style={{ color: '#94A3B8' }}
            >
              <LayoutGrid size={14} />
              Modules
              <ChevronDown
                size={13}
                className={`transition-transform duration-200 ${modulesOpen ? 'rotate-180' : ''}`}
              />
            </button>

            {modulesOpen && (
              <div
                className="absolute top-full left-1/2 -translate-x-1/2 mt-4 w-64 rounded-2xl py-2 z-50"
                style={{
                  background: 'rgba(11,16,32,0.97)',
                  border: '1px solid rgba(124,58,237,0.2)',
                  backdropFilter: 'blur(24px)',
                  boxShadow: '0 20px 40px rgba(0,0,0,0.7), 0 0 40px rgba(124,58,237,0.1)',
                }}
              >
                <div className="px-4 py-2 mb-1">
                  <span className="text-[9px] font-black uppercase tracking-[0.25em]" style={{ color: 'rgba(124,58,237,0.7)' }}>
                    Sovereign Modules
                  </span>
                </div>
                {MODULES.map(({ label, path, icon: Icon, status }) => (
                  <Link
                    key={path}
                    to={path}
                    onClick={() => setModulesOpen(false)}
                    className="flex items-center justify-between px-4 py-3 text-[13px] font-medium transition-colors duration-200"
                    style={{
                      color: isActive(path) ? '#A78BFA' : '#94A3B8',
                      background: isActive(path) ? 'rgba(124,58,237,0.08)' : 'transparent',
                    }}
                    onMouseEnter={e => { if (!isActive(path)) { e.currentTarget.style.background = 'rgba(124,58,237,0.06)'; e.currentTarget.style.color = '#CBD5E1'; } }}
                    onMouseLeave={e => { if (!isActive(path)) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#94A3B8'; } }}
                  >
                    <div className="flex items-center gap-3">
                      <Icon size={15} />
                      {label}
                    </div>
                    {status === 'LIVE' ? (
                      <span className="flex items-center gap-1 text-[9px] font-black uppercase tracking-wider" style={{ color: '#A78BFA' }}>
                        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: '#A78BFA' }} />
                        Live
                      </span>
                    ) : (
                      <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: '#475569' }}>
                        Soon
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Right Side ───────────────────────────────────────────────────── */}
        <div className="flex-1 flex justify-end items-center gap-3">
          {isLoggedIn ? (
            <div className="relative" ref={userRef}>
              <button
                onClick={() => setUserOpen(v => !v)}
                className="flex items-center gap-2.5 pl-2 pr-3 py-1.5 rounded-xl transition-all duration-200"
                style={{
                  border: '1px solid rgba(124,58,237,0.25)',
                  background: 'rgba(124,58,237,0.06)',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(124,58,237,0.5)'; e.currentTarget.style.boxShadow = '0 0 15px rgba(124,58,237,0.2)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(124,58,237,0.25)'; e.currentTarget.style.boxShadow = 'none'; }}
              >
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black text-white"
                  style={{ background: 'linear-gradient(135deg, #7C3AED, #5B21B6)' }}
                >
                  {initials}
                </div>
                <span className="text-[13px] font-semibold hidden sm:block" style={{ color: '#CBD5E1' }}>
                  {displayName.split(' ')[0]}
                </span>
                <ChevronDown
                  size={13}
                  className={`transition-transform ${userOpen ? 'rotate-180' : ''}`}
                  style={{ color: '#475569' }}
                />
              </button>

              {userOpen && (
                <div
                  className="absolute top-full right-0 mt-3 w-56 rounded-2xl py-2 z-50"
                  style={{
                    background: 'rgba(11,16,32,0.97)',
                    border: '1px solid rgba(124,58,237,0.2)',
                    backdropFilter: 'blur(24px)',
                    boxShadow: '0 20px 40px rgba(0,0,0,0.7)',
                  }}
                >
                  <div className="px-4 py-3" style={{ borderBottom: '1px solid rgba(124,58,237,0.1)' }}>
                    <p className="text-[13px] font-bold truncate" style={{ color: '#E2E8F0' }}>{displayName}</p>
                    {subLabel && <p className="text-xs truncate mt-0.5" style={{ color: '#475569' }}>{subLabel}</p>}
                    {user?.role === 'admin' && (
                      <span
                        className="inline-block mt-1.5 px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-wider"
                        style={{ background: 'rgba(124,58,237,0.15)', color: '#A78BFA' }}
                      >
                        Admin
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => { setUserOpen(false); navigate('/settings'); }}
                    className="w-full flex items-center gap-3 px-4 py-3 text-[13px] font-medium transition-colors text-left"
                    style={{ color: '#94A3B8' }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#CBD5E1'; e.currentTarget.style.background = 'rgba(124,58,237,0.06)'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = '#94A3B8'; e.currentTarget.style.background = 'transparent'; }}
                  >
                    <Settings size={14} /> Settings
                  </button>
                  <button
                    onClick={handleSignOut}
                    className="w-full flex items-center gap-3 px-4 py-3 text-[13px] font-medium transition-colors text-left"
                    style={{ color: '#94A3B8' }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#EF4444'; e.currentTarget.style.background = 'rgba(239,68,68,0.06)'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = '#94A3B8'; e.currentTarget.style.background = 'transparent'; }}
                  >
                    <LogOut size={14} /> Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link to={ROUTES.LOGIN}>
              <button
                className="px-5 py-2 rounded-xl text-[13px] font-bold text-white transition-all duration-200"
                style={{
                  background: 'linear-gradient(135deg, #7C3AED, #5B21B6)',
                  boxShadow: '0 0 20px rgba(124,58,237,0.4)',
                }}
                onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 0 35px rgba(124,58,237,0.65)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
                onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 0 20px rgba(124,58,237,0.4)'; e.currentTarget.style.transform = 'translateY(0)'; }}
              >
                Connect Portal
              </button>
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
