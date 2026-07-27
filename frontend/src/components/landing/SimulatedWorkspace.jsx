import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import workspaceImg from '../../pages/IMAGES/ElevenLabs_image_nano-banana-2_AI BOT DRAFT..._2026-05-29T12_57_11.png';

const SimulatedWorkspace = () => {
  return (
    <section style={{ padding: '80px 0', background: '#000000', position: 'relative', overflow: 'hidden', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
      <div className="section-container" style={{ position: 'relative', zIndex: 10 }}>

        {/* Section Header */}
        <div className="section-header">
          <p className="section-eyebrow">// Live Product Preview</p>
          <h2 className="section-headline">The Workspace</h2>
          <p className="section-subhead">
            A production-ready statutory intelligence console — query, cite, draft and research, all in one place.
          </p>
        </div>

        {/* Screenshot frame */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="relative premium-card overflow-hidden"
          style={{
            boxShadow: `
              inset 0 1px 0 rgba(255,255,255,0.09),
              inset 0 -1px 0 rgba(0,0,0,0.5),
              0 0 80px rgba(79,183,197,0.12),
              0 0 160px rgba(79,183,197,0.05),
              0 40px 80px rgba(0,0,0,0.9)
            `,
          }}
        >
          {/* Fake chrome bar */}
          <div
            className="flex items-center justify-between px-5 py-3 flex-shrink-0"
            style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(10,15,26,0.95)' }}
          >
            <div className="flex items-center gap-4">
              <div className="flex gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(239,68,68,0.35)' }} />
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(245,158,11,0.35)' }} />
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(34,197,94,0.35)' }} />
              </div>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em]" style={{ color: '#475569' }}>
                LETA TEC Interactive Workspace
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#22C55E' }} />
              <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: '#4FB7C5' }}>
                PORT_CONNECTED
              </span>
            </div>
          </div>

          {/* The real screenshot */}
          <img
            src={workspaceImg}
            alt="LETA Workspace"
            className="w-full block"
            style={{ display: 'block' }}
          />

          {/* Bottom CTA overlay */}
          <div
            className="absolute bottom-0 left-0 right-0 flex items-end justify-center pb-10"
            style={{
              background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.6) 40%, transparent 100%)',
              paddingTop: '80px',
            }}
          >
            <Link to="/dashboard">
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className="flex items-center gap-2.5 px-7 py-3.5 font-semibold text-sm text-black transition-all"
                style={{
                  background: '#4FB7C5',
                  boxShadow: '0 0 40px rgba(79,183,197,0.4), 0 4px 16px rgba(0,0,0,0.4)',
                }}
              >
                Open Workspace <ChevronRight size={15} />
              </motion.button>
            </Link>
          </div>
        </motion.div>

      </div>
    </section>
  );
};

export default SimulatedWorkspace;
