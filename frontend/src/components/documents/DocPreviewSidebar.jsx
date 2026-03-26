import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Download, FileText, ChevronRight } from 'lucide-react';
import { BASE_URL } from '../../config/api';

const DocPreviewSidebar = ({ isOpen, document, onClose, onDownload }) => {
  return (
    <AnimatePresence>
      {isOpen && document && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 transition-opacity"
          />

          {/* Sidebar */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 bottom-0 w-3/4 bg-[#050A10] border-l border-white/10 z-50 flex flex-col shadow-2xl shadow-black/80"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-white/10 bg-[#081018]">
              <div className="flex items-start gap-4">
                <div className="p-3 rounded-sm bg-sentinel-blue/10 text-sentinel-blue">
                  <FileText size={24} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white font-mono leading-tight">{document.title}</h3>
                  <div className="flex items-center gap-2 mt-2 text-xs font-mono text-gray-500">
                    <span>{document.id.split('_')[0].toUpperCase()}</span>
                    <ChevronRight size={12} />
                    <span>{document.size}</span>
                  </div>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    const category = document.category || document.id.split('_')[0];
                    window.open(`${BASE_URL}/api/documents/view?category=${category}&filename=${encodeURIComponent(document.filename)}&download=true`, '_blank');
                  }}
                  className="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-sm transition-all font-mono text-xs uppercase tracking-wider"
                >
                  <Download size={14} />
                  Download PDF
                </button>
                <button
                  onClick={onClose}
                  className="p-2 text-gray-500 hover:text-white hover:bg-white/5 rounded-sm transition-colors"
                >
                  <X size={20} />
                </button>
              </div>
            </div>

             <div className="flex-1 overflow-hidden bg-[#0A1420] p-0 relative">
               <iframe 
                 src={`${BASE_URL}/api/documents/view?category=${document.category || document.id.split('_')[0]}&filename=${encodeURIComponent(document.filename)}#toolbar=0`}
                 className="w-full h-full border-none bg-white"
                 title="PDF Preview"
               />
               
               {/* Overlay for non-previewable files or while loading could go here */}
            </div>
            
            <div className="p-2 bg-[#020202] border-t border-white/10 text-center text-[10px] text-gray-600 font-mono">
                // PREVIEW_MODE_ACTIVE // {document.path}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default DocPreviewSidebar;
