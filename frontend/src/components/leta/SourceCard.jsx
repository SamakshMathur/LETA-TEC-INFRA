import React from 'react';
import { motion } from 'framer-motion';
import { FileText, ExternalLink } from 'lucide-react';

const SourceCard = ({ source, onClick, index = 0 }) => {
  const { title, page, url } = source;
  
  // Clean up title (remove path, replace %20)
  const cleanTitle = title.split(/[\\/]/).pop().replace(/%20/g, ' ');

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      whileHover={{ scale: 1.02, backgroundColor: 'rgba(255, 255, 255, 0.05)' }}
      whileTap={{ scale: 0.98 }}
      onClick={() => onClick({ url, page, title: cleanTitle })}
      className="flex flex-col p-3 bg-[#0A1622] border border-white/10 rounded-lg cursor-pointer group transition-all duration-300 hover:border-sentinel-green/40 shadow-sm"
    >
      <div className="flex items-start justify-between mb-2">
        <div className="p-1.5 bg-sentinel-green/10 rounded text-sentinel-green group-hover:bg-sentinel-green/20 transition-colors">
          <FileText size={14} />
        </div>
        <ExternalLink size={12} className="text-gray-600 group-hover:text-sentinel-green opacity-0 group-hover:opacity-100 transition-all" />
      </div>
      
      <div className="flex-1 min-w-0">
        <h4 className="text-[11px] font-bold text-gray-200 truncate leading-tight mb-1 group-hover:text-sentinel-green transition-colors">
          {cleanTitle}
        </h4>
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono text-gray-500 uppercase tracking-tighter">
            PROVISION AT PAGE {page}
          </span>
        </div>
      </div>
    </motion.div>
  );
};

export default SourceCard;
