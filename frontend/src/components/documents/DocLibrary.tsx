import React from 'react';
import { Layers, FileText, BookOpen, Gavel, Smartphone, Scroll, File, Globe, Truck, LucideIcon } from 'lucide-react';

interface Category {
  id: string;
  label: string;
  count: number;
  icon: LucideIcon;
}

const categories: Category[] = [
  { id: 'circulars', label: 'CIRCULARS', count: 0, icon: Layers },
  { id: 'forms', label: 'FORMS', count: 0, icon: FileText },
  { id: 'flyers', label: 'FLYERS', count: 0, icon: BookOpen },
  { id: 'aars', label: 'AARS', count: 0, icon: Gavel },
  { id: 'acts', label: 'ACTS', count: 0, icon: Smartphone },
  { id: 'rules', label: 'RULES', count: 0, icon: Scroll },
  { id: 'cgst', label: 'CGST', count: 0, icon: File },
  { id: 'igst', label: 'IGST', count: 0, icon: Globe },
  { id: 'export', label: 'EXPORT', count: 0, icon: Truck },
];

const DocLibrary: React.FC = () => {
  return (
    <div className="w-full bg-[#050505] border border-leta-gray-200 rounded-leta overflow-hidden font-mono">
      {/* Header */}
      <div className="p-4 border-b border-leta-gray-200 flex justify-between items-center bg-[#0a0a0a]">
        <div className="flex items-center gap-2 text-xl text-leta-gray-900 font-bold tracking-wider">
           <BookOpen className="text-[#00df9a]" size={20} />
           <span>DOC_LIBRARY_V1.0</span>
        </div>
        <div className="text-xs text-leta-gray-600 tracking-widest">
          ID: GST_DATABASE_ACTIVE
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-y divide-white/10 border-b border-leta-gray-200">
        {categories.map((item) => (
          <div 
            key={item.id} 
            className="group relative p-8 flex flex-col items-center justify-center gap-4 hover:bg-leta-gray-50 transition-colors cursor-pointer"
          >
            <div className="text-leta-gray-500 group-hover:text-[#00df9a] transition-colors duration-300">
              <item.icon strokeWidth={1.5} size={32} />
            </div>
            
            <div className="text-center">
              <div className="text-leta-gray-600 font-medium tracking-widest text-sm mb-1 group-hover:text-leta-gray-900 transition-colors">
                {item.label}
              </div>
              <div className="text-leta-gray-600 text-xs">
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
