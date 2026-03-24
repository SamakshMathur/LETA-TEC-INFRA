import React, { useRef } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import TemplateCard from './TemplateCard';

const TemplateRow = ({ title, templates, isHero, onPreview }) => {
  const scrollRef = useRef(null);

  const scrollLeft = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: -800, behavior: 'smooth' });
    }
  };

  const scrollRight = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: 800, behavior: 'smooth' });
    }
  };

  if (!templates || templates.length === 0) return null;

  return (
    <div className="relative group/row py-8 first:pt-0">
      <div className="flex items-end justify-between px-12 mb-6">
        <h2 className={`font-black tracking-tight text-white uppercase ${isHero ? 'text-3xl' : 'text-xl'}`}>
          {title}
          {isHero && <span className="ml-4 text-xs text-emerald-500 font-mono tracking-[0.3em]">CORE_DRAFTS</span>}
        </h2>
        <div className="h-[1px] flex-grow mx-8 bg-white/5" />
      </div>
      
      <div className="relative px-4">
        {/* Left Scroll Button - Glass UI */}
        <button 
          onClick={scrollLeft}
          className="absolute left-0 top-0 bottom-0 w-24 flex items-center justify-center opacity-0 group-hover/row:opacity-100 transition-all duration-500 bg-gradient-to-r from-black via-black/40 to-transparent z-40 text-white hover:text-emerald-400 backdrop-blur-[2px]"
          aria-label="Scroll left"
        >
          <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center hover:bg-emerald-500/20 hover:border-emerald-500/50 transition-all">
            <ChevronLeft size={32} />
          </div>
        </button>

        {/* Scrollable Container */}
        <div 
          ref={scrollRef}
          className={`flex gap-6 overflow-x-hidden scroll-smooth pb-12 pt-4 px-12 mask-fade-edges ${isHero ? 'gap-8' : ''}`}
        >
          {templates.map((template) => (
            <div key={template.id} className="flex-none transition-all duration-500 hover:z-30">
              <TemplateCard 
                template={template} 
                isHero={isHero} 
                onPreview={() => onPreview(template.id)} 
              />
            </div>
          ))}
        </div>

        {/* Right Scroll Button - Glass UI */}
        <button 
          onClick={scrollRight}
          className="absolute right-0 top-0 bottom-0 w-24 flex items-center justify-center opacity-0 group-hover/row:opacity-100 transition-all duration-500 bg-gradient-to-l from-black via-black/40 to-transparent z-40 text-white hover:text-emerald-400 backdrop-blur-[2px]"
          aria-label="Scroll right"
        >
          <div className="w-12 h-12 rounded-full bg-white/5 border border-white/10 flex items-center justify-center hover:bg-emerald-500/20 hover:border-emerald-500/50 transition-all">
            <ChevronRight size={32} />
          </div>
        </button>
      </div>
    </div>
  );
};

export default TemplateRow;
