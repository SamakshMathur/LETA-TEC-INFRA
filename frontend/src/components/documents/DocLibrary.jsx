import React from 'react';
import { Layers, FileText, BookOpen, Gavel, Smartphone, Scroll, File, Globe, Truck } from 'lucide-react';

const categories = [
  { id: 'circulars', label: 'CIRCULARS', count: 0, icon: Layers },
  { id: 'forms', label: 'FORMS', count: 0, icon: FileText },
  { id: 'flyers', label: 'FLYERS', count: 0, icon: BookOpen },
  { id: 'aars', label: 'AARS', count: 0, icon: Gavel },
  { id: 'acts', label: 'ACTS', count: 0, icon: Smartphone }, // Using Smartphone as proxy for 'mobile-like' icon in screenshot, or maybe Book
  { id: 'rules', label: 'RULES', count: 0, icon: Scroll },
  { id: 'cgst', label: 'CGST', count: 0, icon: File },
  { id: 'igst', label: 'IGST', count: 0, icon: Globe },
  { id: 'export', label: 'EXPORT', count: 0, icon: Truck },
];

const DocLibrary = () => {
  return (
    <div className="w-full bg-[#050505] border border-white/10 rounded-lg overflow-hidden font-mono">
      {/* Header */}
      <div className="p-4 border-b border-white/10 flex justify-between items-center bg-[#0a0a0a]">
        <div className="flex items-center gap-2 text-xl text-white font-bold tracking-wider">
           <BookOpen className="text-sentinel-green" size={20} />
           <span>DOC_LIBRARY_V1.0</span>
        </div>
        <div className="text-xs text-gray-600 tracking-widest">
          ID: GST_DATABASE_ACTIVE
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-y divide-white/10 border-b border-white/10">
        {categories.map((item) => (
          <div 
            key={item.id} 
            className="group relative p-8 flex flex-col items-center justify-center gap-4 hover:bg-white/5 transition-colors cursor-pointer"
          >
            <div className="text-gray-500 group-hover:text-sentinel-green transition-colors duration-300">
              <item.icon strokeWidth={1.5} size={32} />
            </div>
            
            <div className="text-center">
              <div className="text-gray-400 font-medium tracking-widest text-sm mb-1 group-hover:text-white transition-colors">
                {item.label}
              </div>
              <div className="text-gray-600 text-xs">
                [{item.count}]
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DocLibrary;
