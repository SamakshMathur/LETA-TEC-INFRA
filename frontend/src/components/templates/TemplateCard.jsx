import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, FileText, CheckCircle, Wand2, ArrowRight } from 'lucide-react';

const TemplateCard = ({ template, isHero, onPreview }) => {
  const navigate = useNavigate();
  
  const cardWidth = isHero ? 'w-80' : 'w-72';
  const cardHeight = isHero ? 'h-[440px]' : 'h-[400px]';

  return (
    <div className={`relative group ${cardWidth} ${cardHeight} rounded-2xl overflow-hidden bg-glass border-white/5 transition-all duration-700 hover:scale-[1.02] hover:border-emerald-500/50 hover:shadow-[0_20px_60px_rgba(16,185,129,0.15)] group`}>
      
      {/* Premium Document Pattern Overlay */}
      <div className="absolute inset-0 opacity-[0.03] group-hover:opacity-10 transition-opacity duration-700">
        <div className="w-full h-full flex flex-col p-6 space-y-4">
          {[...Array(12)].map((_, i) => (
            <div key={i} className={`h-1.5 bg-white rounded-full ${i % 3 === 0 ? 'w-full' : 'w-2/3'}`}></div>
          ))}
        </div>
      </div>

      {/* Decorative Accents */}
      <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 blur-3xl rounded-full" />
      <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-blue-500/5 blur-3xl rounded-full" />

      {/* Content - Static State */}
      <div className="absolute inset-0 p-6 flex flex-col justify-between z-10">
        <div>
          <div className="flex items-center justify-between mb-4">
            <span className="text-[9px] font-black tracking-[0.2em] text-emerald-400 px-3 py-1 transparent uppercase border border-emerald-500/30 rounded-md backdrop-blur-md">
              {template.category || 'TITAN_DOC'}
            </span>
            {isHero && (
              <div className="flex items-center gap-1 text-[8px] font-bold text-gray-500 tracking-tighter">
                <CheckCircle size={10} className="text-emerald-500" />
                VERIFIED AI DRAFT
              </div>
            )}
          </div>
          
          <h3 className={`font-bold text-white leading-[1.3] font-sans transition-colors duration-500 ${isHero ? 'text-2xl' : 'text-xl'}`}>
            {template.title}
          </h3>
          
          <div className="mt-4 flex flex-wrap gap-2 opacity-60">
             <span className="text-[10px] text-gray-300 font-medium">#{template.stage || 'Compliance'}</span>
             <span className="text-[10px] text-gray-300 font-medium">• 12k Words</span>
          </div>
        </div>
        
        {isHero && (
          <p className="text-sm text-gray-400 line-clamp-3 mb-6 font-light leading-relaxed">
            {template.summary}
          </p>
        )}

        {/* View Details Hint */}
        <div className="flex items-center gap-2 text-[10px] font-bold text-emerald-500 group-hover:opacity-0 transition-opacity duration-300">
          <Eye size={12} />
          SCROLL TO PREVIEW
        </div>
      </div>

      {/* Titanium Hover Overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black via-black/95 to-transparent opacity-0 group-hover:opacity-100 transition-all duration-500 z-20 flex flex-col justify-end p-6 translate-y-4 group-hover:translate-y-0">
        
        <p className="text-[13px] text-gray-400 font-light leading-relaxed mb-8">
          {template.summary || 'Premium AI-optimized legal template for rapid compliance and strategic filing.'}
        </p>
        
        <div className="flex flex-col gap-3">
          <div className="flex gap-3">
            <button 
              onClick={(e) => {
                e.preventDefault();
                onPreview();
              }}
              className="flex-1 flex items-center justify-center gap-2 bg-white text-black py-3 rounded-xl text-xs font-black tracking-widest uppercase hover:bg-emerald-50 transition-all active:scale-95"
            >
              PREVIEW
            </button>
            <button 
              className="flex items-center justify-center p-3 bg-white/10 border border-white/10 rounded-xl text-white hover:bg-emerald-500/20 hover:border-emerald-500 transition-all"
              title="Download Original"
            >
              <FileText size={18} />
            </button>
          </div>

          <button 
            onClick={() => navigate(`/gst/templates/${template.id}/customize`)}
            className="w-full flex items-center justify-center gap-3 bg-emerald-600 text-white py-4 rounded-xl text-xs font-black tracking-[0.1em] uppercase shadow-[0_10px_30px_rgba(16,185,129,0.3)] hover:bg-emerald-500 transition-all hover:shadow-[0_15px_40px_rgba(16,185,129,0.4)] active:scale-95"
          >
            <Wand2 size={16} /> 
            <span>CHAT WITH LETA</span>
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default TemplateCard;
