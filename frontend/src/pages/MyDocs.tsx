import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bookmark, Download, Trash2, BookOpen, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useSavedDocs, SavedDoc } from '../hooks/useSavedDocs';
import { getDocumentContext } from '../constants/documentLibrary';
import { BASE_URL as VITE_API_BASE } from '../config/api';
import { DocPreviewSidebar } from '../components/documents';

const API_BASE = `${VITE_API_BASE}/api/documents`;

const SavedDocCard: React.FC<{
  doc: SavedDoc;
  onRemove: (doc: SavedDoc) => void;
  onPreview: (doc: SavedDoc) => void;
}> = ({ doc, onRemove, onPreview }) => {
  const meta = getDocumentContext(doc.title);

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    const category = doc.category || doc.id.split('_')[0];
    window.open(`${API_BASE}/view?category=${category}&filename=${encodeURIComponent(doc.filename)}`, '_blank');
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.94 }}
      transition={{ duration: 0.18 }}
      onClick={() => onPreview(doc)}
      className="rounded-xl cursor-pointer group relative flex flex-col gap-3 p-4 transition-all duration-200"
      style={{
        background: '#0A0F18',
        border: '1px solid rgba(79,183,197,0.08)',
      }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(79,183,197,0.22)'; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(79,183,197,0.08)'; }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span
          className="text-[10px] font-mono font-bold uppercase tracking-widest px-2 py-0.5 rounded"
          style={{ background: 'rgba(79,183,197,0.08)', color: '#4FB7C5', border: '1px solid rgba(79,183,197,0.2)' }}
        >
          {meta.type}
        </span>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={handleDownload}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: '#6B7280' }}
            onMouseEnter={e => { e.currentTarget.style.color = '#A7B3C2'; }}
            onMouseLeave={e => { e.currentTarget.style.color = '#6B7280'; }}
            title="Download"
          >
            <Download size={13} />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onRemove(doc); }}
            className="p-1.5 rounded-lg transition-colors"
            style={{ color: '#6B7280' }}
            onMouseEnter={e => { e.currentTarget.style.color = '#EF4444'; }}
            onMouseLeave={e => { e.currentTarget.style.color = '#6B7280'; }}
            title="Remove from My Docs"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {/* Title */}
      <h4 className="text-sm font-semibold leading-snug text-white">
        {doc.title.replace('.pdf', '')}
      </h4>

      {/* Summary */}
      <p className="text-xs leading-relaxed flex-1" style={{ color: '#6B7280' }}>
        {meta.summary}
      </p>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5">
        {meta.sections.map((s, i) => (
          <span
            key={i}
            className="text-[10px] font-mono px-2 py-0.5 rounded"
            style={{ background: 'rgba(255,255,255,0.04)', color: '#6B7280', border: '1px solid rgba(255,255,255,0.06)' }}
          >
            {s}
          </span>
        ))}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-1" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <span className="text-[10px] font-mono" style={{ color: '#4B5563' }}>{meta.authority}</span>
        <span className="text-[10px] font-mono" style={{ color: '#4B5563' }}>{meta.date}</span>
      </div>

      {/* Saved indicator */}
      <Bookmark
        size={11}
        fill="#4FB7C5"
        className="absolute top-3 right-3 opacity-20 group-hover:opacity-0 transition-opacity"
        style={{ color: '#4FB7C5' }}
      />
    </motion.div>
  );
};

