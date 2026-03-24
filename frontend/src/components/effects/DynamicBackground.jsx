import React from 'react';
import { motion } from 'framer-motion';

const DynamicBackground = ({ children, className = "" }) => {
  return (
    <div className={`relative overflow-hidden ${className}`}>
       {/* Animated Blobs */}
       <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
          <motion.div 
            animate={{ 
                x: [0, 100, 0],
                y: [0, -50, 0],
                rotate: [0, 180, 0]
            }}
            transition={{ 
                duration: 20,
                repeat: Infinity,
                ease: "linear"
            }}
            className="absolute -top-[10%] -left-[10%] w-[600px] h-[600px] bg-sentinel-green/10 rounded-full blur-[100px] opacity-70"
          />
          <motion.div 
             animate={{ 
                x: [0, -70, 0],
                y: [0, 100, 0],
                scale: [1, 1.2, 1]
             }}
             transition={{ 
                duration: 25,
                repeat: Infinity,
                ease: "linear"
             }}
             className="absolute top-[40%] -right-[5%] w-[500px] h-[500px] bg-sentinel-blue/20 rounded-full blur-[80px] opacity-60"
          />
           <motion.div 
             animate={{ 
                x: [0, 100, 0], 
                y: [0, 100, 0]
             }}
             transition={{ 
                duration: 30,
                repeat: Infinity,
                ease: "easeInOut"
             }}
             className="absolute bottom-0 left-[20%] w-[300px] h-[300px] bg-cyan-900/10 rounded-full blur-[60px]"
          />
       </div>

       {/* Content */}
       <div className="relative z-10">
         {children}
       </div>
    </div>
  );
};

export default DynamicBackground;
