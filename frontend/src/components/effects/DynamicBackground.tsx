import React from 'react';
import { motion } from 'framer-motion';

interface DynamicBackgroundProps {
  children?: React.ReactNode;
  className?: string;
}

const DynamicBackground: React.FC<DynamicBackgroundProps> = ({ children, className = "" }) => {
  return (
    <div className={`relative overflow-hidden ${className}`}>
       {/* Animated Blobs */}
       <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
          <motion.div 
            animate={{ 
                x: [0, 80, 0],
                y: [0, -40, 0],
                rotate: [0, 180, 0]
            }}
            transition={{ 
                duration: 25,
                repeat: Infinity,
                ease: "linear"
            }}
            className="absolute -top-[15%] -left-[15%] w-[500px] h-[500px] bg-[#4FB7C5]/05 rounded-full blur-[100px] opacity-40"
            style={{ willChange: 'transform' }}
          />
          <motion.div 
             animate={{ 
                x: [0, -50, 0],
                y: [0, 80, 0],
                scale: [1, 1.1, 1]
             }}
             transition={{ 
                duration: 30,
                repeat: Infinity,
                ease: "linear"
             }}
             className="absolute top-[40%] -right-[10%] w-[450px] h-[450px] bg-[#6C7A99]/05 rounded-full blur-[90px] opacity-35"
             style={{ willChange: 'transform' }}
          />
           <motion.div 
             animate={{ 
                x: [0, 60, 0], 
                y: [0, 60, 0]
             }}
             transition={{ 
                duration: 35,
                repeat: Infinity,
                ease: "easeInOut"
             }}
             className="absolute bottom-0 left-[20%] w-[250px] h-[250px] bg-[#131D2B]/20 rounded-full blur-[60px]"
             style={{ willChange: 'transform' }}
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
