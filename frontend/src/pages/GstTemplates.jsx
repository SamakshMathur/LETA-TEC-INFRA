import React, { useState, useEffect } from 'react';
import { Search, Loader2, Zap } from 'lucide-react';
import { TemplateResults } from '../components/templates';

const GstTemplates = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchTemplates = async (searchQuery = '') => {
    setIsLoading(true);
    try {
      const response = await fetch(`${import.meta.env.PROD ? '' : 'http://localhost:8000'}/api/templates/search?query=${encodeURIComponent(searchQuery)}`);
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

  const handleSearch = (e) => {
    e.preventDefault();
    fetchTemplates(query);
  };

  return (
    <div className="min-h-screen bg-[#020202] text-gray-200 selection:bg-emerald-500/30">
      
      {/* Cinematic Search Hero */}
      <div className="relative pt-32 pb-24 px-6 flex flex-col items-center overflow-hidden">
        {/* Background Visual Accents */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.08)_0%,transparent_70%)] pointer-events-none" />
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-emerald-500/5 blur-[120px] rounded-full animate-pulse" />
        
        <div className="relative z-10 max-w-4xl w-full text-center">
          <div className="inline-flex items-center gap-2 py-1 px-4 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] font-black tracking-[0.2em] text-emerald-400 mb-8 uppercase">
             <Zap size={10} className="fill-emerald-400" />
             Sovereign Retrieval Engine
          </div>
          
          <h1 className="text-5xl md:text-7xl font-black tracking-tight text-white mb-6 leading-tight">
            Litigation <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-emerald-600">Intelligence.</span>
          </h1>
          
          <p className="text-gray-400 text-lg md:text-xl font-light max-w-2xl mx-auto mb-12 leading-relaxed">
            Navigate through 1,150+ specialized legal templates and notifications with 
            millisecond-latency semantic matching.
          </p>

          {/* Premium Search Hub */}
          <form onSubmit={handleSearch} className="w-full relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-emerald-500/20 to-blue-500/20 rounded-2xl blur opacity-0 group-hover:opacity-100 transition duration-1000 group-hover:duration-200"></div>
            <div className="relative flex items-center bg-white/5 backdrop-blur-3xl border border-white/10 rounded-2xl overflow-hidden shadow-2xl transition-all duration-300 group-focus-within:border-emerald-500/50 group-focus-within:shadow-[0_0_50px_rgba(16,185,129,0.1)]">
              <div className="pl-6 text-gray-500 group-focus-within:text-emerald-500 transition-colors">
                <Search size={24} />
              </div>
              <input
                type="text"
                placeholder="Search by case facts, section, or document ID (e.g., ITC mismatch 3B)..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-transparent border-none py-6 px-6 text-white focus:outline-none focus:ring-0 text-xl font-light placeholder-gray-600"
              />
              <button 
                type="submit" 
                className="mr-3 bg-emerald-600 hover:bg-emerald-500 text-white px-10 py-4 rounded-xl font-black transition-all uppercase tracking-widest text-xs active:scale-95 shadow-lg shadow-emerald-900/20"
              >
                Match
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Results Area */}
      <div className="pb-24">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-32">
            <Loader2 className="animate-spin text-emerald-500 w-16 h-16 mb-6" />
            <p className="text-gray-500 font-mono tracking-[0.2em] text-[10px] uppercase animate-pulse">Syncing with legal cloud...</p>
          </div>
        ) : (
          <TemplateResults groups={results} />
        )}
      </div>
    </div>
  );
};

export default GstTemplates;
