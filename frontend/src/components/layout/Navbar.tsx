import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FileText, Landmark, Globe, Briefcase, ChevronDown, Shield, Settings, LogOut } from 'lucide-react';
import { motion } from 'framer-motion';
import ThemeToggle from '../common/ThemeToggle';
import { useAuth } from '../../context/AuthContext';
import { ROUTES } from '../../constants/routes';

const DOMAINS = [
  { label: 'GST Intelligence',  path: '/gst',          icon: FileText,  status: 'ACTIVE' },
  { label: 'Income Tax',        path: '/income-tax',    icon: Landmark,  status: 'ACTIVE' },
  { label: 'FEMA Advisory',     path: '/fema',          icon: Globe,     status: 'ACTIVE' },
  { label: 'Company Law',       path: '/company-law',   icon: Briefcase, status: 'ACTIVE' },
];

const NAV_LINKS = [
  { label: 'About', path: '/about' },
  { label: 'Docs',  path: '/docs'  },
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

  const [scrolled,    setScrolled]    = useState(false);
  const [domainsOpen, setDomainsOpen] = useState(false);
  const [userOpen,    setUserOpen]    = useState(false);

  const domainsMenuRef = useRef<HTMLDivElement>(null);
  const userMenuRef    = useRef<HTMLDivElement>(null);

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + '/');

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (domainsMenuRef.current && !domainsMenuRef.current.contains(e.target as Node))
        setDomainsOpen(false);
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node))
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

  const anyDomainActive = DOMAINS.some(d => isActive(d.path));
  const displayName = user?.full_name || user?.username || 'User';
  const initials    = getInitials(displayName);
  const subLabel    = user?.email || (user?.phone ? `+91 ${user.phone}` : '');

  return (
    <nav
      className="fixed top-0 left-0 w-full z-50 transition-all duration-300"
      style={{
        height: scrolled ? '60px' : '84px',
        backgroundColor: scrolled ? 'rgba(14,14,14,0.90)' : 'transparent',
        backdropFilter: scrolled ? 'blur(20px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(20px)' : 'none',
      }}
    >
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center">

        {/* ── Column 1: Logo (Left) ─────────────────────────────────── */}
        <div className="flex-1 flex justify-start">
          <Link to="/" className="flex items-center gap-3 group flex-shrink-0">
            <div
              className="w-9 h-9 rounded flex items-center justify-center transition-all duration-200"
              style={{
                background: 'linear-gradient(135deg, #4edea3 0%, #10b981 100%)',
                boxShadow: '0 0 10px rgba(78,222,163,0.15)',
              }}
            >
              <Shield className="w-4 h-4" style={{ color: '#0e0e0e' }} />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-lg leading-none tracking-tight" style={{ color: '#e5e2e1' }}>
                LETA <span style={{ color: '#4edea3' }}>TITAN</span>
              </span>
              <span className="text-[9px] font-bold uppercase tracking-[0.2em] mt-0.5" style={{ color: '#9a9a9a' }}>
                SOVEREIGN AI
              </span>
            </div>
          </Link>
        </div>

        {/* ── Column 2: Nav items (Center) ───────────────────────────── */}
        <div className="hidden md:flex items-center gap-10">
          {/* Domains dropdown */}
          <div className="relative" ref={domainsMenuRef}>
            <button
              onClick={() => setDomainsOpen(v => !v)}
              className="flex items-center gap-1.5 px-4 py-2 rounded text-[11px] font-black uppercase tracking-[0.15em] transition-all duration-200 border border-transparent hover:border-white/10 hover:bg-white/5"
              style={{ color: anyDomainActive ? '#4edea3' : '#9a9a9a' }}
            >
              Modules
              <ChevronDown
                size={12}
                className="transition-transform duration-200"
                style={{ transform: domainsOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
              />
            </button>

            {domainsOpen && (
              <div
                className="absolute top-full left-1/2 -translate-x-1/2 mt-4 w-60 rounded-sm py-2 z-50 overflow-hidden"
                style={{
                  backgroundColor: 'rgba(10, 10, 10, 0.95)',
                  backdropFilter: 'blur(32px)',
                  boxShadow: '0 25px 50px -12px rgba(0,0,0,0.8), inset 0 0 0 1px rgba(255,255,255,0.08)',
                }}
              >
                <div className="px-4 py-2 mb-1">
                  <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[#4edea3]/60">Sovereign Modules</span>
                </div>
                {DOMAINS.map(({ label, path, icon: Icon }) => (
                  <Link
                    key={path}
                    to={path}
                    onClick={() => setDomainsOpen(false)}
                    className="flex items-center gap-4 px-5 py-3 text-[11px] font-bold uppercase tracking-wider transition-all duration-200"
                    style={{
                      color: isActive(path) ? '#4edea3' : '#9a9a9a',
                      backgroundColor: isActive(path) ? 'rgba(78,222,163,0.08)' : 'transparent',
                    }}
                    onMouseEnter={e => {
                      if (!isActive(path)) {
                        e.currentTarget.style.color = '#e5e2e1';
                        e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.03)';
                      }
                    }}
                    onMouseLeave={e => {
                      if (!isActive(path)) {
                        e.currentTarget.style.color = '#9a9a9a';
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }
                    }}
                  >
                    <Icon size={14} className={isActive(path) ? 'animate-pulse' : ''} />
                    {label}
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Static nav links */}
          {NAV_LINKS.map(({ label, path }) => (
            <Link
              key={path}
              to={path}
              className="relative px-2 py-1 text-[11px] font-black uppercase tracking-[0.15em] transition-all duration-200 hover:text-white"
              style={{ color: isActive(path) ? '#e5e2e1' : '#9a9a9a' }}
            >
              {label}
              {isActive(path) && (
                <motion.span
                  layoutId="activeNav"
                  className="absolute -bottom-2 left-0 right-0 h-[1.5px] rounded-full"
                  style={{
                    background: 'linear-gradient(90deg, transparent, #4edea3, transparent)',
                    boxShadow: '0 0 5px rgba(78,222,163,0.3)',
                  }}
                />
              )}
            </Link>
          ))}
        </div>

        {/* ── Column 3: Right side ────────────────────────────────────── */}
        <div className="flex-1 flex justify-end items-center gap-4">
          <ThemeToggle />

          {isLoggedIn && (
            <div className="relative" ref={userMenuRef}>
              {/* Avatar button */}
              <button
                onClick={() => setUserOpen(v => !v)}
                className="flex items-center gap-2.5 pl-2 pr-3 py-1.5 rounded-lg border border-white/10 hover:border-white/20 hover:bg-white/5 transition-all duration-200 group"
              >
                {/* Initials circle */}
                <div
                  className="w-7 h-7 rounded-md flex items-center justify-center text-[11px] font-black flex-shrink-0"
                  style={{
                    background: 'linear-gradient(135deg, #4edea3 0%, #10b981 100%)',
                    color: '#0e0e0e',
                  }}
                >
                  {initials}
                </div>
                {/* Name */}
                <span
                  className="text-[11px] font-bold uppercase tracking-[0.1em] max-w-[100px] truncate hidden sm:block"
                  style={{ color: '#e5e2e1' }}
                >
                  {displayName.split(' ')[0]}
                </span>
                <ChevronDown
                  size={11}
                  className="transition-transform duration-200 flex-shrink-0"
                  style={{
                    color: '#9a9a9a',
                    transform: userOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                  }}
                />
              </button>

              {/* Dropdown */}
              {userOpen && (
                <div
                  className="absolute top-full right-0 mt-3 w-56 rounded-xl py-2 z-50 overflow-hidden"
                  style={{
                    backgroundColor: 'rgba(10,10,10,0.97)',
                    backdropFilter: 'blur(32px)',
                    boxShadow: '0 25px 50px -12px rgba(0,0,0,0.8), inset 0 0 0 1px rgba(255,255,255,0.08)',
                  }}
                >
                  {/* User info header */}
                  <div className="px-4 py-3 border-b border-white/5">
                    <p className="text-[12px] font-bold text-white truncate">{displayName}</p>
                    {subLabel && (
                      <p className="text-[10px] text-white/40 truncate mt-0.5">{subLabel}</p>
                    )}
                    {user?.role === 'admin' && (
                      <span className="inline-block mt-1.5 px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider"
                        style={{ background: 'rgba(78,222,163,0.15)', color: '#4edea3' }}>
                        Admin
                      </span>
                    )}
                  </div>

                  {/* Settings */}
                  <button
                    onClick={() => { setUserOpen(false); navigate('/settings'); }}
                    className="w-full flex items-center gap-3 px-4 py-3 text-[11px] font-bold uppercase tracking-wider transition-all duration-200 hover:bg-white/5 text-left"
                    style={{ color: '#9a9a9a' }}
                    onMouseEnter={e => (e.currentTarget.style.color = '#e5e2e1')}
                    onMouseLeave={e => (e.currentTarget.style.color = '#9a9a9a')}
                  >
                    <Settings size={13} />
                    Settings
                  </button>

                  {/* Sign out */}
                  <button
                    onClick={handleSignOut}
                    className="w-full flex items-center gap-3 px-4 py-3 text-[11px] font-bold uppercase tracking-wider transition-all duration-200 hover:bg-red-500/10 text-left"
                    style={{ color: '#9a9a9a' }}
                    onMouseEnter={e => (e.currentTarget.style.color = '#f87171')}
                    onMouseLeave={e => (e.currentTarget.style.color = '#9a9a9a')}
                  >
                    <LogOut size={13} />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
