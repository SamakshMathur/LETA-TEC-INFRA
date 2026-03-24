import { motion } from 'framer-motion';
import React from 'react';
const AmbientBackground = () => {
  return (
    <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
      {/* Primary Teal Spotlight - Top Left */}
      <motion.div 
        animate={{ 
          scale: [1, 1.2, 1],
          opacity: [0.3, 0.5, 0.3],
          x: [-20, 20, -20],
          y: [-20, 20, -20],
        }}
        transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
        className="absolute -top-[20%] -left-[10%] w-[70vw] h-[70vw] rounded-full bg-sentinel-green/10 blur-[120px]"
      />

      {/* Secondary Blue Spotlight - Bottom Right */}
      <motion.div 
        animate={{ 
          scale: [1, 1.3, 1],
          opacity: [0.2, 0.4, 0.2],
          x: [20, -20, 20],
        }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut", delay: 2 }}
        className="absolute -bottom-[20%] -right-[10%] w-[60vw] h-[60vw] rounded-full bg-sentinel-blue/10 blur-[120px]"
      />

      {/* Cinematic Gold Accent - Center (Subtle) */}
      <motion.div 
        animate={{ 
          opacity: [0, 0.05, 0],
        }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 5 }}
        className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[40vw] h-[40vw] rounded-full bg-cinema-gold/5 blur-[150px]"
      />
    </div>
  );
};

export default AmbientBackground;
