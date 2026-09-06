import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, FileText, CheckCircle, Wand2, ArrowRight, Plus, Sparkles, Zap, Play } from 'lucide-react';

const TemplateCard = ({ template, isHero, onPreview }) => {
   const navigate = useNavigate();

   // Card dimensions for the shelf look
   const cardWidth = isHero ? 'w-[400px]' : 'w-[320px]';
   const cardHeight = isHero ? 'h-[220px]' : 'h-[180px]';

   return (
      <div className={`relative group ${cardWidth} ${cardHeight} rounded-leta overflow-visible cursor-pointer transition-all duration-500 ease-out 
      hover:scale-125 hover:z-[100] hover:shadow-[0_20px_50px_rgba(0,0,0,0.8)]`}>


         {/* Base Card - Static View */}
         <div className="absolute inset-0 bg-[#141414] rounded-leta border border-leta-gray-100 overflow-hidden flex flex-col">
            {/* Placeholder "Poster" with generic legal pattern */}
            <div className="h-2/3 w-full bg-gradient-to-br from-emerald-900/20 to-blue-900/10 relative flex items-center justify-center p-4">
               <FileText className="text-emerald-500/20 w-12 h-12" />
               <div className="absolute top-2 right-2 text-[8px] font-black text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-leta border border-emerald-500/20 uppercase">
                  {template.category || 'LETA_TEC_DOC'}
               </div>
            </div>
            <div className="flex-1 p-3 bg-[#181818] flex flex-col justify-center">
               <h3 className="text-leta-gray-900 text-sm font-bold truncate leading-tight tracking-tight">
                  {template.title}
               </h3>
               <div className="mt-1 flex items-center gap-2">
                  <span className="text-[10px] text-emerald-400 font-bold">98% Match</span>
                  <span className="text-[10px] text-leta-gray-600 font-medium tracking-tighter uppercase">{template.stage || 'Compliance'}</span>
               </div>
            </div>
         </div>

         {/* Expanded Hover Detail Overlay */}
         <div className="absolute top-0 left-0 w-full bg-[#181818] rounded-leta shadow-2xl overflow-hidden opacity-0 group-hover:opacity-100 
        transition-all duration-300 pointer-events-none group-hover:pointer-events-auto border-t border-leta-gray-200"
            style={{ transform: 'translateY(-10%)', height: 'fit-content', minHeight: '100%' }}>

            {/* Hover Mini-Billboard */}
            <div className="h-32 bg-gradient-to-br from-emerald-600/30 to-blue-600/10 relative flex items-center justify-center">
               <Zap size={32} className="text-emerald-400 opacity-40 animate-pulse" />
               <div className="absolute bottom-2 left-3 flex items-center gap-2">
                  <span className="flex items-center gap-1 text-[10px] font-black text-leta-gray-900 bg-emerald-600 px-2 py-1 rounded-leta">
                     <Sparkles size={10} /> MUST READ
                  </span>
               </div>
            </div>

            {/* Hover Controls & Meta */}
            <div className="p-4 flex flex-col gap-3 shadow-[0_-20px_40px_rgba(0,0,0,0.5)] bg-[#181818]">
               <div className="flex items-center justify-between">
                  <div className="flex gap-2">
                     <button
                        onClick={(e) => { e.stopPropagation(); onPreview(); }}
                        className="w-10 h-10 rounded-full bg-leta-white flex items-center justify-center text-leta-black hover:bg-leta-white/90 transition-all active:scale-95 shadow-xl"
                        title="Preview Strategy"
                     >
                        <Play size={20} className="fill-black ml-1" />
                     </button>
                     <button
                        className="w-10 h-10 rounded-full bg-transparent border border-leta-gray-600 flex items-center justify-center text-leta-gray-900 hover:border-leta-white transition-all active:scale-95"
                        title="Add to Library"
                     >
                        <Plus size={20} />
                     </button>
                  </div>
                  <button
                     onClick={(e) => { e.stopPropagation(); navigate(`/gst/templates/${template.id}/customize`); }}
                     className="btn-primary px-4 py-2 text-[9px] tracking-[0.1em]"
                  >
                     AI_CUSTOMIZE
                  </button>
               </div>

               <div className="space-y-1">
                  <div className="flex items-center gap-2 text-[11px] font-bold">
                     <span className="text-emerald-400">Trusted Strategy</span>
                     <span className="text-leta-gray-500">•</span>
                     <span className="text-leta-gray-300">Semantic Score: {template.score ? (template.score * 100).toFixed(0) : '95'}%</span>
                     <span className="px-1.5 py-0.5 border border-leta-gray-700 text-leta-gray-500 text-[8px] rounded-leta uppercase font-mono">HD</span>
                  </div>
                  <p className="text-[10px] text-leta-gray-600 line-clamp-2 leading-relaxed font-light">
                     {template.summary || 'Premium AI-optimized legal template for rapid compliance and strategic filing.'}
                  </p>
               </div>
            </div>
         </div>
      </div>
   );
};

export default TemplateCard;
