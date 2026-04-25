import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { X, GitBranch, Link2, Activity, Shield } from 'lucide-react';
import { Link } from 'react-router-dom';

const logMessages = [
  'Initializing handshake protocol...',
  'Syncing statutory databases [GST, FEMA, IT]...',
  'Node_Alpha: Latency verified at 12ms.',
  'Re-indexing vector embeddings...',
  'Optimizing query resolution path...',
  'Secure connection established: 256-bit AES.',
  'System Status: OPTIMAL.',
  'Waiting for user input...',
  'Deconstructing latest Notification 12/2024...',
  'Telemetry signal: STRONG.',
];

const SystemFooter = () => {
  const [currentLog, setCurrentLog] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentLog((prev) => (prev + 1) % logMessages.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <footer
      className="pt-16 pb-8 relative overflow-hidden"
      /* No-Line Rule: tonal shift replaces border-t */
      style={{ backgroundColor: 'var(--surface-container-low)' }}
    >
      {/* Top emerald gradient shimmer — single decorative line allowed */}
      <div
        className="absolute top-0 left-0 w-full h-px pointer-events-none"
        style={{
          background: 'linear-gradient(to right, transparent, rgba(78,222,163,0.40), transparent)',
        }}
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-16">

          {/* Brand */}
          <div className="col-span-1">
            <Link to="/" className="flex items-center gap-2 mb-6 group">
              <div
                className="w-8 h-8 rounded flex items-center justify-center transition-all duration-300"
                style={{
                  backgroundColor: 'rgba(78,222,163,0.08)',
                  boxShadow: 'inset 0 0 0 1px rgba(78,222,163,0.20)',
                }}
              >
                <Shield size={15} style={{ color: '#4edea3' }} />
              </div>
              <span className="font-display font-bold text-lg tracking-tight" style={{ color: '#e5e2e1' }}>
                LETA <span style={{ color: '#4edea3' }}>TITAN</span>
              </span>
            </Link>
            <p className="text-sm font-light leading-relaxed mb-6" style={{ color: '#9a9a9a' }}>
              Advanced statutory intelligence for the modern Chartered Accountant.
              Autonomous deconstruction of complex legal frameworks.
            </p>
            <div className="flex gap-4">
              {[X, GitBranch, Link2].map((Icon, i) => (
                <a
                  key={i}
                  href="#"
                  className="transition-colors duration-200"
                  style={{ color: '#9a9a9a' }}
                  onMouseEnter={e => { e.currentTarget.style.color = '#e5e2e1'; }}
                  onMouseLeave={e => { e.currentTarget.style.color = '#9a9a9a'; }}
                >
                  <Icon size={17} />
                </a>
              ))}
            </div>
          </div>

          {/* Platform links */}
          <div>
            <h4
              className="text-xs font-bold uppercase tracking-[0.12em] mb-6 font-mono"
              style={{ color: '#e5e2e1' }}
            >
              Platform
            </h4>
            <ul className="flex flex-col gap-3 text-sm font-mono">
              {[
                { label: 'GST Intelligence', to: '/gst' },
                { label: 'Income Tax',       to: '/income-tax' },
                { label: 'FEMA Expert',      to: '/fema' },
                { label: 'Company Law',      to: '/company-law' },
              ].map(({ label, to }) => (
                <li key={label}>
                  <Link
                    to={to}
                    className="transition-colors duration-200"
                    style={{ color: '#9a9a9a' }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#4edea3'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = '#9a9a9a'; }}
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources links */}
          <div>
            <h4
              className="text-xs font-bold uppercase tracking-[0.12em] mb-6 font-mono"
              style={{ color: '#e5e2e1' }}
            >
              Resources
            </h4>
            <ul className="flex flex-col gap-3 text-sm font-mono">
              {[
                { label: 'Documentation', to: '/docs' },
                { label: 'API Reference',  to: '#' },
                { label: 'System Status',  to: '#' },
                { label: 'About Us',       to: '/about' },
              ].map(({ label, to }) => (
                <li key={label}>
                  <Link
                    to={to}
                    className="transition-colors duration-200"
                    style={{ color: '#9a9a9a' }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#4edea3'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = '#9a9a9a'; }}
                  >
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Live network terminal — Level 2 surface inset */}
          <div
            className="rounded font-mono text-xs overflow-hidden relative min-h-[160px] p-4"
            style={{
              backgroundColor: 'var(--surface-container-lowest)',
              boxShadow: '0 4px 16px rgba(0,0,0,0.40)',
            }}
          >
            <div className="flex items-center gap-2 mb-3 pb-2" style={{ borderBottom: '1px solid rgba(229,226,225,0.06)' }}>
              <Activity size={11} style={{ color: '#4edea3' }} className="animate-pulse" />
              <span className="uppercase tracking-widest text-[10px]" style={{ color: '#9a9a9a' }}>
                Network Activity
              </span>
            </div>

            <div className="flex flex-col gap-2">
              <div style={{ color: 'rgba(78,222,163,0.25)' }}>
                &gt; {logMessages[(currentLog - 2 + logMessages.length) % logMessages.length]}
              </div>
              <div style={{ color: 'rgba(78,222,163,0.50)' }}>
                &gt; {logMessages[(currentLog - 1 + logMessages.length) % logMessages.length]}
              </div>
              <motion.div
                key={currentLog}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                className="font-bold"
                style={{ color: '#4edea3' }}
              >
                &gt; {logMessages[currentLog]}
                <span className="animate-pulse ml-1">_</span>
              </motion.div>
            </div>

            {/* Scanline texture */}
            <div
              className="absolute inset-0 pointer-events-none opacity-10"
              style={{
                backgroundImage:
                  'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(78,222,163,0.03) 2px, rgba(78,222,163,0.03) 4px)',
              }}
            />
          </div>
        </div>

        {/* Bottom bar — tonal shift, no border */}
        <div
          className="pt-8 flex flex-col md:flex-row justify-between items-center gap-4"
          style={{ borderTop: '1px solid rgba(229,226,225,0.06)' }}
        >
          <p className="text-xs font-mono" style={{ color: '#9a9a9a' }}>
            &copy; {new Date().getFullYear()} LETA TITAN — All Rights Reserved.
          </p>
          <div className="flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ backgroundColor: '#4edea3', boxShadow: '0 0 6px rgba(78,222,163,0.6)' }}
            />
            <span className="text-xs font-mono uppercase tracking-widest" style={{ color: '#9a9a9a' }}>
              System Operational
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default SystemFooter;
