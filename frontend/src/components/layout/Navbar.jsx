import { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LogOut, Shield, ChevronDown, FileText, Landmark, Globe, Briefcase } from 'lucide-react';

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
  const { user, isAdmin, logout } = useAuth();

  const [scrolled,         setScrolled]         = useState(false);
  const [dropdownOpen,     setDropdownOpen]     = useState(false);
  const [domainsOpen,      setDomainsOpen]      = useState(false);

  const userMenuRef    = useRef(null);
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
      if (userMenuRef.current    && !userMenuRef.current.contains(e.target))    setDropdownOpen(false);
      if (domainsMenuRef.current && !domainsMenuRef.current.contains(e.target)) setDomainsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = () => { logout(); setDropdownOpen(false); navigate('/'); };

  const getUserInitial = () => {
    if (user?.name)  return user.name.charAt(0).toUpperCase();
    if (user?.email) return user.email.charAt(0).toUpperCase();
    return 'U';
  };

  const anyDomainActive = DOMAINS.some(d => isActive(d.path));

  return (
    <nav
      className="fixed top-0 left-0 w-full z-50 transition-all duration-500"
      style={{
        height: scrolled ? '60px' : '84px',
        backgroundColor: scrolled ? 'rgba(14,14,14,0.90)' : 'transparent',
        backdropFilter: scrolled ? 'blur(20px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(20px)' : 'none',
      }}
    >
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">

        {/* ── Logo ─────────────────────────────────────────────────── */}
        <Link to="/" className="flex items-center gap-3 group flex-shrink-0">
          <div
            className="w-9 h-9 rounded flex items-center justify-center transition-all duration-300 group-hover:rotate-6"
            style={{
              background: 'linear-gradient(135deg, #4edea3 0%, #10b981 100%)',
              boxShadow: '0 0 16px rgba(78,222,163,0.20)',
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

        {/* ── Nav items ────────────────────────────────────────────── */}
        <div className="hidden md:flex items-center gap-1">

          {/* Domains dropdown */}
          <div className="relative" ref={domainsMenuRef}>
            <button
              onClick={() => setDomainsOpen(v => !v)}
              className="flex items-center gap-1.5 px-4 py-2 rounded text-sm font-semibold tracking-wide transition-all duration-200"
              style={{ color: anyDomainActive ? '#e5e2e1' : '#9a9a9a' }}
              onMouseEnter={e => { e.currentTarget.style.color = '#e5e2e1'; }}
              onMouseLeave={e => { if (!anyDomainActive) e.currentTarget.style.color = '#9a9a9a'; }}
            >
              Modules
              <ChevronDown
                size={14}
                className="transition-transform duration-200"
                style={{ transform: domainsOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
              />
            </button>

            {domainsOpen && (
              <div
                className="absolute top-full left-0 mt-2 w-56 rounded py-1.5 z-50"
                style={{
                  backgroundColor: 'rgba(26,26,26,0.97)',
                  backdropFilter: 'blur(20px)',
                  WebkitBackdropFilter: 'blur(20px)',
                  boxShadow: '0 20px 60px rgba(0,0,0,0.60), inset 0 0 0 1px rgba(229,226,225,0.08)',
                }}
              >
                {DOMAINS.map(({ label, path, icon: Icon }) => (
                  <Link
                    key={path}
                    to={path}
                    onClick={() => setDomainsOpen(false)}
                    className="flex items-center gap-3 px-4 py-2.5 text-sm transition-all duration-150"
                    style={{
                      color: isActive(path) ? '#4edea3' : '#9a9a9a',
                      backgroundColor: isActive(path) ? 'rgba(78,222,163,0.06)' : 'transparent',
                    }}
                    onMouseEnter={e => {
                      if (!isActive(path)) {
                        e.currentTarget.style.color = '#e5e2e1';
                        e.currentTarget.style.backgroundColor = 'rgba(229,226,225,0.04)';
                      }
                    }}
                    onMouseLeave={e => {
                      if (!isActive(path)) {
                        e.currentTarget.style.color = '#9a9a9a';
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }
                    }}
                  >
                    <Icon size={14} />
                    {label}
                    {isActive(path) && (
                      <span
                        className="ml-auto w-1.5 h-1.5 rounded-full"
                        style={{ backgroundColor: '#4edea3' }}
                      />
                    )}
                  </Link>
                ))}

                {/* Divider gap — no line */}
                <div className="h-2.5" />

                {/* Admin links inside dropdown if admin */}
                {user && isAdmin && (
                  <>
                    <div className="px-4 pb-1">
                      <span className="text-[10px] font-bold uppercase tracking-[0.12em]" style={{ color: '#333' }}>
                        Admin
                      </span>
                    </div>
                    {[
                      { label: 'Template Manager', path: '/admin/templates' },
                      { label: 'Upload Portal',    path: '/admin/upload'    },
                    ].map(({ label, path }) => (
                      <Link
                        key={path}
                        to={path}
                        onClick={() => setDomainsOpen(false)}
                        className="flex items-center gap-3 px-4 py-2.5 text-sm transition-all duration-150"
                        style={{
                          color: isActive(path) ? '#4edea3' : '#9a9a9a',
                          backgroundColor: isActive(path) ? 'rgba(78,222,163,0.06)' : 'transparent',
                        }}
                        onMouseEnter={e => {
                          if (!isActive(path)) {
                            e.currentTarget.style.color = '#e5e2e1';
                            e.currentTarget.style.backgroundColor = 'rgba(229,226,225,0.04)';
                          }
                        }}
                        onMouseLeave={e => {
                          if (!isActive(path)) {
                            e.currentTarget.style.color = '#9a9a9a';
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }
                        }}
                      >
                        {label}
                      </Link>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Static nav links */}
          {NAV_LINKS.map(({ label, path }) => (
            <Link
              key={path}
              to={path}
              className="relative px-4 py-2 text-sm font-semibold tracking-wide transition-all duration-200"
              style={{ color: isActive(path) ? '#e5e2e1' : '#9a9a9a' }}
              onMouseEnter={e => { e.currentTarget.style.color = '#e5e2e1'; }}
              onMouseLeave={e => { if (!isActive(path)) e.currentTarget.style.color = '#9a9a9a'; }}
            >
              {label}
              {isActive(path) && (
                <span
                  className="absolute bottom-0 left-4 right-4 h-[2px] rounded-full"
                  style={{ backgroundColor: '#4edea3', boxShadow: '0 0 6px rgba(78,222,163,0.6)' }}
                />
              )}
            </Link>
          ))}
        </div>

        {/* ── Auth section ─────────────────────────────────────────── */}
        <div className="flex items-center gap-3">
          {user ? (
            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setDropdownOpen(v => !v)}
                className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-200"
                style={{
                  backgroundColor: 'rgba(229,226,225,0.06)',
                  color: '#e5e2e1',
                  boxShadow: dropdownOpen
                    ? '0 0 0 2px rgba(78,222,163,0.45)'
                    : 'inset 0 0 0 1px rgba(229,226,225,0.12)',
                }}
              >
                {getUserInitial()}
              </button>

              {dropdownOpen && (
                <div
                  className="absolute right-0 mt-3 w-52 rounded py-1.5 z-50"
                  style={{
                    backgroundColor: 'rgba(26,26,26,0.97)',
                    backdropFilter: 'blur(20px)',
                    WebkitBackdropFilter: 'blur(20px)',
                    boxShadow: '0 20px 60px rgba(0,0,0,0.60), inset 0 0 0 1px rgba(229,226,225,0.08)',
                  }}
                >
                  <div className="px-4 py-3" style={{ backgroundColor: 'rgba(229,226,225,0.03)' }}>
                    <p className="text-sm font-semibold truncate" style={{ color: '#e5e2e1' }}>
                      {user.name || 'User'}
                    </p>
                    <p className="text-xs font-mono mt-0.5 truncate" style={{ color: '#9a9a9a' }}>
                      {user.email}
                    </p>
                  </div>
                  <div className="h-2.5" />
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2.5 text-sm font-semibold flex items-center gap-3 transition-all duration-150"
                    style={{ color: '#f87171' }}
                    onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'rgba(248,113,113,0.08)'; }}
                    onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                  >
                    <LogOut size={14} />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <Link to="/login" className="btn-titan px-6 py-2.5 text-xs">
              Sign In
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
