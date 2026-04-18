import React from 'react';
import { motion } from 'framer-motion';
import { Search, Loader2 } from 'lucide-react';

const SimpleSearchLoader = () => {
  return (
    <div className="flex flex-col items-center justify-center py-10 w-full animate-in fade-in duration-500">
      <div className="relative mb-6">
        <motion.div
           animate={{ rotate: 360 }}
           transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
           className="p-4 rounded-full border border-sentinel-green/20 bg-sentinel-green/5"
        >
          <Search size={28} className="text-sentinel-green" />
        </motion.div>
        <motion.div 
           initial={{ scale: 0.8, opacity: 0 }}
           animate={{ scale: 1.5, opacity: [0, 0.2, 0] }}
           transition={{ duration: 2, repeat: Infinity }}
           className="absolute inset-0 rounded-full bg-sentinel-green"
        />
      </div>
      
      <div className="flex items-center gap-3">
        <Loader2 size={16} className="text-sentinel-green animate-spin" />
        <h2 className="text-sm font-mono font-bold text-white uppercase tracking-[0.3em]">
          Querying Advisory Protocol
        </h2>
      </div>
      <p className="mt-2 text-[10px] font-mono text-gray-500 uppercase tracking-widest">
        Scanning Statute Database & Recent Circulars
      </p>
    </div>
  );
};

export default SimpleSearchLoader;
