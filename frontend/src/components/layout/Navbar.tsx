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
  { label: 'Home',         path: '/'      },
  { label: 'About Us',     path: '/about' },
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
      className="fixed top-0 left-0 w-full z-50 transition-all duration-500"
      style={{
        height: scrolled ? '68px' : '80px',
        background: scrolled
          ? 'rgba(0,0,0,0.82)'
          : 'rgba(0,0,0,0)',
        backdropFilter: scrolled ? 'blur(24px) saturate(180%)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(24px) saturate(180%)' : 'none',
        borderBottom: scrolled
          ? '1px solid rgba(79,183,197,0.1)'
          : '1px solid rgba(255,255,255,0.0)',
        boxShadow: scrolled ? '0 8px 40px rgba(0,0,0,0.5)' : 'none',
      }}
    >
      <div className="w-full px-10 lg:px-20 h-full flex items-center">

        {/* ── Logo ─────────────────────────────────────────────────────────── */}
        <div className="flex-1 flex justify-start">
          <Link to="/" className="flex items-center gap-3 group flex-shrink-0">
            <img
              src="/LETA_WHITE_ON_BLACK_4K.png"
              alt="LETA"
              className="h-9 w-9 object-contain"
              style={{ mixBlendMode: 'screen' }}
            />
            <div className="flex flex-col leading-none">
              <span
                className="font-display font-bold text-2xl tracking-[0.06em]"
                style={{ color: '#F4F7FA', lineHeight: 1 }}
              >
                LETA
              </span>
              <span
                className="font-mono text-[9px] font-semibold tracking-[0.22em] uppercase"
                style={{ color: '#4FB7C5', marginTop: '2px', opacity: 0.85 }}
              >
                TEC
              </span>
            </div>
          </Link>
        </div>

        {/* ── Center Nav ───────────────────────────────────────────────────── */}
        <div className="hidden md:flex items-center gap-10">
          {/* Modules dropdown */}
          <div className="relative" ref={modulesRef}>
            <button
              onClick={() => setModulesOpen(v => !v)}
              className="flex items-center gap-1.5 text-[14px] font-medium tracking-wider transition-colors duration-200"
              style={{ color: '#A7B3C2' }}
              onMouseEnter={e => e.currentTarget.style.color = '#F4F7FA'}
              onMouseLeave={e => { if (!modulesOpen) e.currentTarget.style.color = '#A7B3C2' }}
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
                  background: '#0F1722',
                  border: '1px solid rgba(255,255,255,0.06)',
                  backdropFilter: 'blur(24px)',
                  boxShadow: '0 20px 40px rgba(0,0,0,0.55)',
                }}
              >
                <div className="px-4 py-2 mb-1">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.12em]" style={{ color: 'rgba(79,183,197,0.8)' }}>
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
                      color: isActive(path) ? '#4FB7C5' : '#A7B3C2',
                      background: isActive(path) ? 'rgba(255,255,255,0.03)' : 'transparent',
                    }}
                    onMouseEnter={e => { if (!isActive(path)) { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; e.currentTarget.style.color = '#F4F7FA'; } }}
                    onMouseLeave={e => { if (!isActive(path)) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#A7B3C2'; } }}
                  >
                    <div className="flex items-center gap-3">
                      <Icon size={15} />
                      {label}
                    </div>
                    {status === 'LIVE' ? (
                      <span className="flex items-center gap-1 text-[9px] font-bold uppercase tracking-wider" style={{ color: '#4FB7C5' }}>
                        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: '#4FB7C5' }} />
                        Live
                      </span>
                    ) : (
                      <span className="text-[9px] font-bold uppercase tracking-wider" style={{ color: '#6C7A99' }}>
                        Soon
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </div>

          {NAV_LINKS.map(({ label, path }) => (
            <Link
              key={label}
              to={path}
              className="relative text-[14px] font-medium tracking-wider transition-colors duration-200"
              style={{ color: isActive(path) ? '#F4F7FA' : '#A7B3C2' }}
              onMouseEnter={e => { if (!isActive(path)) e.currentTarget.style.color = '#F4F7FA'; }}
              onMouseLeave={e => { if (!isActive(path)) e.currentTarget.style.color = '#A7B3C2'; }}
            >
              {label}
              {isActive(path) && (
                <motion.span
                  layoutId="activeNavIndicator"
                  className="absolute -bottom-1.5 left-0 right-0 h-[2px] rounded-full"
                  style={{ background: '#4FB7C5' }}
                />
              )}
            </Link>
          ))}
        </div>

        {/* ── Right Side ───────────────────────────────────────────────────── */}
        <div className="flex-1 flex justify-end items-center gap-3">
          {isLoggedIn ? (
            <div className="relative" ref={userRef}>
              <button
                onClick={() => setUserOpen(v => !v)}
                className="flex items-center gap-2.5 pl-2 pr-3 py-1.5 rounded-xl transition-all duration-200"
                style={{
                  border: '1px solid rgba(255,255,255,0.06)',
                  background: 'rgba(255,255,255,0.03)',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(79,183,197,0.3)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'; }}
              >
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-semibold text-black"
                  style={{ background: '#4FB7C5' }}
                >
                  {initials}
                </div>
                <span className="text-[13px] font-semibold hidden sm:block" style={{ color: '#F4F7FA' }}>
                  {displayName.split(' ')[0]}
                </span>
                <ChevronDown
                  size={13}
                  className={`transition-transform ${userOpen ? 'rotate-180' : ''}`}
                  style={{ color: '#6C7A99' }}
                />
              </button>

              {userOpen && (
                <div
                  className="absolute top-full right-0 mt-3 w-56 rounded-2xl py-2 z-50"
                  style={{
                    background: '#0F1722',
                    border: '1px solid rgba(255,255,255,0.06)',
                    backdropFilter: 'blur(24px)',
                    boxShadow: '0 20px 40px rgba(0,0,0,0.55)',
                  }}
                >
                  <div className="px-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                    <p className="text-[13px] font-bold truncate" style={{ color: '#F4F7FA' }}>{displayName}</p>
                    {subLabel && <p className="text-xs truncate mt-0.5" style={{ color: '#6C7A99' }}>{subLabel}</p>}
                    {user?.role === 'admin' && (
                      <span
                        className="inline-block mt-1.5 px-2 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider"
                        style={{ background: 'rgba(79,183,197,0.15)', color: '#4FB7C5' }}
                      >
                        Admin
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => { setUserOpen(false); navigate('/settings'); }}
                    className="w-full flex items-center gap-3 px-4 py-3 text-[13px] font-medium transition-colors text-left"
                    style={{ color: '#A7B3C2' }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#F4F7FA'; e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = '#A7B3C2'; e.currentTarget.style.background = 'transparent'; }}
                  >
                    <Settings size={14} /> Settings
                  </button>
                  <button
                    onClick={handleSignOut}
                    className="w-full flex items-center gap-3 px-4 py-3 text-[13px] font-medium transition-colors text-left"
                    style={{ color: '#A7B3C2' }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#EF4444'; e.currentTarget.style.background = 'rgba(239,68,68,0.06)'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = '#A7B3C2'; e.currentTarget.style.background = 'transparent'; }}
                  >
                    <LogOut size={14} /> Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link to={ROUTES.LOGIN}>
              <button
                className="px-5 py-2.5 rounded-xl text-[13px] font-semibold text-black transition-all duration-200"
                style={{
                  background: '#4FB7C5',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = '#3EA6B4'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = '#4FB7C5'; e.currentTarget.style.transform = 'translateY(0)'; }}
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
