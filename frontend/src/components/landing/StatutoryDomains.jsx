import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { FileText, Landmark, Globe, Briefcase, ChevronRight, Activity } from 'lucide-react';

const domains = [
  {
    id: 'gst',
    title: 'GST Intelligence',
    subtext: 'Goods and Services Tax',
    desc: 'Domain-trained statutory intelligence for Indian GST, covering Acts, Rules, Notifications, Circulars, and judicial clarifications.',
    icon: FileText,
    path: '/gst',
    status: 'ACTIVE',
    accentColor: '#4edea3',
  },
  {
    id: 'income-tax',
    title: 'Income Tax',
    subtext: 'Direct Tax Laws',
    desc: 'Structured intelligence for interpretation and compliance under the Income-tax Act, including assessments, deductions, and procedural guidance.',
    icon: Landmark,
    path: '/income-tax',
    status: 'COMING SOON',
    accentColor: '#c084fc',
  },
  {
    id: 'fema',
    title: 'FEMA Advisory',
    subtext: 'Foreign Exchange Management',
    desc: 'Specialized intelligence for cross-border transactions, remittances, and regulatory compliance under FEMA.',
    icon: Globe,
    path: '/fema',
    status: 'COMING SOON',
    accentColor: '#fb923c',
  },
  {
    id: 'company-law',
    title: 'Company Law',
    subtext: 'Companies Act, 2013',
    desc: 'Compliance and interpretive intelligence for corporate governance, filings, and statutory obligations.',
    icon: Briefcase,
    path: '/company-law',
    status: 'COMING SOON',
    accentColor: '#f87171',
  },
];

