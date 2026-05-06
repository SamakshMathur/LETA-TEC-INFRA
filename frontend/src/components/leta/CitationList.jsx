import React from 'react';
import { BookOpen } from 'lucide-react';

const CitationList = ({ citations, isDark = false }) => {
  if (!citations || citations.length === 0) return null;

  return (
    <div className={`mt-4 border-t pt-4 ${isDark ? 'border-leta-gray-200' : 'border-leta-gray-100'}`}>
      <h4 className="flex items-center gap-2 text-xs font-bold text-leta-gray-600 uppercase tracking-widest mb-3">
        <BookOpen size={14} />
        Sources & Citations
      </h4>
      <ul className="space-y-2">
        {citations.map((citation, idx) => (
          <li key={idx} className={`text-sm p-2 rounded-leta border font-mono text-xs transition-all duration-200 ${
             isDark 
                ? 'bg-leta-gray-50 border-leta-gray-100 text-leta-gray-300 hover:bg-leta-white/10' 
                : 'text-leta-gray-900/80 bg-leta-gray-50 border-leta-gray-100 hover:bg-leta-white hover:shadow-sm'
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
