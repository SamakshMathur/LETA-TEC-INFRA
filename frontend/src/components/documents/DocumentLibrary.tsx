import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, Layers, BookOpen, Gavel, Book, Scroll, Globe, Truck, ChevronLeft, ChevronRight, Bookmark, Download, ExternalLink, Info, Search, Sparkles, X, Brain } from 'lucide-react';
import DocPreviewSidebar from './DocPreviewSidebar';

const categoryGroups = [
  {
    title: "GST STATUTORY ARCHIVES",
    rows: [
      { id: 'circulars', label: 'Circulars & Notifications', icon: Layers, color: 'text-indigo-400', accent: 'bg-indigo-500/20' },
      { id: 'aars', label: 'Advance Rulings (AAR)', icon: Gavel, color: 'text-rose-400', accent: 'bg-rose-500/20' },
      { id: 'highcourt', label: 'High Court Case Laws', icon: Book, color: 'text-amber-400', accent: 'bg-amber-500/20' },
      { id: 'supremecourt', label: 'Supreme Court Case Laws', icon: Gavel, color: 'text-emerald-400', accent: 'bg-emerald-500/20' },
    ]
  },
  {
    title: "OPERATIONAL RESOURCES",
    rows: [
      { id: 'forms', label: 'Statutory Forms', icon: FileText, color: 'text-blue-400', accent: 'bg-blue-500/20' },
      { id: 'brochures', label: 'Official Brochures', icon: BookOpen, color: 'text-purple-400', accent: 'bg-purple-500/20' },
      { id: 'flyers', label: 'Information Flyers', icon: Info, color: 'text-cyan-400', accent: 'bg-cyan-500/20' },
    ]
  },
  {
    title: "ACTS & FRAMEWORKS",
    rows: [
      { id: 'acts', label: 'The GST Acts', icon: Book, color: 'text-orange-400', accent: 'bg-orange-500/20' },
      { id: 'rules', label: 'Statutory Rules', icon: Scroll, color: 'text-yellow-400', accent: 'bg-yellow-500/20' },
      { id: 'cgst', label: 'CGST Notifications', icon: FileText, color: 'text-indigo-400', accent: 'bg-indigo-500/20' },
      { id: 'igst', label: 'IGST Notifications', icon: Globe, color: 'text-cyan-400', accent: 'bg-cyan-500/20' },
    ]
  }
];

import { BASE_URL as VITE_API_BASE } from '../../config/api';
const API_BASE = `${VITE_API_BASE}/api/documents`;

