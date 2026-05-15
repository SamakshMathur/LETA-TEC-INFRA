import React, { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { Play } from 'lucide-react';

const VideoSection = () => {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({ target: containerRef, offset: ['start end', 'end start'] });
  const scale   = useTransform(scrollYProgress, [0, 0.5], [0.95, 1]);
  const opacity = useTransform(scrollYProgress, [0, 0.3], [0.5, 1]);

  return (
    <section
      ref={containerRef}
      className="py-[140px] relative overflow-hidden border-t border-white/[0.05]"
    >
      {/* Ambient glow behind video */}
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] pointer-events-none bg-[radial-gradient(ellipse,rgba(103,232,249,0.02)_0%,transparent_70%)] blur-[80px]" />



      <div className="w-full px-10 lg:px-20 text-center relative z-10">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-12"
        >
          <span className="inline-block py-1.5 px-3.5 font-mono text-[10px] tracking-[0.2em] mb-4 uppercase rounded-full border border-white/[0.05] bg-white/[0.02] text-[#67E8F9]">
            // EXECUTION_LOG_01
          </span>
          <h2 className="text-3xl md:text-5xl font-bold mb-6 font-display tracking-tight text-[#F5F7FA] uppercase">
            See LETA in Action
          </h2>
          <p className="max-w-2xl mx-auto text-sm leading-relaxed font-mono text-[#A1AAB8]">
            Observing real-time statutory deconstruction and analysis protocols.
          </p>
        </motion.div>

        {/* Video frame */}
        <motion.div
          style={{ scale, opacity }}
          className="relative aspect-video max-w-5xl mx-auto group rounded-2xl overflow-hidden border border-white/[0.06] bg-secondary shadow-2xl"
          initial={{ boxShadow: '0 40px 80px rgba(0,0,0,0.6)' }}
        >
          {/* Actual border overlay */}
          <div className="absolute inset-0 rounded-2xl z-20 pointer-events-none border border-white/[0.06]" />

          {/* Corner indicators */}
          {[
            'top-0 left-0 border-t border-l',
            'top-0 right-0 border-t border-r',
            'bottom-0 left-0 border-b border-l',
            'bottom-0 right-0 border-b border-r',
          ].map((cls, i) => (
            <div key={i} className={`absolute ${cls} w-5 h-5 z-20 pointer-events-none border-white/[0.15]`} />
          ))}

          {/* Background image */}
          <div
            className="absolute inset-0 bg-cover bg-center grayscale"
            style={{
              backgroundImage: `url('https://images.unsplash.com/photo-1551288049-bebda4e38f71?ixlib=rb-1.2.1&auto=format&fit=crop&w=1950&q=80')`,
              opacity: 0.1,
              mixBlendMode: 'luminosity',
            }}
          />
          {/* Dark overlay */}
          <div className="absolute inset-0 bg-[#000000]/90" />

          {/* Play button */}
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <motion.button
              whileTap={{ opacity: 0.8 }}
              className="relative flex items-center justify-center transition-all duration-300 text-[#67E8F9] hover:text-[#5EEAD4]"
              style={{ width: 96, height: 96 }}
            >
              <div className="absolute inset-0 rounded-full animate-[spin_10s_linear_infinite] border border-white/[0.05]" />
              <div className="absolute inset-2 rounded-full animate-[spin_5s_linear_infinite_reverse] border border-[#67E8F9]/10" />
              <div className="absolute inset-0 rounded-full bg-white/[0.01]" />
              <Play size={30} fill="currentColor" className="ml-1 relative z-10" />
            </motion.button>
          </div>

          {/* REC badge */}
          <div className="absolute top-4 left-4 flex items-center gap-2 font-mono text-[10px] tracking-widest px-3 py-1.5 z-20 rounded-lg bg-[#000000]/80 border border-white/[0.06] text-[#67E8F9]">
            <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            <span>REC_001 // LIVE_FEED</span>
          </div>

          {/* Tech label */}
          <div className="absolute bottom-4 right-4 font-mono text-[10px] tracking-widest z-20 text-[#6B7280]/40">
            [ 1080p | 60FPS | ENCRYPTED ]
          </div>
        </motion.div>

      </div>
    </section>
  );
};

export default VideoSection;
