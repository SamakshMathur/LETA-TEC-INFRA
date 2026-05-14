import React from 'react';
import ReactDOM from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Download, FileText, ChevronRight } from 'lucide-react';
import { BASE_URL } from '../../config/api';

import cx from 'classnames/bind';
import styles from './DocPreviewSidebar.module.css';

const cn = cx.bind(styles);

interface DocMetadata {
  id: string;
  title: string;
  filename: string;
  size: string;
  path?: string;
  category?: string;
}

interface DocPreviewSidebarProps {
  isOpen: boolean;
  docMetadata: DocMetadata | null;
  onClose: () => void;
  onDownload?: () => void;
}

const DocPreviewSidebar: React.FC<DocPreviewSidebarProps> = ({ isOpen, docMetadata, onClose, onDownload }) => {
  if (!isOpen || !docMetadata) return null;

  return ReactDOM.createPortal(
    <AnimatePresence>
      <>
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className={cn('backdrop')}
        />

        {/* Sidebar */}
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          className={cn('sidebar')}
        >
          {/* Header */}
          <div className={cn('header')}>
            <div className={cn('headerLeft')}>
              <div className={cn('iconContainer')}>
                <FileText size={24} />
              </div>
              <div className={cn('titleContainer')}>
                <h3 className={cn('title')}>{docMetadata.title}</h3>
                <div className={cn('subtitle')}>
                  <span>{docMetadata.id.split('_')[0].toUpperCase()}</span>
                  <ChevronRight size={12} />
                  <span>{docMetadata.size}</span>
                </div>
              </div>
            </div>
            
            <div className={cn('headerRight')}>
              <button
                onClick={() => {
                  const category = docMetadata.category || docMetadata.id.split('_')[0];
                  window.open(`${BASE_URL}/api/documents/view?category=${category}&filename=${encodeURIComponent(docMetadata.filename)}&download=true`, '_blank');
                }}
                className={cn('downloadBtn')}
              >
                <Download size={14} />
                Download PDF
              </button>
              <button
                onClick={onClose}
                className={cn('closeBtn')}
              >
                <X size={20} />
              </button>
            </div>
          </div>

           <div className={cn('iframeContainer')}>
             <iframe 
               src={`${BASE_URL}/api/documents/view?category=${docMetadata.category || docMetadata.id.split('_')[0]}&filename=${encodeURIComponent(docMetadata.filename)}#toolbar=0`}
               className={cn('iframe')}
               title="PDF Preview"
             />
          </div>
          
          <div className={cn('footer')}>
              // PREVIEW_MODE_ACTIVE // {docMetadata.path}
          </div>
        </motion.div>
      </>
    </AnimatePresence>,
    document.body
  );
};

export default DocPreviewSidebar;
