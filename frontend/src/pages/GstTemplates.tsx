import React, { useState, useEffect } from 'react';
import { Search, Loader2, Zap, Sparkles } from 'lucide-react';
import { TemplateResults } from '../components/templates';
import { BASE_URL } from '../config/api';

const GstTemplates: React.FC = () => {
  const [query, setQuery] = useState<string>('');
  const [results, setResults] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchTemplates = async (searchQuery: string = '') => {
    setIsLoading(true);
    try {
      const response = await fetch(`${BASE_URL}/api/templates/search?query=${encodeURIComponent(searchQuery)}`);
      const data = await response.json();
      setResults(data.groups || []);
    } catch (error) {
      console.error("Failed to fetch templates:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchTemplates(query);
  };

  return (
    <div className="min-h-screen bg-[#141414] text-leta-gray-900 selection:bg-emerald-500/30">
      
      {/* 🎬 Netflix-Style Billboard Hero */}
      <div className="relative min-h-[90vh] w-full overflow-hidden flex flex-col">
        {/* Cinematic Backdrop */}
        <div className="absolute inset-0 bg-gradient-to-r from-[#141414] via-[#141414]/80 to-transparent z-10" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#141414] via-transparent to-transparent z-10" />
        
        {/* Animated Visual Accent */}
        <div className="absolute right-0 top-0 w-2/3 h-full overflow-hidden opacity-40">
           <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.15)_0%,transparent_70%)] animate-pulse" />
           <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] border border-emerald-500/10 rounded-full animate-[spin_60s_linear_infinite]" />
           <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] border border-blue-500/5 rounded-full animate-[spin_40s_linear_infinite_reverse]" />
        </div>

        {/* Billboard Content */}
        <div className="relative z-20 flex-1 flex flex-col justify-center px-12 md:px-24 max-w-4xl pt-40 pb-24">
           <div className="flex items-center gap-3 mb-6">
              <div className="flex items-center gap-1.5 px-2 py-0.5 bg-emerald-600 rounded-leta text-[10px] font-black tracking-widest uppercase">
                 <Zap size={12} fill="white" /> Trending
              </div>
              <span className="text-sm font-bold text-leta-gray-600 tracking-tight">Legal Strategy #127: GSTR-3B vs 2B Mismatch</span>
           </div>

           <h1 className="text-6xl md:text-8xl font-black tracking-tighter mb-6 leading-[0.9] uppercase italic">
              Litigation <br/>
              <span className="text-emerald-500 text-shadow-[0_0_30px_rgba(16,185,129,0.5)]">Intelligence.</span>
           </h1>

           <p className="text-lg md:text-xl text-leta-gray-300 font-light max-w-xl mb-10 leading-relaxed">
              Navigate 1,150+ high-end litigation templates with millisecond-latency semantic matching. 
              Drafted by senior counsels, optimized by TITAN AI for 100% compliance.
           </p>

           <div className="flex flex-wrap gap-4 mb-16">
              <button 
                onClick={() => fetchTemplates('ITC mismatch')}
                className="flex items-center gap-3 bg-leta-white text-leta-black px-8 py-4 rounded-leta font-bold text-lg hover:bg-leta-white/90 transition-all active:scale-95 shadow-2xl"
              >
                 <Zap size={24} fill="black" /> Get Started
              </button>
              <button 
                className="flex items-center gap-3 bg-leta-gray-500/30 backdrop-blur-md text-leta-gray-900 px-8 py-4 rounded-leta font-bold text-lg border border-leta-gray-200 hover:bg-leta-gray-500/40 transition-all"
              >
                 <Sparkles size={24} /> More Info
              </button>
           </div>

           {/* Integrated Search Hub - now part of the flow to prevent overlap */}
           <div className="w-full max-w-2xl group focus-within:max-w-3xl transition-all duration-700">
              <form onSubmit={handleSearch} className="relative">
                 <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500/20 to-blue-500/20 rounded-leta blur opacity-0 group-hover:opacity-100 transition duration-1000"></div>
                 <div className="relative flex items-center bg-[#181818]/60 backdrop-blur-xl border border-leta-gray-200 rounded-leta overflow-hidden">
                   <div className="pl-6 text-leta-gray-500">
                     <Search size={24} />
                   </div>
                   <input
                     type="text"
                     placeholder="Ask for specific case facts or sections..."
                     value={query}
                     onChange={(e) => setQuery(e.target.value)}
                     className="w-full bg-transparent border-none py-6 px-6 text-leta-gray-900 focus:outline-none focus:ring-0 text-lg font-light placeholder-gray-600"
                   />
                 </div>
              </form>
           </div>
        </div>
      </div>

      {/* Results Area */}
      <div className="pb-24 mt-12">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-32">
            <Loader2 className="animate-spin text-emerald-500 w-16 h-16 mb-6" />
            <p className="text-leta-gray-500 font-mono tracking-[0.2em] text-[10px] uppercase animate-pulse">Syncing with legal cloud...</p>
          </div>
        ) : (
          <TemplateResults groups={results} />
        )}
      </div>
    </div>
  );
};

export default GstTemplates;
