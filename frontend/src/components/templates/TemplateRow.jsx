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
      <div className="flex items-end justify-between px-12 mb-4">
        <h2 className="font-bold tracking-tight text-[#e5e5e5] text-lg md:text-xl transition-colors hover:text-white">
          {title}
        </h2>
      </div>
      
      <div className="relative group">
        {/* Left Scroll Button - Netflix Glass UI */}
        <button 
          onClick={scrollLeft}
          className="absolute left-0 top-0 bottom-0 w-12 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-300 bg-black/50 z-[110] text-white hover:bg-black/70"
          aria-label="Scroll left"
        >
          <ChevronLeft size={40} />
        </button>

        {/* Scrollable Container - Padded for hover scaling */}
        <div 
          ref={scrollRef}
          className="flex gap-2 overflow-x-hidden scroll-smooth py-12 px-12 mask-fade-row no-scrollbar"
        >
          {templates.map((template) => (
            <div key={template.id} className="flex-none">
              <TemplateCard 
                template={template} 
                isHero={isHero} 
                onPreview={() => onPreview(template.id)} 
              />
            </div>
          ))}
        </div>

        {/* Right Scroll Button - Netflix Glass UI */}
        <button 
          onClick={scrollRight}
          className="absolute right-0 top-0 bottom-0 w-12 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all duration-300 bg-black/50 z-[110] text-white hover:bg-black/70"
          aria-label="Scroll right"
        >
          <ChevronRight size={40} />
        </button>
      </div>
    </div>
  );
};

export default TemplateRow;