// --- SUB-COMPONENT: PRIME CARD ---
const DocCard = ({ doc, onClick, onDownload, accentColor }) => {
  return (
    <motion.div 
      whileHover={{ scale: 1.05, zIndex: 10 }}
      className="relative flex-shrink-0 w-64 h-36 bg-[#081018] rounded-xl border border-white/5 overflow-hidden group cursor-pointer transition-all duration-300 hover:shadow-[0_10px_30px_rgba(0,0,0,0.5)] hover:border-white/20"
      onClick={() => onClick(doc)}
    >
      {/* Background Pattern */}
      <div className="absolute inset-0 opacity-10 group-hover:opacity-20 transition-opacity">
        <div className="w-full h-full bg-grid-white/[0.02]" />
      </div>

      <div className="absolute inset-0 p-4 flex flex-col justify-between">
         <div className="flex justify-between items-start">
            <div className={`p-2 rounded-lg ${accentColor}`}>
               <FileText size={18} className="text-white" />
            </div>
            <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
               <button 
                  onClick={(e) => { e.stopPropagation(); onDownload(doc); }}
                  className="p-1.5 rounded-full bg-white/10 hover:bg-emerald-500/20 text-white/70 hover:text-emerald-400 transition-all"
               >
                  <Download size={14} />
               </button>
               <button className="p-1.5 rounded-full bg-white/10 hover:bg-blue-500/20 text-white/70 hover:text-blue-400 transition-all">
                  <Bookmark size={14} />
               </button>
            </div>
         </div>

         <div>
            <h4 className="text-xs font-bold text-white line-clamp-2 leading-tight group-hover:text-emerald-400 transition-colors uppercase tracking-tight">
               {doc.title.replace('.pdf', '')}
            </h4>
            <div className="flex items-center gap-2 mt-2">
               <span className="text-[9px] font-black text-gray-500 px-1.5 py-0.5 rounded-sm bg-white/5 border border-white/5">PDF</span>
               <span className="text-[9px] text-gray-600 font-mono tracking-tighter uppercase">{doc.size}</span>
            </div>
         </div>
      </div>

      {/* Hover Overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
    </motion.div>
  );
};

// --- SUB-COMPONENT: CATEGORY ROW ---
const DocumentRow = ({ category, onDocClick, onDownload }) => {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/list/${category.id}`)
      .then(res => res.json())
      .then(data => {
        setDocs(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [category.id]);

  const scroll = (direction) => {
    if (scrollRef.current) {
      const { scrollLeft, clientWidth } = scrollRef.current;
      const scrollTo = direction === 'left' ? scrollLeft - clientWidth / 2 : scrollLeft + clientWidth / 2;
      scrollRef.current.scrollTo({ left: scrollTo, behavior: 'smooth' });
    }
  };

  if (!loading && docs.length === 0) return null;

  return (
    <div className="mb-10 group/row">
      <div className="flex items-center justify-between px-8 mb-4">
        <h3 className="text-sm font-black tracking-[0.2em] text-gray-400 uppercase flex items-center gap-3">
          <category.icon size={16} className={category.color} />
          {category.label}
          <span className="text-[10px] text-gray-700 font-mono">[{docs.length}]</span>
        </h3>
        <div className="flex gap-2 opacity-0 group-hover/row:opacity-100 transition-opacity">
           <button onClick={() => scroll('left')} className="p-2 rounded-full bg-white/5 border border-white/5 text-gray-400 hover:text-white hover:border-white/20">
              <ChevronLeft size={16} />
           </button>
           <button onClick={() => scroll('right')} className="p-2 rounded-full bg-white/5 border border-white/5 text-gray-400 hover:text-white hover:border-white/20">
              <ChevronRight size={16} />
           </button>
        </div>
      </div>

      <div 
        ref={scrollRef}
        className="flex gap-4 overflow-x-auto px-8 no-scrollbar scroll-smooth"
      >
        {loading ? (
          [1, 2, 3, 4].map(i => (
            <div key={i} className="flex-shrink-0 w-64 h-36 bg-white/5 rounded-xl animate-pulse border border-white/5" />
          ))
        ) : (
          docs.slice(0, 20).map((doc) => (
            <DocCard 
               key={doc.id} 
               doc={doc} 
               onClick={onDocClick} 
               onDownload={onDownload}
               accentColor={category.accent} 
            />
          ))
        )}
      </div>
    </div>
  );
};

const DocumentLibrary = () => {
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [aiResults, setAiResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const searchRef = useRef(null);

  // Semantic AI Search Effect
  useEffect(() => {
    if (searchQuery.trim().length < 3) {
      setAiResults([]);
      return;
    }

    const timer = setTimeout(() => {
      setIsSearching(true);
      fetch(`${VITE_API_BASE}/api/documents/ai_search?query=${encodeURIComponent(searchQuery)}`)
        .then(res => res.json())
        .then(data => {
          setAiResults(data);
          setIsSearching(false);
        })
        .catch(() => setIsSearching(false));
    }, 500);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleDownload = (doc) => {
    const category = doc.id.split('_')[0];
    window.open(`${API_BASE}/view?category=${category}&filename=${encodeURIComponent(doc.filename)}`, '_blank');
  };

  return (
    <div className="relative min-h-screen bg-[#020202] rounded-3xl overflow-hidden border border-white/5 mt-12 mb-20 pb-20">
      {/* Background Glow */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-emerald-500/5 blur-[120px] rounded-full -translate-y-1/2 translate-x-1/2 pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-indigo-500/5 blur-[120px] rounded-full translate-y-1/2 -translate-x-1/2 pointer-events-none" />

      {/* HEADER SECTION */}
      <div className="px-8 py-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 border-b border-white/5 bg-gradient-to-b from-[#050A10] to-transparent">
        <div>
          <h2 className="text-3xl font-black text-white tracking-tighter flex items-center gap-4">
            <BookOpen className="text-emerald-500" size={32} />
            DOC_LIBRARY_V1.0
          </h2>
          <p className="text-xs text-gray-500 font-mono mt-2 tracking-widest uppercase">
            // STATUS: <span className="text-emerald-400">ACTIVE</span> // ENCRYPTION: <span className="text-emerald-400">MIL_SPEC</span>
          </p>
        </div>
        <div className="flex gap-3">
           <button className="px-5 py-2.5 bg-white/5 border border-white/10 rounded-lg text-xs font-bold text-white hover:bg-white/10 transition-all flex items-center gap-2">
              <Layers size={14} />
              All Notifications
           </button>
           <button className="px-5 py-2.5 bg-emerald-500 text-black border border-emerald-400 rounded-lg text-xs font-black uppercase tracking-widest hover:bg-emerald-400 transition-all flex items-center gap-2 shadow-[0_0_20px_rgba(16,185,129,0.2)]">
              <Download size={14} />
              Bulk Export
           </button>
        </div>
      </div>

      {/* SEARCH BAR (NETFLIX STYLE) */}
      <div className="px-8 py-6 sticky top-0 z-40 bg-[#020202]/80 backdrop-blur-xl border-b border-white/5">
         <div className="flex items-center justify-between gap-4">
            <motion.div 
              ref={searchRef}
              initial={false}
              animate={{ width: isSearchFocused || searchQuery ? '100%': '300px' }}
              className="relative group flex items-center"
            >
               <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Search className={`h-4 w-4 ${isSearching ? 'animate-spin text-emerald-400' : 'text-gray-500'} transition-colors`} />
               </div>
               <input 
                  type="text" 
                  value={searchQuery}
                  onFocus={() => setIsSearchFocused(true)}
                  onBlur={() => !searchQuery && setIsSearchFocused(false)}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="SEARCH UNIVERSAL STATUTES, CASE LAWS, AND CIRCULARS..." 
                  className="block w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-12 pr-12 text-xs font-mono text-white placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 transition-all"
               />
               <AnimatePresence>
                  {searchQuery && (
                    <motion.button
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      onClick={() => setSearchQuery('')}
                      className="absolute right-4 p-1 rounded-full bg-white/10 hover:bg-white/20 text-gray-400 hover:text-white"
                    >
                      <X size={14} />
                    </motion.button>
                  )}
               </AnimatePresence>
            </motion.div>

            {!isSearchFocused && !searchQuery && (
               <div className="hidden md:flex items-center gap-2 text-[10px] font-mono text-gray-600 whitespace-nowrap">
                  <Brain size={12} className="text-emerald-500" />
                  LETA AI POWERED DISCOVERY MODE 
               </div>
            )}
         </div>
      </div>

      {/* AI RESULTS SECTION (DYNAMIC) */}
      <AnimatePresence>
        {(aiResults.length > 0 || isSearching) && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="px-8 py-10 bg-gradient-to-b from-emerald-500/5 to-transparent border-b border-white/5"
          >
            <div className="flex items-center gap-3 mb-6">
               <Sparkles className="text-emerald-400 animate-pulse" size={20} />
               <h3 className="text-sm font-black tracking-[0.3em] text-white uppercase flex items-center gap-2">
                 LETA AI DISCOVERY
                 <span className="text-[10px] text-emerald-500/60 ml-2 font-mono">Found {aiResults.length} statutory insights</span>
               </h3>
            </div>
            
            <div className="flex gap-4 overflow-x-auto no-scrollbar scroll-smooth pb-4">
              {isSearching ? (
                 [1, 2, 3, 4].map(i => (
                    <div key={i} className="flex-shrink-0 w-64 h-36 bg-emerald-500/5 rounded-xl animate-pulse border border-emerald-500/10" />
                 ))
              ) : (
                aiResults.map((doc) => (
                  <DocCard 
                    key={doc.id}
                    doc={doc}
                    accentColor="bg-emerald-500/20"
                    onClick={setSelectedDoc}
                    onDownload={handleDownload}
                  />
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* CONTENT ROWS */}
      <div className="py-10 space-y-4">
        {categoryGroups.map((group, idx) => (
          <div key={idx} className="mb-12">
            <div className="px-8 mb-8 flex items-center gap-4">
               <div className="h-[1px] flex-grow bg-white/5" />
               <span className="text-[10px] font-black text-gray-500 tracking-[0.5em] uppercase whitespace-nowrap">{group.title}</span>
               <div className="h-[1px] flex-grow bg-white/5" />
            </div>
            {group.rows.map((row) => (
              <DocumentRow 
                key={row.id} 
                category={row} 
                onDocClick={setSelectedDoc}
                onDownload={handleDownload}
              />
            ))}
          </div>
        ))}
      </div>

      {/* Sidebar Portal for Previews */}
      <DocPreviewSidebar 
        isOpen={!!selectedDoc} 
        docMetadata={selectedDoc} 
        onClose={() => setSelectedDoc(null)} 
        onDownload={handleDownload}
      />
    </div>
  );
};

export default DocumentLibrary;
