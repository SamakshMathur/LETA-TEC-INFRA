import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileText, Layers, BookOpen, Gavel, Book, Scroll, Globe,
  ChevronLeft, ChevronRight, Bookmark, Download, Info,
  Search, Sparkles, X, Brain,
} from 'lucide-react';
import DocPreviewSidebar from './DocPreviewSidebar';
import { BASE_URL as VITE_API_BASE } from '../../config/api';

const API_BASE = `${VITE_API_BASE}/api/documents`;

const categoryGroups = [
  {
    title: 'GST STATUTORY ARCHIVES',
    rows: [
      { id: 'circulars',    label: 'Circulars & Notifications',   icon: Layers,   color: 'text-purple-400',  accent: 'bg-purple-500/20' },
      { id: 'aars',         label: 'Advance Rulings (AAR)',        icon: Gavel,    color: 'text-rose-400',    accent: 'bg-rose-500/20'   },
      { id: 'highcourt',    label: 'High Court Case Laws',         icon: Book,     color: 'text-amber-400',   accent: 'bg-amber-500/20'  },
      { id: 'supremecourt', label: 'Supreme Court Case Laws',      icon: Gavel,    color: 'text-violet-400',  accent: 'bg-violet-500/20' },
    ],
  },
  {
    title: 'OPERATIONAL RESOURCES',
    rows: [
      { id: 'forms',     label: 'Statutory Forms',    icon: FileText, color: 'text-blue-400',   accent: 'bg-blue-500/20'   },
      { id: 'brochures', label: 'Official Brochures', icon: BookOpen, color: 'text-purple-400', accent: 'bg-purple-500/20' },
      { id: 'flyers',    label: 'Information Flyers', icon: Info,     color: 'text-cyan-400',   accent: 'bg-cyan-500/20'   },
    ],
  },
  {
    title: 'ACTS & FRAMEWORKS',
    rows: [
      { id: 'acts',  label: 'The GST Acts',          icon: Book,    color: 'text-orange-400', accent: 'bg-orange-500/20' },
      { id: 'rules', label: 'Statutory Rules',        icon: Scroll,  color: 'text-yellow-400', accent: 'bg-yellow-500/20' },
      { id: 'cgst',  label: 'CGST Notifications',    icon: FileText, color: 'text-indigo-400', accent: 'bg-indigo-500/20' },
      { id: 'igst',  label: 'IGST Notifications',    icon: Globe,   color: 'text-cyan-400',   accent: 'bg-cyan-500/20'   },
    ],
  },
];

interface DocItem {
  id: string;
  title: string;
  filename: string;
  size: string;
  path?: string;
  category?: string;
}

interface CategoryRow {
  id: string;
  label: string;
  icon: React.ElementType;
  color: string;
  accent: string;
}

// ── Doc Card ──────────────────────────────────────────────────────────────────
const DocCard: React.FC<{
  doc: DocItem;
  onClick: (d: DocItem) => void;
  onDownload: (d: DocItem) => void;
  accentColor: string;
}> = ({ doc, onClick, onDownload, accentColor }) => (
  <motion.div
    whileHover={{ scale: 1.04, zIndex: 10 }}
    className="relative flex-shrink-0 w-64 h-36 rounded-2xl border border-white/5 overflow-hidden group cursor-pointer transition-all duration-300 hover:shadow-purple hover:border-white/15"
    style={{ background: 'rgba(255,255,255,0.04)', backdropFilter: 'blur(12px)' }}
    onClick={() => onClick(doc)}
  >
    {/* Purple glow on hover */}
    <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none rounded-2xl"
      style={{ boxShadow: 'inset 0 0 30px rgba(168,85,247,0.08)' }} />

    <div className="absolute inset-0 p-4 flex flex-col justify-between">
      <div className="flex justify-between items-start">
        <div className={`p-2 rounded-xl ${accentColor}`}>
          <FileText size={16} className="text-white/80" />
        </div>
        <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => { e.stopPropagation(); onDownload(doc); }}
            className="p-1.5 rounded-full bg-white/8 hover:bg-purple-500/20 text-white/50 hover:text-purple-400 transition-all"
          >
            <Download size={13} />
          </button>
          <button className="p-1.5 rounded-full bg-white/8 hover:bg-blue-500/20 text-white/50 hover:text-blue-400 transition-all">
            <Bookmark size={13} />
          </button>
        </div>
      </div>

      <div>
        <h4 className="text-xs font-bold text-white/80 line-clamp-2 leading-tight group-hover:text-purple-300 transition-colors uppercase tracking-tight">
          {doc.title.replace('.pdf', '')}
        </h4>
        <div className="flex items-center gap-2 mt-2">
          <span className="text-[9px] font-black text-white/30 px-1.5 py-0.5 rounded bg-white/5 border border-white/8">PDF</span>
          <span className="text-[9px] text-white/30 font-mono tracking-tighter uppercase">{doc.size}</span>
        </div>
      </div>
    </div>

    <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
  </motion.div>
);