const MyDocs: React.FC = () => {
  const { saved, toggle, clear } = useSavedDocs();
  const [selectedDoc, setSelectedDoc] = useState<SavedDoc | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const handleDownloadSelected = () => {
    if (!selectedDoc) return;
    const category = selectedDoc.category || selectedDoc.id.split('_')[0];
    window.open(`${API_BASE}/view?category=${category}&filename=${encodeURIComponent(selectedDoc.filename)}`, '_blank');
  };

  return (
    <div className="min-h-screen bg-[#000000]">

      {/* Header */}
      <div className="pt-[140px] pb-12 px-4 sm:px-6 bg-[#0F1722] border-b border-white/[0.04]">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-end justify-between gap-4 flex-wrap">
            <div>
              <div
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-4 font-mono text-[10px] uppercase tracking-widest"
                style={{ background: 'rgba(79,183,197,0.08)', border: '1px solid rgba(79,183,197,0.2)', color: '#4FB7C5' }}
              >
                <Bookmark size={11} fill="#4FB7C5" />
                Saved Collection
              </div>
              <h1 className="font-display font-bold text-3xl md:text-4xl text-white uppercase tracking-tight">
                My Docs
              </h1>
              <p className="text-sm font-light mt-2" style={{ color: '#A7B3C2' }}>
                {saved.length === 0
                  ? 'No documents saved yet. Bookmark any document from the library.'
                  : `${saved.length} document${saved.length !== 1 ? 's' : ''} saved to your collection`}
              </p>
            </div>

            {saved.length > 0 && (
              <div className="flex items-center gap-3">
                <AnimatePresence>
                  {showClearConfirm ? (
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      className="flex items-center gap-2"
                    >
                      <span className="text-xs font-mono" style={{ color: '#A7B3C2' }}>Clear all?</span>
                      <button
                        onClick={() => { clear(); setShowClearConfirm(false); }}
                        className="px-3 py-1.5 rounded-lg text-xs font-mono transition-colors"
                        style={{ background: 'rgba(239,68,68,0.1)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.3)' }}
                      >
                        Yes, clear
                      </button>
                      <button
                        onClick={() => setShowClearConfirm(false)}
                        className="p-1.5 rounded-lg"
                        style={{ color: '#6B7280' }}
                      >
                        <X size={14} />
                      </button>
                    </motion.div>
                  ) : (
                    <button
                      onClick={() => setShowClearConfirm(true)}
                      className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono transition-all"
                      style={{ color: '#6B7280', border: '1px solid rgba(255,255,255,0.08)' }}
                      onMouseEnter={e => { e.currentTarget.style.color = '#EF4444'; e.currentTarget.style.borderColor = 'rgba(239,68,68,0.3)'; }}
                      onMouseLeave={e => { e.currentTarget.style.color = '#6B7280'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; }}
                    >
                      <Trash2 size={12} />
                      Clear All
                    </button>
                  )}
                </AnimatePresence>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        {saved.length === 0 ? (
          /* Empty state */
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center py-24 text-center"
          >
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6"
              style={{ background: 'rgba(79,183,197,0.06)', border: '1px solid rgba(79,183,197,0.12)' }}
            >
              <BookOpen size={24} style={{ color: 'rgba(79,183,197,0.4)' }} />
            </div>
            <h3 className="font-display font-semibold text-lg text-white mb-2">No saved documents</h3>
            <p className="text-sm max-w-xs leading-relaxed mb-8" style={{ color: '#6B7280' }}>
              Browse the document library and click the bookmark icon on any document to save it here.
            </p>
            <Link
              to="/docs"
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-mono transition-all"
              style={{
                background: 'rgba(79,183,197,0.08)',
                color: '#4FB7C5',
                border: '1px solid rgba(79,183,197,0.25)',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(79,183,197,0.14)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'rgba(79,183,197,0.08)'; }}
            >
              <BookOpen size={14} />
              Browse Document Library
            </Link>
          </motion.div>
        ) : (
          <motion.div
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
            layout
          >
            <AnimatePresence>
              {saved.map(doc => (
                <SavedDocCard
                  key={doc.id}
                  doc={doc}
                  onRemove={toggle}
                  onPreview={setSelectedDoc}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </div>

      {/* Preview sidebar — reuse the same component */}
      <DocPreviewSidebar
        isOpen={!!selectedDoc}
        docMetadata={selectedDoc}
        onClose={() => setSelectedDoc(null)}
        onDownload={handleDownloadSelected}
      />
    </div>
  );
};

export default MyDocs;
