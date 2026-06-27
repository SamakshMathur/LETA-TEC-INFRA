import React from 'react';
import { motion } from 'framer-motion';
import { ShieldAlert, Server, Layers, Key } from 'lucide-react';

const TRUST_METRICS = [
  {
    icon: Layers,
    value: '14M+',
    label: 'Statutory References',
    desc: 'Deep indexing of Central & State GST, Income Tax codes, notifications, circular guidelines, and historic tribunal orders.',
  },
  {
    icon: Server,
    value: '2.3s',
    label: 'Avg Advisory Generation',
    desc: 'High-performance statutory retrieval and reasoning pipeline producing citations and compliance advisory in seconds.',
  },
  {
    icon: ShieldAlert,
    value: '99.2%',
    label: 'Statutory Mapping Accuracy',
    desc: 'Rigorous cross-referencing logic filtering contradictions between historic case laws and active legal exceptions.',
  },
  {
    icon: Key,
    value: '256-Bit',
    label: 'Enterprise Encryption',
    desc: 'Sovereign data encapsulation ensuring secure workspace queries and private corporate document storage.',
  },
];

const SovereignTrust = () => {
  return (
    <section style={{
      padding: '80px 0',
      background: '#000000',
      position: 'relative', overflow: 'hidden',
      borderTop: '1px solid rgba(255,255,255,0.03)',
    }}>

      {/* Subtle background radial */}
      <div aria-hidden style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse 80% 60% at 50% 100%, rgba(79,183,197,0.025) 0%, transparent 65%)',
      }} />

      <div className="section-container" style={{ position: 'relative', zIndex: 10 }}>

        {/* Section header */}
        <motion.div
          className="section-header"
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-40px' }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <p className="section-eyebrow">// Security &amp; Integrity Infrastructure</p>
          <h2 className="section-headline">Sovereign Trust Layer</h2>
          <p className="section-subhead">
            Concrete compliance performance metrics, enterprise-grade encryption,
            and real-time statutory coverage statistics.
          </p>
        </motion.div>

        {/* Metrics — editorial large numbers */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(1, 1fr)',
          gap: 1,
        }}
          className="md:grid-cols-2 lg:grid-cols-4"
        >
          {TRUST_METRICS.map((item, index) => {
            const Icon = item.icon;
            return (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.65, delay: index * 0.07, ease: [0.16, 1, 0.3, 1] }}
                style={{
                  padding: 'clamp(32px, 4vw, 52px)',
                  background: 'linear-gradient(145deg, #0D1521 0%, #07090F 100%)',
                  border: '1px solid rgba(255,255,255,0.05)',
                  display: 'flex', flexDirection: 'column',
                  position: 'relative', overflow: 'hidden',
                  transition: 'border-color 0.3s ease',
                }}
                whileHover={{ borderColor: 'rgba(79,183,197,0.2)' }}
              >
                {/* Icon */}
                <div style={{
                  width: 36, height: 36,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  border: '1px solid rgba(79,183,197,0.15)',
                  background: 'rgba(79,183,197,0.04)',
                  marginBottom: 32,
                }}>
                  <Icon size={16} style={{ color: '#4FB7C5' }} />
                </div>

                {/* Large editorial number */}
                <motion.p
                  className="stat-display-number"
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.8, delay: 0.2 + index * 0.06 }}
                  style={{ marginBottom: 8 }}
                >
                  {item.value}
                </motion.p>

                {/* Label */}
                <p className="stat-display-label" style={{ marginBottom: 20 }}>
                  {item.label}
                </p>

                {/* Description — pushed to bottom */}
                <p style={{
                  fontFamily: "'Inter', sans-serif",
                  fontSize: 12, fontWeight: 300,
                  lineHeight: 1.72, color: 'rgba(107,114,128,0.75)',
                  margin: 0, marginTop: 'auto',
                }}>
                  {item.desc}
                </p>

                {/* Subtle top accent */}
                <div style={{
                  position: 'absolute', top: 0, left: 0, right: 0, height: 1,
                  background: 'linear-gradient(90deg, rgba(79,183,197,0.3) 0%, transparent 50%)',
                }} />
              </motion.div>
            );
          })}
        </div>

      </div>
    </section>
  );
};

export default SovereignTrust;
