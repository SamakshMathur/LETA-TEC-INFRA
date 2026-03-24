import { motion, useScroll, useTransform } from 'framer-motion';
import { Link } from 'react-router-dom';

const STATS = [
  { value: '500+', label: 'Litigation Templates' },
  { value: '99.2%', label: 'Citation Accuracy' },
  { value: '4',    label: 'Statutory Domains' },
];

const Hero = () => {
  const { scrollY } = useScroll();
  const y1      = useTransform(scrollY, [0, 500], [0, 180]);
  const opacity = useTransform(scrollY, [0, 280], [1, 0]);

  return (
    <div
      className="relative min-h-screen flex items-center justify-center overflow-hidden pt-24"
      style={{ backgroundColor: 'var(--surface)' }}
    >
      {/* ── Background layers ─────────────────────────────────────── */}
      <motion.div style={{ y: y1, opacity }} className="absolute inset-0 z-0 pointer-events-none">

        {/* Rotating emerald nebula */}
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 160, repeat: Infinity, ease: 'linear' }}
          className="absolute inset-[-50%] w-[200%] h-[200%]"
          style={{
            background: 'radial-gradient(circle at 50% 50%, rgba(78,222,163,0.09) 0%, rgba(20,19,19,0) 55%)',
          }}
        />

        {/* Drifting dot grid */}
        <motion.div
          animate={{ x: ['0%','-2%','0%','2%','0%'], y: ['0%','1.5%','1.5%','0%','0%'] }}
          transition={{ duration: 35, repeat: Infinity, ease: 'linear' }}
          className="absolute inset-[-10%] w-[120%] h-[120%] opacity-20"
          style={{
            backgroundImage: 'radial-gradient(circle, rgba(78,222,163,0.45) 1px, transparent 1px)',
            backgroundSize: '42px 42px',
          }}
        />

        {/* Ambient tonal glows — NO drop shadows */}
        <div
          className="absolute top-1/4 left-1/3 w-[500px] h-[500px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(78,222,163,0.07) 0%, transparent 70%)', filter: 'blur(60px)' }}
        />
        <div
          className="absolute bottom-1/4 right-1/4 w-[400px] h-[400px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(0,238,252,0.05) 0%, transparent 70%)', filter: 'blur(80px)' }}
        />

        {/* Fade to surface */}
        <div
          className="absolute inset-x-0 bottom-0 h-48"
          style={{ background: 'linear-gradient(to top, var(--surface), transparent)' }}
        />
      </motion.div>

      {/* ── Main Content ──────────────────────────────────────────── */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 text-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Status pill */}
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.8 }}
            className="inline-flex items-center gap-3 py-2 px-5 rounded-full mb-14"
            style={{
              backgroundColor: 'rgba(78,222,163,0.08)',
              boxShadow: 'inset 0 0 0 1px rgba(78,222,163,0.20)',
            }}
          >
            <span
              className="w-2 h-2 rounded-full animate-ping"
              style={{ backgroundColor: '#4edea3', boxShadow: '0 0 10px #4edea3' }}
            />
            <span className="text-xs font-bold tracking-[0.25em] uppercase font-mono" style={{ color: '#4edea3' }}>
              Nebula Protocol Active
            </span>
          </motion.div>

          {/* Display headline — Orbitron only for h1/h2 */}
          <h1
            className="font-display font-black leading-[0.92] tracking-tight mb-6"
            style={{ fontSize: 'clamp(3.8rem, 10vw, 9rem)' }}
          >
            <span className="block" style={{ color: '#e5e2e1' }}>
              STATUTORY
            </span>
            <span
              className="block"
              style={{
                WebkitTextFillColor: 'transparent',
                WebkitBackgroundClip: 'text',
                backgroundImage: 'linear-gradient(135deg, #4edea3 0%, #10b981 55%, #4edea3 100%)',
                textShadow: 'none',
                filter: 'drop-shadow(0 0 30px rgba(78,222,163,0.35))',
              }}
            >
              TITAN.
            </span>
          </h1>

          {/* Sub-headline — Inter body */}
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45, duration: 0.9 }}
            className="mt-8 text-lg md:text-xl max-w-2xl mx-auto font-light leading-relaxed"
            style={{ color: '#9a9a9a' }}
          >
            Engineering the future of{' '}
            <span style={{ color: '#e5e2e1', fontWeight: 500 }}>GST Compliance</span>{' '}
            with high-fidelity retrieval and sovereign intelligence.
          </motion.p>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.65, duration: 0.9 }}
            className="mt-14 flex flex-col sm:flex-row gap-5 justify-center items-center"
          >
            <Link to="/gst">
              <button className="btn-titan px-10 py-4">Initialize Titan</button>
            </Link>
            <Link to="/docs">
              <button className="btn-secondary px-10 py-4">Documentation</button>
            </Link>
          </motion.div>

          {/* Trust stats — surface-container-low tiles, no borders */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9, duration: 0.9 }}
            className="mt-20 flex flex-wrap justify-center gap-2.5"
          >
            {STATS.map(({ value, label }) => (
              <div
                key={label}
                className="flex flex-col items-center px-8 py-5 rounded"
                style={{ backgroundColor: 'var(--surface-container-low)', minWidth: '140px' }}
              >
                <span
                  className="font-display font-bold text-2xl"
                  style={{ color: '#4edea3', filter: 'drop-shadow(0 0 8px rgba(78,222,163,0.4))' }}
                >
                  {value}
                </span>
                <span
                  className="text-xs font-bold uppercase tracking-[0.06em] mt-1.5"
                  style={{ color: '#9a9a9a' }}
                >
                  {label}
                </span>
              </div>
            ))}
          </motion.div>
        </motion.div>
      </div>

      {/* Bottom surface fade */}
      <div
        className="absolute inset-x-0 bottom-0 h-32 z-20 pointer-events-none"
        style={{ background: 'linear-gradient(to top, var(--surface), transparent)' }}
      />
    </div>
  );
};

export default Hero;
