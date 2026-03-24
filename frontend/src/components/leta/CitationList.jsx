import React from 'react';
import { BookOpen } from 'lucide-react';

const CitationList = ({ citations, isDark = false }) => {
  if (!citations || citations.length === 0) return null;

  return (
    <div className={`mt-4 border-t pt-4 ${isDark ? 'border-white/10' : 'border-gray-100'}`}>
      <h4 className="flex items-center gap-2 text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">
        <BookOpen size={14} />
        Sources & Citations
      </h4>
      <ul className="space-y-2">
        {citations.map((citation, idx) => (
          <li key={idx} className={`text-sm p-2 rounded border font-mono text-xs transition-all duration-200 ${
             isDark 
                ? 'bg-white/5 border-white/5 text-gray-300 hover:bg-white/10' 
                : 'text-sentinel-blue/80 bg-gray-50 border-gray-100 hover:bg-white hover:shadow-sm'
          }`}>
             <span className="font-bold text-sentinel-green mr-2">[{idx + 1}]</span>
             {citation}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default CitationList;