const StatutoryDomains = () => {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % domains.length);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section
      className="py-32 relative overflow-hidden"
      style={{ backgroundColor: 'var(--surface)' }}
    >
      {/* Subtle grid matrix — very low opacity on Level 0 */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(229,226,225,0.5) 1px, transparent 1px), linear-gradient(to bottom, rgba(229,226,225,0.5) 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      />

      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-12 relative z-10">

        {/* Section header — no divider line, spacing-gap only */}
        <div className="mb-16 pb-8 flex items-end justify-between">
          {/* Background shift replaces border-b */}
          <div>
            <h2
              className="font-display font-bold text-3xl md:text-5xl mb-4 tracking-tight"
              style={{ color: '#e5e2e1' }}
            >
              Statutory Intelligence{' '}
              <span style={{ color: '#2a2a2a' }}>Modules</span>
            </h2>
            <div className="flex items-center gap-2 font-mono text-xs uppercase tracking-widest" style={{ color: '#4edea3' }}>
              <Activity size={12} className="animate-pulse" />
              <span>System Status: Online</span>
            </div>
          </div>
          <p className="hidden md:block text-sm font-mono text-right" style={{ color: '#9a9a9a' }}>
            // SELECT ACTIVE JURISDICTION_
          </p>
        </div>

        {/* Accordion — no visible borders on inactive, tonal shifts only */}
        <div className="flex flex-col lg:flex-row gap-2.5 h-[620px] lg:h-[520px]">
          {domains.map((domain, index) => {
            const isActive = index === activeIndex;

            return (
              <motion.div
                key={domain.id}
                layout
                onClick={() => setActiveIndex(index)}
                className="relative overflow-hidden cursor-pointer rounded transition-all duration-700 ease-out"
                style={{
                  flex: isActive ? 4 : 1,
                  backgroundColor: isActive
                    ? 'var(--surface-container-high)'
                    : 'var(--surface-container-low)',
                  /* Ambient shadow on active, no shadow on inactive */
                  boxShadow: isActive
                    ? '0 20px 60px rgba(0,0,0,0.50)'
                    : 'none',
                }}
                whileHover={!isActive ? { backgroundColor: 'var(--surface-container)' } : {}}
              >
                {/* Active glow overlay */}
                {isActive && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.8 }}
                    className="absolute inset-0 z-0 pointer-events-none"
                  >
                    <div
                      className="absolute top-0 right-0 w-96 h-96"
                      style={{
                        background: `radial-gradient(circle at top right, ${domain.accentColor}18 0%, transparent 65%)`,
                      }}
                    />
                    {/* Bottom accent line — single decorative line allowed here */}
                    <div
                      className="absolute bottom-0 left-0 w-full h-px"
                      style={{
                        background: `linear-gradient(to right, transparent, ${domain.accentColor}50, transparent)`,
                      }}
                    />
                    {/* Binary decoration */}
                    <div
                      className="absolute top-8 right-8 text-[9px] font-mono flex flex-col items-end gap-1"
                      style={{ color: `${domain.accentColor}30` }}
                    >
                      <span>01011001</span>
                      <span>10100110</span>
                      <span>SYSTEM_ACTIVE</span>
                    </div>
                  </motion.div>
                )}

                {/* Content */}
                <div className="relative z-10 h-full p-8 flex flex-col">

                  {/* Inactive vertical label */}
                  {!isActive && (
                    <div className="absolute inset-0 flex items-center justify-center lg:-rotate-90">
                      <h3
                        className="font-mono font-bold uppercase tracking-[0.2em] text-xs whitespace-nowrap opacity-50"
                        style={{ color: '#9a9a9a' }}
                      >
                        {domain.title}
                      </h3>
                    </div>
                  )}

                  {/* Active content */}
                  <AnimatePresence mode="wait">
                    {isActive && (
                      <motion.div
                        initial={{ opacity: 0, x: -16, filter: 'blur(8px)' }}
                        animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
                        exit={{ opacity: 0, x: -8, filter: 'blur(4px)' }}
                        transition={{ duration: 0.45, delay: 0.1 }}
                        className="h-full flex flex-col justify-between"
                      >
                        <div>
                          {/* Icon + status */}
                          <div className="flex items-center justify-between mb-10">
                            <div
                              className="p-4 rounded"
                              style={{ backgroundColor: 'var(--surface-container-lowest)' }}
                            >
                              <domain.icon
                                size={30}
                                strokeWidth={1.2}
                                style={{ color: domain.accentColor }}
                              />
                            </div>
                            <span
                              className={domain.status === 'ACTIVE' ? 'badge-active' : 'badge-pending'}
                            >
                              {domain.status === 'ACTIVE' && (
                                <span
                                  className="w-1.5 h-1.5 rounded-full animate-pulse"
                                  style={{ backgroundColor: '#4edea3' }}
                                />
                              )}
                              {domain.status}
                            </span>
                          </div>

                          {/* Title */}
                          <h3
                            className="font-display font-bold text-4xl lg:text-5xl mb-3 tracking-tight"
                            style={{ color: '#e5e2e1' }}
                          >
                            {domain.title}
                          </h3>

                          {/* Subtext — accent bar instead of border-l */}
                          <div className="flex items-center gap-2 mb-8">
                            <div
                              className="w-3 h-px"
                              style={{ backgroundColor: domain.accentColor }}
                            />
                            <p
                              className="font-mono text-xs uppercase tracking-[0.15em]"
                              style={{ color: `${domain.accentColor}cc` }}
                            >
                              {domain.subtext}
                            </p>
                          </div>

                          <p
                            className="text-lg leading-relaxed font-light max-w-xl"
                            style={{ color: '#9a9a9a' }}
                          >
                            {domain.desc}
                          </p>
                        </div>

                        {/* CTA — all domains are routable */}
                        <div className="mt-8">
                          <Link
                            to={domain.path}
                            className="group inline-flex items-center gap-4 btn-titan px-8 py-3.5"
                          >
                            Initialize Module
                            <ChevronRight
                              size={15}
                              className="group-hover:translate-x-1 transition-transform"
                            />
                          </Link>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default StatutoryDomains;