// ── Document Row ──────────────────────────────────────────────────────────────
const DocumentRow: React.FC<{
  category: CategoryRow;
  onDocClick: (d: DocItem) => void;
  onDownload: (d: DocItem) => void;
}> = ({ category, onDocClick, onDownload }) => {
  const [docs, setDocs]       = useState<DocItem[]>([]);
  const [loading, setLoading] = useState(true);
  const scrollRef             = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/list/${category.id}`)
      .then(r => r.json())
      .then(data => { setDocs(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [category.id]);

  const scroll = (dir: 'left' | 'right') => {
    if (!scrollRef.current) return;
    const { scrollLeft, clientWidth } = scrollRef.current;
    scrollRef.current.scrollTo({ left: dir === 'left' ? scrollLeft - clientWidth / 2 : scrollLeft + clientWidth / 2, behavior: 'smooth' });
  };

  if (!loading && docs.length === 0) return null;

  return (
    <div className="mb-10 group/row">
      <div className="flex items-center justify-between px-8 mb-4">
        <h3 className="text-sm font-black tracking-[0.2em] text-white/40 uppercase flex items-center gap-3">
          <category.icon size={15} className={category.color} />
          {category.label}
          <span className="text-[10px] text-white/20 font-mono">[{docs.length}]</span>
        </h3>
        <div className="flex gap-2 opacity-0 group-hover/row:opacity-100 transition-opacity">
          <button onClick={() => scroll('left')} className="p-2 rounded-full bg-white/5 border border-white/8 text-white/40 hover:text-white hover:border-white/20 transition-all">
            <ChevronLeft size={15} />
          </button>
          <button onClick={() => scroll('right')} className="p-2 rounded-full bg-white/5 border border-white/8 text-white/40 hover:text-white hover:border-white/20 transition-all">
            <ChevronRight size={15} />
          </button>
        </div>
      </div>

      <div ref={scrollRef} className="flex gap-4 overflow-x-auto px-8 no-scrollbar scroll-smooth">
        {loading
          ? [1, 2, 3, 4].map(i => (
              <div key={i} className="flex-shrink-0 w-64 h-36 rounded-2xl animate-pulse border border-white/5"
                style={{ background: 'rgba(168,85,247,0.04)' }} />
            ))
          : docs.slice(0, 20).map(doc => (
              <DocCard key={doc.id} doc={doc} onClick={onDocClick} onDownload={onDownload} accentColor={category.accent} />
            ))
        }
      </div>
    </div>
  );
};

// ── DocumentLibrary ───────────────────────────────────────────────────────────
const DocumentLibrary: React.FC = () => {
  const [selectedDoc,    setSelectedDoc]    = useState<DocItem | null>(null);
  const [searchQuery,    setSearchQuery]    = useState('');
  const [isSearchFocused,setIsSearchFocused]= useState(false);
  const [aiResults,      setAiResults]      = useState<DocItem[]>([]);
  const [isSearching,    setIsSearching]    = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (searchQuery.trim().length < 3) { setAiResults([]); return; }
    const timer = setTimeout(() => {
      setIsSearching(true);
      fetch(`${VITE_API_BASE}/api/documents/ai_search?query=${encodeURIComponent(searchQuery)}`)
        .then(r => r.json())
        .then(data => { setAiResults(data); setIsSearching(false); })
        .catch(() => setIsSearching(false));
    }, 500);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleDownload = (doc: DocItem) => {
    const category = doc.category || doc.id.split('_')[0];
    window.open(`${API_BASE}/view?category=${category}&filename=${encodeURIComponent(doc.filename)}`, '_blank');
  };

  return (
    <div className="relative rounded-3xl overflow-hidden border border-white/5 mt-12 mb-20 pb-20"
      style={{ background: 'rgba(6,8,22,0.95)', backdropFilter: 'blur(20px)' }}>

      {/* Ambient glows */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full -translate-y-1/2 translate-x-1/2 pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(168,85,247,0.07) 0%, transparent 70%)', filter: 'blur(60px)' }} />
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] rounded-full translate-y-1/2 -translate-x-1/2 pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(96,165,250,0.05) 0%, transparent 70%)', filter: 'blur(60px)' }} />

      {/* Header */}
      <div className="px-8 py-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 border-b border-white/5"
        style={{ background: 'linear-gradient(180deg, rgba(168,85,247,0.05) 0%, transparent 100%)' }}>
        <div>
          <h2 className="text-2xl font-display font-bold text-white tracking-tight flex items-center gap-4">
            <BookOpen className="text-purple-400" size={28} />
            DOC_LIBRARY_V1.0
          </h2>
          <p className="text-xs text-white/30 font-mono mt-2 tracking-widest uppercase">
            // STATUS: <span className="text-purple-400">ACTIVE</span> // ENCRYPTION: <span className="text-purple-400">AES_256</span>
          </p>
        </div>
        <div className="flex gap-3">
          <button className="px-5 py-2.5 rounded-xl text-xs font-bold text-white/70 hover:text-white transition-all flex items-center gap-2 border border-white/10 hover:border-purple-500/30"
            style={{ background: 'rgba(255,255,255,0.04)' }}>
            <Layers size={13} />
            All Notifications
          </button>
          <button className="px-5 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest text-white transition-all flex items-center gap-2"
            style={{ background: 'linear-gradient(135deg,#7C3AED,#5B21B6)', boxShadow: '0 0 20px rgba(124,58,237,0.35)' }}>
            <Download size={13} />
            Bulk Export
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="px-8 py-5 sticky top-0 z-40 border-b border-white/5"
        style={{ background: 'rgba(6,8,22,0.85)', backdropFilter: 'blur(20px)' }}>
        <div className="flex items-center justify-between gap-4">
          <motion.div
            ref={searchRef}
            initial={false}
            animate={{ width: isSearchFocused || searchQuery ? '100%' : '320px' }}
            className="relative flex items-center"
          >
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <Search className={`h-4 w-4 transition-colors ${isSearching ? 'animate-spin text-purple-400' : 'text-white/30'}`} />
            </div>
            <input
              type="text"
              value={searchQuery}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => !searchQuery && setIsSearchFocused(false)}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="SEARCH STATUTES, CASE LAWS, CIRCULARS..."
              className="block w-full rounded-xl py-3 pl-11 pr-10 text-xs font-mono text-white placeholder-white/20 outline-none transition-all border"
              style={{
                background: 'rgba(255,255,255,0.04)',
                borderColor: isSearchFocused ? 'rgba(168,85,247,0.5)' : 'rgba(255,255,255,0.08)',
                boxShadow: isSearchFocused ? '0 0 15px rgba(168,85,247,0.15)' : 'none',
              }}
            />
            <AnimatePresence>
              {searchQuery && (
                <motion.button
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 p-1 rounded-full bg-white/8 hover:bg-white/15 text-white/40 hover:text-white transition-all"
                >
                  <X size={13} />
                </motion.button>
              )}
            </AnimatePresence>
          </motion.div>

          {!isSearchFocused && !searchQuery && (
            <div className="hidden md:flex items-center gap-2 text-[10px] font-mono text-white/25 whitespace-nowrap">
              <Brain size={11} className="text-purple-500" />
              LETA AI POWERED DISCOVERY MODE
            </div>
          )}
        </div>
      </div>

      {/* AI Results */}
      <AnimatePresence>
        {(aiResults.length > 0 || isSearching) && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="px-8 py-10 border-b border-white/5"
            style={{ background: 'linear-gradient(180deg, rgba(168,85,247,0.04) 0%, transparent 100%)' }}
          >
            <div className="flex items-center gap-3 mb-6">
              <Sparkles className="text-purple-400 animate-pulse" size={18} />
              <h3 className="text-sm font-black tracking-[0.3em] text-white uppercase flex items-center gap-2">
                LETA AI DISCOVERY
                <span className="text-[10px] text-purple-400/50 ml-2 font-mono">Found {aiResults.length} statutory insights</span>
              </h3>
            </div>
            <div className="flex gap-4 overflow-x-auto no-scrollbar scroll-smooth pb-4">
              {isSearching
                ? [1,2,3,4].map(i => (
                    <div key={i} className="flex-shrink-0 w-64 h-36 rounded-2xl animate-pulse border border-purple-500/10"
                      style={{ background: 'rgba(168,85,247,0.04)' }} />
                  ))
                : aiResults.map(doc => (
                    <DocCard key={doc.id} doc={doc} accentColor="bg-purple-500/20" onClick={setSelectedDoc} onDownload={handleDownload} />
                  ))
              }
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Category rows */}
      <div className="py-10 space-y-4">
        {categoryGroups.map((group, idx) => (
          <div key={idx} className="mb-12">
            <div className="px-8 mb-8 flex items-center gap-4">
              <div className="h-px flex-grow" style={{ background: 'rgba(168,85,247,0.12)' }} />
              <span className="text-[10px] font-black text-white/25 tracking-[0.5em] uppercase whitespace-nowrap">{group.title}</span>
              <div className="h-px flex-grow" style={{ background: 'rgba(168,85,247,0.12)' }} />
            </div>
            {group.rows.map(row => (
              <DocumentRow key={row.id} category={row} onDocClick={setSelectedDoc} onDownload={handleDownload} />
            ))}
          </div>
        ))}
      </div>

      {/* Sidebar preview portal */}
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
