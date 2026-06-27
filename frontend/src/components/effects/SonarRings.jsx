import React from 'react';
import { motion } from 'framer-motion';

const RINGS = [0, 1, 2, 3, 4];

export const SonarRings = ({ className = '' }) => {
  return (
    <div className={`pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden ${className}`}>
      {RINGS.map((i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            border: '1px solid rgba(79, 183, 197, 0.18)',
            width: '200px',
            height: '200px',
          }}
          animate={{
            scale: [1, 8],
            opacity: [0.55, 0],
          }}
          transition={{
            duration: 6,
            delay: i * 1.2,
            repeat: Infinity,
            ease: 'easeOut',
          }}
        />
      ))}
    </div>
  );
};

export default SonarRings;
