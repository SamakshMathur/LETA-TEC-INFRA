import React from 'react';
import { motion } from 'framer-motion';
import { FileText, ExternalLink } from 'lucide-react';

const SourceCard = ({ source, onClick, index = 0 }) => {
  const { title, page, url } = source;
  const cleanTitle = title.split(/[\\/]/).pop().replace(/%20/g, ' ');

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      onClick={() => onClick({ url, page, title: cleanTitle })}
      className="flex flex-col p-3 rounded-xl cursor-pointer group transition-all duration-150"
      style={{
        background: 'rgba(103,232,249,0.06)',
        border: '1px solid rgba(103,232,249,0.15)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'rgba(103,232,249,0.4)';
        e.currentTarget.style.background = 'rgba(103,232,249,0.1)';
        e.currentTarget.style.boxShadow = '0 0 15px rgba(103,232,249,0.15)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'rgba(103,232,249,0.15)';
        e.currentTarget.style.background = 'rgba(103,232,249,0.06)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="p-1.5 rounded-lg" style={{ background: 'rgba(103,232,249,0.12)', color: '#67E8F9' }}>
          <FileText size={13} />
        </div>
        <ExternalLink size={11} className="opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: '#67E8F9' }} />
      </div>

      <div className="flex-1 min-w-0">
        <h4 className="text-[11px] font-bold truncate leading-tight mb-1 transition-colors" style={{ color: '#CBD5E1' }}>
          {cleanTitle}
        </h4>
        <span className="text-[9px] font-mono uppercase tracking-tighter" style={{ color: '#475569' }}>
          PROVISION AT PAGE {page}
        </span>
      </div>
    </motion.div>
  );
};

export default SourceCard;
