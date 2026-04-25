import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FileText, Landmark, Globe, Briefcase, ChevronDown, Shield } from 'lucide-react';
import { motion } from 'framer-motion';
import ThemeToggle from '../common/ThemeToggle';

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

const Navbar = () => {
  const location  = useLocation();
  const navigate  = useNavigate();

  const [scrolled,         setScrolled]         = useState(false);
  const [domainsOpen,      setDomainsOpen]      = useState(false);

  const domainsMenuRef = useRef(null);

  const isActive = (path) =>
    location.pathname === path || location.pathname.startsWith(path + '/');

  /* ── scroll listener ── */
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  /* ── close dropdowns on outside click ── */
  useEffect(() => {
    const handler = (e) => {
      if (domainsMenuRef.current && !domainsMenuRef.current.contains(e.target)) setDomainsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const anyDomainActive = DOMAINS.some(d => isActive(d.path));

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
                  boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8), inset 0 0 0 1px rgba(255, 255, 255, 0.08)',
                }}
              >
                {/* dropdown content */}
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
                    <Icon size={14} className={isActive(path) ? "animate-pulse" : ""} />
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
                    boxShadow: '0 0 5px rgba(78,222,163,0.3)' 
                  }}
                />
              )}
            </Link>
          ))}
        </div>

        {/* ── Column 3: Theme Toggle (Right) ────────────────────────── */}
        <div className="flex-1 flex justify-end">
           <ThemeToggle />
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
