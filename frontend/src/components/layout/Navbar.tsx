import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FileText, Landmark, Globe, Briefcase, ChevronDown, Shield, Settings, LogOut } from 'lucide-react';
import { motion } from 'framer-motion';
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
      className={`fixed top-0 left-0 w-full z-50 transition-all duration-300 border-b border-transparent ${
        scrolled ? 'bg-leta-white/90 backdrop-blur-md border-leta-gray-100 shadow-sm' : 'bg-transparent'
      }`}
      style={{ height: scrolled ? '64px' : '84px' }}
    >
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center">

        {/* ── Column 1: Logo (Left) ─────────────────────────────────── */}
        <div className="flex-1 flex justify-start">
          <Link to="/" className="flex items-center gap-3 group flex-shrink-0">
            <div className="w-9 h-9 rounded-lg bg-leta-primary flex items-center justify-center shadow-sm">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="font-heading font-bold text-lg leading-none tracking-tight text-leta-gray-900">
                LETA <span className="text-leta-primary">TITAN</span>
              </span>
              <span className="text-[9px] font-bold uppercase tracking-[0.2em] mt-0.5 text-leta-gray-500">
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
              className={`flex items-center gap-1.5 px-4 py-2 rounded-leta text-caption font-semibold transition-colors duration-200 ${
                anyDomainActive ? 'text-leta-primary bg-leta-primary/5' : 'text-leta-gray-700 hover:text-leta-gray-900 hover:bg-leta-gray-50'
              }`}
            >
              Modules
              <ChevronDown
                size={14}
                className={`transition-transform duration-200 ${domainsOpen ? 'rotate-180' : 'rotate-0'}`}
              />
            </button>

            {domainsOpen && (
              <div className="absolute top-full left-1/2 -translate-x-1/2 mt-4 w-60 rounded-leta py-2 z-50 bg-leta-white shadow-elevated border border-leta-gray-100">
                <div className="px-4 py-2 mb-1">
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-leta-gray-500">Sovereign Modules</span>
                </div>
                {DOMAINS.map(({ label, path, icon: Icon }) => (
                  <Link
                    key={path}
                    to={path}
                    onClick={() => setDomainsOpen(false)}
                    className={`flex items-center gap-4 px-5 py-3 text-caption font-medium transition-colors duration-200 ${
                      isActive(path) 
                        ? 'text-leta-primary bg-leta-primary/5' 
                        : 'text-leta-gray-700 hover:bg-leta-gray-50 hover:text-leta-gray-900'
                    }`}
                  >
                    <Icon size={16} className={isActive(path) ? 'animate-pulse' : ''} />
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
              className={`relative px-2 py-1 text-caption font-semibold transition-colors duration-200 ${
                isActive(path) ? 'text-leta-primary' : 'text-leta-gray-700 hover:text-leta-gray-900'
              }`}
            >
              {label}
              {isActive(path) && (
                <motion.span
                  layoutId="activeNav"
                  className="absolute -bottom-2 left-0 right-0 h-[2px] bg-leta-primary rounded-full"
                />
              )}
            </Link>
          ))}
        </div>

        {/* ── Column 3: Right side ────────────────────────────────────── */}
        <div className="flex-1 flex justify-end items-center gap-4">

          {isLoggedIn ? (
            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setUserOpen(v => !v)}
                className="flex items-center gap-2.5 pl-2 pr-3 py-1.5 rounded-leta border border-leta-gray-200 hover:border-leta-gray-300 hover:bg-leta-gray-50 transition-colors duration-200"
              >
                <div className="w-7 h-7 rounded-md bg-leta-primary text-white flex items-center justify-center text-xs font-bold">
                  {initials}
                </div>
                <span className="text-caption font-semibold text-leta-gray-900 hidden sm:block">
                  {displayName.split(' ')[0]}
                </span>
                <ChevronDown size={14} className={`text-leta-gray-500 transition-transform ${userOpen ? 'rotate-180' : ''}`} />
              </button>

              {userOpen && (
                <div className="absolute top-full right-0 mt-3 w-56 bg-leta-white rounded-leta py-2 shadow-elevated border border-leta-gray-100 z-50">
                  <div className="px-4 py-3 border-b border-leta-gray-100">
                    <p className="text-caption font-bold text-leta-gray-900 truncate">{displayName}</p>
                    {subLabel && <p className="text-xs text-leta-gray-500 truncate mt-0.5">{subLabel}</p>}
                    {user?.role === 'admin' && (
                      <span className="inline-block mt-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-leta-primary/10 text-leta-primary">
                        Admin
                      </span>
                    )}
                  </div>
                  <button
                    onClick={() => { setUserOpen(false); navigate('/settings'); }}
                    className="w-full flex items-center gap-3 px-4 py-3 text-caption font-medium text-leta-gray-700 hover:text-leta-gray-900 hover:bg-leta-gray-50 transition-colors text-left"
                  >
                    <Settings size={14} /> Settings
                  </button>
                  <button
                    onClick={handleSignOut}
                    className="w-full flex items-center gap-3 px-4 py-3 text-caption font-medium text-leta-gray-700 hover:text-leta-error hover:bg-leta-error/5 transition-colors text-left"
                  >
                    <LogOut size={14} /> Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link to={ROUTES.LOGIN}>
              <button className="px-4 py-2 bg-leta-primary text-white rounded-leta text-caption font-semibold hover:opacity-90 transition-opacity shadow-sm">
                Sign In
              </button>
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
