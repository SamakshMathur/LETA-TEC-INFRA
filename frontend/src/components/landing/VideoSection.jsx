import React, { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { Play } from 'lucide-react';

const VideoSection = () => {
  const containerRef = useRef(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end start"]
  });

  const scale = useTransform(scrollYProgress, [0, 0.5], [0.9, 1]);
  const opacity = useTransform(scrollYProgress, [0, 0.3], [0.5, 1]);

  return (
    <section ref={containerRef} className="py-24 bg-[#020202] relative overflow-hidden text-white border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-12"
        >
            <span className="inline-block py-1 px-3 border border-sentinel-green/30 text-sentinel-green bg-sentinel-green/5 font-mono text-[10px] tracking-[0.2em] mb-4 uppercase">
                // EXECUTION_LOG_01
            </span>
            <h2 className="text-3xl md:text-5xl font-bold mb-6 font-sans tracking-tight">
              See <span className="text-gray-500">LETA</span> in Action
            </h2>
            <p className="text-gray-400 max-w-2xl mx-auto text-lg font-mono text-sm leading-relaxed border-l border-sentinel-blue/30 pl-4 text-left md:text-center md:border-l-0 md:pl-0">
                Observing real-time statutory deconstruction and analysis protocols.
            </p>
        </motion.div>

        <motion.div 
          style={{ scale, opacity }}
          className="relative aspect-video max-w-5xl mx-auto bg-[#050A10] border border-white/10 group shadow-[0_0_50px_rgba(0,0,0,0.8)]"
        >
            {/* Corner Indicators */}
            <div className="absolute top-0 left-0 w-4 h-4 border-t border-l border-sentinel-green/50 z-20" />
            <div className="absolute top-0 right-0 w-4 h-4 border-t border-r border-sentinel-green/50 z-20" />
            <div className="absolute bottom-0 left-0 w-4 h-4 border-b border-l border-sentinel-green/50 z-20" />
            <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r border-sentinel-green/50 z-20" />

            {/* Placeholder for actual video source */}
            <div className="absolute inset-0 flex items-center justify-center bg-transparent">
                <div className="absolute inset-0 opacity-20 bg-[url('https://images.unsplash.com/photo-1551288049-bebda4e38f71?ixlib=rb-1.2.1&auto=format&fit=crop&w=1950&q=80')] bg-cover bg-center grayscale mix-blend-luminosity" />
                <div className="absolute inset-0 bg-[#050A10]/60" />
                
                <motion.button 
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    className="relative z-10 w-24 h-24 flex items-center justify-center text-sentinel-green group-hover:text-white transition-colors duration-300"
                >
                    <div className="absolute inset-0 border border-sentinel-green/30 rounded-full animate-[spin_10s_linear_infinite]" />
                    <div className="absolute inset-2 border border-sentinel-green/10 rounded-full animate-[spin_5s_linear_infinite_reverse]" />
                    <Play size={32} fill="currentColor" className="ml-1" />
                </motion.button>
            </div>
            
            {/* Overlay UI elements to make it look technical */}
            <div className="absolute top-4 left-4 flex items-center gap-3 font-mono text-[10px] text-sentinel-green tracking-widest bg-black/50 px-2 py-1 border border-sentinel-green/20">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                <span>REC_001 // LIVE_FEED</span>
            </div>
            
            <div className="absolute bottom-4 right-4 font-mono text-[10px] text-gray-500 tracking-widest">
                [ 1080p | 60FPS | ENCRYPTED ]
            </div>
        </motion.div>
      </div>
      
      {/* Background Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:40px_40px] pointer-events-none" />
    </section>
  );
};

export default VideoSection;
