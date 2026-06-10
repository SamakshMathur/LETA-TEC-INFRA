import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform } from 'framer-motion';
import {
  ChevronLeft, ChevronRight, Bookmark, Download,
  Search, X, Brain
} from 'lucide-react';
import DocPreviewSidebar from './DocPreviewSidebar';
import { BASE_URL as VITE_API_BASE } from '../../config/api';

import cx from 'classnames/bind';
import styles from './DocumentLibrary.module.css';

import {
  CATEGORY_GROUPS,
  FILTER_OPTIONS,
  TRENDING_SEARCHES,
  getDocumentContext
} from '../../constants/documentLibrary';

const cn = cx.bind(styles);

const API_BASE = `${VITE_API_BASE}/api/documents`;

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
  icon: React.ComponentType<{ size?: number; className?: string }>;
  colorClass: string;
  accentClass: string;
}

// ── 3D tilt wrapper ────────────────────────────────────────────────────────
const Card3D: React.FC<{ children: React.ReactNode; className: string; onClick?: () => void }> = ({ children, className, onClick }) => {
  const ref = useRef<HTMLDivElement>(null);
  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const rawGlowX = useMotionValue(50);
  const rawGlowY = useMotionValue(50);
  const rawScale = useMotionValue(1);
  const spring = { stiffness: 300, damping: 28, mass: 0.55 };
  const rotateX = useSpring(useTransform(rawY, [-0.5, 0.5], [8, -8]),  spring);
  const rotateY = useSpring(useTransform(rawX, [-0.5, 0.5], [-8, 8]),  spring);
  const scale   = useSpring(rawScale, { stiffness: 320, damping: 26 });
  const glowX   = useSpring(rawGlowX, { stiffness: 200, damping: 30 });
  const glowY   = useSpring(rawGlowY, { stiffness: 200, damping: 30 });
  const specular = useTransform([glowX, glowY] as any, ([x, y]: number[]) =>
    `radial-gradient(circle at ${x}% ${y}%, rgba(255,255,255,0.08) 0%, transparent 65%)`
  );
  return (
    <motion.div
      ref={ref}
      style={{ rotateX, rotateY, scale, transformStyle: 'preserve-3d', transformPerspective: 800, position: 'relative' }}
      onMouseMove={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        rawX.set((e.clientX - r.left) / r.width  - 0.5);
        rawY.set((e.clientY - r.top)  / r.height - 0.5);
        rawGlowX.set(((e.clientX - r.left) / r.width)  * 100);
        rawGlowY.set(((e.clientY - r.top)  / r.height) * 100);
      }}
      onMouseEnter={() => rawScale.set(1.04)}
      onMouseLeave={() => { rawX.set(0); rawY.set(0); rawGlowX.set(50); rawGlowY.set(50); rawScale.set(1); }}
      className={className}
      onClick={onClick}
    >
      {children}
      <motion.div style={{ background: specular, position: 'absolute', inset: 0, borderRadius: 'inherit', pointerEvents: 'none', zIndex: 10 }} />
    </motion.div>
  );
};

// ── Redesigned Card System (Matte, spacious, structured) ──────────────────
const DocCard: React.FC<{
  doc: DocItem;
  onClick: (d: DocItem) => void;
  onDownload: (d: DocItem) => void;
}> = ({ doc, onClick, onDownload }) => {
  const meta = getDocumentContext(doc.title);

  return (
    <Card3D
      className={cn('docCard')}
      onClick={() => onClick(doc)}
    >
      <div className={cn('cardContent')}>
        {/* Type & Action row */}
        <div className={cn('cardHeader')}>
          <span className={cn('cardType')}>
            {meta.type}
          </span>
          <div className={cn('cardActions')}>
            <button
              onClick={(e) => { e.stopPropagation(); onDownload(doc); }}
              className={cn('cardActionBtn')}
              title="Download Document"
            >
              <Download size={12} />
            </button>
            <button 
              onClick={(e) => { e.stopPropagation(); }}
              className={cn('cardActionBtn')}
              title="Save to Brief"
            >
              <Bookmark size={12} />
            </button>
          </div>
        </div>

        {/* Title */}
        <h4 className={cn('cardTitle')}>
          {doc.title.replace('.pdf', '')}
        </h4>

        {/* Summary Context */}
        <p className={cn('cardSummary')}>
          {meta.summary}
        </p>
      </div>

      <div className={cn('cardFooter')}>
        {/* Monospace section tags */}
        <div className={cn('cardTags')}>
          {meta.sections.map((sect, i) => (
            <span key={i} className={cn('cardTag')}>
              {sect}
            </span>
          ))}
        </div>

        {/* Footer info metrics */}
        <div className={cn('cardMeta')}>
          <span>{meta.authority}</span>
          <span>{meta.date}</span>
        </div>
      </div>
    </Card3D>
  );
};

// ── Redesigned Bottom Archive Row ──
const DocumentRow: React.FC<{
  category: CategoryRow;
  onDocClick: (d: DocItem) => void;
  onDownload: (d: DocItem) => void;
  searchQuery: string;
}> = ({ category, onDocClick, onDownload, searchQuery }) => {
  const [docs, setDocs]       = useState<DocItem[]>([]);
  const [loading, setLoading] = useState(true);
  const scrollRef             = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/list/${category.id}`)
      .then(r => r.json())
      .then(data => { setDocs(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [category.id]);

  const scroll = (dir: 'left' | 'right') => {
    if (!scrollRef.current) return;
    const { scrollLeft, clientWidth } = scrollRef.current;
    scrollRef.current.scrollTo({ 
      left: dir === 'left' ? scrollLeft - clientWidth / 2 : scrollLeft + clientWidth / 2, 
      behavior: 'smooth' 
    });
  };

  // Live filter the documents by searchQuery keyword
  const filteredDocs = searchQuery.trim() 
    ? docs.filter(doc => doc.title.toLowerCase().includes(searchQuery.toLowerCase()))
    : docs;

  if (!loading && filteredDocs.length === 0) return null;

  return (
    <div className={cn('documentRow')}>
      <div className={cn('rowHeader')}>
        <h3 className={cn('rowTitle')}>
          <category.icon size={14} className={cn(category.colorClass as any)} />
          {category.label}
          <span className={cn('rowCount')}>[{filteredDocs.length}]</span>
        </h3>
        <div className={cn('rowControls')}>
          <button 
            onClick={() => scroll('left')} 
            className={cn('scrollButton')}
          >
            <ChevronLeft size={13} />
          </button>
          <button 
            onClick={() => scroll('right')} 
            className={cn('scrollButton')}
          >
            <ChevronRight size={13} />
          </button>
        </div>
      </div>

      <div ref={scrollRef} className={cn('scrollContainer')}>
        {loading
          ? [1, 2, 3, 4].map(i => (
              <div 
                key={i} 
                className={cn('docCard')}
                style={{ background: 'rgba(15, 23, 34, 0.2)', opacity: 0.5, borderStyle: 'dashed' }} 
              />
            ))
          : filteredDocs.slice(0, 20).map(doc => (
              <DocCard key={doc.id} doc={doc} onClick={onDocClick} onDownload={onDownload} />
            ))
        }
      </div>
    </div>
  );
};

// ── Redesigned Core DocumentLibrary Component ─────────────────────────────
export const DocumentLibrary: React.FC = () => {
  const [selectedDoc, setSelectedDoc] = useState<DocItem | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [selectedFilter, setSelectedFilter] = useState('all');

  // All documents loaded once on mount for instant client-side search
  const [allDocs, setAllDocs] = useState<DocItem[]>([]);
  const [allDocsLoading, setAllDocsLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/list/all`)
      .then(r => r.json())
      .then(data => { setAllDocs(Array.isArray(data) ? data : []); setAllDocsLoading(false); })
      .catch(() => setAllDocsLoading(false));
  }, []);

  // Instant search — scored client-side, zero latency
  const instantResults = useMemo(() => {
    const q = searchQuery.trim();
    if (!q) return [];

    const lower = q.toLowerCase().replace(/[_+]/g, ' ');
    const words = lower.split(/\s+/).filter(w => w.length > 1);

    const scored = allDocs.map(doc => {
      const title    = (doc.title    || '').toLowerCase().replace(/[_.+]/g, ' ');
      const filename = (doc.filename || '').toLowerCase().replace(/[_.+]/g, ' ');
      const combined = title + ' ' + filename;

      if (combined.includes(lower))
        return { doc, score: 100 + (100 - Math.min(title.length, 100)) / 100 };
      if (words.length > 0 && words.every(w => combined.includes(w)))
        return { doc, score: 80 };
      const hits = words.filter(w => combined.includes(w)).length;
      return { doc, score: hits > 0 ? (hits / words.length) * 50 : 0 };
    }).filter(x => x.score > 0);

    scored.sort((a, b) => b.score - a.score);

    const filtered = selectedFilter === 'all' ? scored : scored.filter(({ doc }) => {
      const cat = doc.category || '';
      if (selectedFilter === 'rules')     return cat === 'acts'      || cat === 'rules';
      if (selectedFilter === 'circulars') return cat === 'circulars' || cat === 'cgst' || cat === 'igst';
      if (selectedFilter === 'case-laws') return cat === 'highcourt' || cat === 'supremecourt';
      if (selectedFilter === 'aar')       return cat === 'aars';
      if (selectedFilter === 'forms')     return cat === 'forms'     || cat === 'brochures' || cat === 'flyers';
      return true;
    });

    return filtered.slice(0, 60).map(x => x.doc);
  }, [searchQuery, allDocs, selectedFilter]);

  const handleDownload = (doc: DocItem) => {
    const category = doc.category || doc.id.split('_')[0];
    window.open(`${API_BASE}/view?category=${category}&filename=${encodeURIComponent(doc.filename)}`, '_blank');
  };

  const getFilteredCategoryGroups = () => {
    if (selectedFilter === 'all') return CATEGORY_GROUPS;
    
    return CATEGORY_GROUPS.map(group => {
      const filteredRows = group.rows.filter(row => {
        if (selectedFilter === 'rules') return row.id === 'acts' || row.id === 'rules';
        if (selectedFilter === 'circulars') return row.id === 'circulars' || row.id === 'cgst' || row.id === 'igst';
        if (selectedFilter === 'case-laws') return row.id === 'highcourt' || row.id === 'supremecourt';
        if (selectedFilter === 'aar') return row.id === 'aars';
        if (selectedFilter === 'forms') return row.id === 'forms' || row.id === 'brochures' || row.id === 'flyers';
        return true;
      });
      return { ...group, rows: filteredRows };
    }).filter(group => group.rows.length > 0);
  };

  // true when user has typed a search query
  const isSearching = searchQuery.trim().length > 0;

  return (
    <div className={cn('container')}>
      
      {/* ── 1. CORE SEARCH EXPERIENCE ────────────────── */}
      <div className={cn('searchSection')}>
        <div className={cn('searchContainer', { searchFocused: isSearchFocused })}>
          <Search className={cn('searchIcon', { searching: isSearching })} />
          <input
            type="text"
            value={searchQuery}
            onFocus={() => setIsSearchFocused(true)}
            onBlur={() => setTimeout(() => setIsSearchFocused(false), 200)}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search Rule 42 reversal circulars, ITC rulings, refund rejection precedents..."
            className={cn('searchInput')}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className={cn('clearSearchButton')}
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Suggested keywords beneath search */}
        <div className={cn('trendingSearches')}>
          <span className={cn('trendingLabel')}>
            <Brain size={11} className={cn('trendingIcon')} />
            Trending References:
          </span>
          {TRENDING_SEARCHES.map((term, i) => (
            <button
              key={i}
              onClick={() => setSearchQuery(term)}
              className={cn('trendingButton')}
            >
              "{term}"
            </button>
          ))}
        </div>
      </div>

      {/* ── 2. STATUTORY DOCUMENT FILTERS ──────────────────────────────────── */}
      <div className={cn('filtersWrapper')}>
        {FILTER_OPTIONS.map((opt) => {
          const isSelected = selectedFilter === opt.id;
          return (
            <button
              key={opt.id}
              onClick={() => setSelectedFilter(opt.id)}
              className={cn('filterButton', {
                filterButtonActive: isSelected,
                filterButtonInactive: !isSelected
              })}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* ── 3. INSTANT SEARCH RESULTS ─────────────────────────────────────── */}
      <AnimatePresence>
        {searchQuery.trim().length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.15 }}
            className={cn('aiResultsContainer')}
          >
            <div className={cn('aiResultsHeader')}>
              <Search className={cn('sparklesIcon')} size={16} />
              <div>
                <h3 className={cn('aiResultsTitle')}>
                  Document Search
                </h3>
                <p className={cn('aiResultsSubtitle')}>
                  {allDocsLoading
                    ? 'Loading document index…'
                    : instantResults.length > 0
                      ? `${instantResults.length} document${instantResults.length !== 1 ? 's' : ''} matched`
                      : `No documents found for "${searchQuery}"`}
                </p>
              </div>
            </div>

            {allDocsLoading ? (
              <div className={cn('aiResultsGrid')}>
                {[1, 2, 3].map(i => <div key={i} className={cn('aiLoadingCard')} />)}
              </div>
            ) : instantResults.length > 0 ? (
              <div className={cn('aiResultsGrid')}>
                {instantResults.map(doc => (
                  <DocCard key={doc.id} doc={doc} onClick={setSelectedDoc} onDownload={handleDownload} />
                ))}
              </div>
            ) : (
              <div className={cn('aiEmptyState')}>
                No documents matched "{searchQuery}". Try a shorter term or document number.
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── 5. CATEGORY ARCHIVE ROWS — hidden while searching ─────────────── */}
      {!searchQuery.trim() && (
        <div className={cn('archiveSection')}>
          {getFilteredCategoryGroups().map((group, idx) => (
            <div key={idx} style={{ marginBottom: '16px' }}>
              <div className={cn('archiveHeader')}>
                <span className={cn('archiveTitle')}>{group.title}</span>
                <div className={cn('archiveDivider')} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {group.rows.map(row => (
                  <DocumentRow key={row.id} category={row} onDocClick={setSelectedDoc} onDownload={handleDownload} searchQuery="" />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview sidebar slider panel */}
      <DocPreviewSidebar
        isOpen={!!selectedDoc}
        docMetadata={selectedDoc}
        onClose={() => setSelectedDoc(null)}
        onDownload={() => selectedDoc && handleDownload(selectedDoc)}
      />
    </div>
  );
};

export default DocumentLibrary;
