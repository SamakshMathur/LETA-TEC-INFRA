import React, { useState } from 'react';
import { X, ExternalLink, Minimize2, Maximize2, Download, FileText, ImageIcon, FileQuestion } from 'lucide-react';
import PDFViewer from './PDFViewer';

const DocumentViewer = ({ url, onClose, title = 'Document Viewer', initialPage, keyword }) => {
  const [isFullscreen, setIsFullscreen] = useState(false);

  if (!url) return null;

  // Determine file type from URL
  const getFileType = (url) => {
    const cleanUrl = url.split('?')[0].split('#')[0];
    const extension = cleanUrl.split('.').pop().toLowerCase();
    
    // Check filename param if it's an API route
    if (url.includes('filename=')) {
        const fileParam = new URLSearchParams(url.split('?')[1]).get('filename');
        if (fileParam) return fileParam.split('.').pop().toLowerCase();
    }
    
    return extension;
  };

  const fileType = getFileType(url);
  const isPDF = fileType === 'pdf';
  const isImage = ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(fileType);
  const isWord = ['doc', 'docx'].includes(fileType);

  return (
    <div className={`flex flex-col bg-[#F9FAFB] border-r border-leta-gray-200 relative shadow-2xl z-20 ${isFullscreen ? 'fixed inset-0 z-[10000]' : 'h-full'}`}>
      {/* Header */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-leta-gray-200 bg-[#FFFFFF]'>
         <div className='flex items-center gap-2 overflow-hidden'>
            <span className='text-xs font-mono font-bold text-sentinel-green uppercase tracking-wider whitespace-nowrap'>
              DOC_VIEWER :: {fileType.toUpperCase()}
            </span>
            <span className='text-leta-gray-500 text-xs truncate max-w-[200px]' title={title}>
               // {title}
            </span>
         </div>
         <div className='flex items-center gap-1'>
            <a 
              href={url} 
              target='_blank' 
              rel='noopener noreferrer'
              className='p-1.5 text-leta-gray-500 hover:text-leta-gray-900 hover:bg-leta-gray-50 rounded-leta transition-colors'
              title='Open / Download'
            >
               <Download size={14} />
            </a>
            <button 
              onClick={() => setIsFullscreen(!isFullscreen)}
              className='p-1.5 text-leta-gray-500 hover:text-leta-gray-900 hover:bg-leta-gray-50 rounded-leta transition-colors hidden lg:block'
            >
               {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
            <button 
              onClick={onClose}
              className='p-1.5 text-leta-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-leta transition-colors'
            >
               <X size={16} />
            </button>
         </div>
      </div>

      {/* Content Viewport */}
      <div className='flex-1 bg-[#111827] relative overflow-auto flex items-center justify-center custom-scrollbar'>
         {isPDF ? (
            <PDFViewer 
               url={url} 
               onClose={onClose} 
               title={title} 
               initialPage={initialPage} 
               keyword={keyword}
               embedded={true} // New prop to tell PDFViewer to hide its own header
            />
         ) : isImage ? (
            <div className="p-4 flex flex-col items-center">
                <img 
                    src={url} 
                    alt={title} 
                    className="max-w-full h-auto shadow-2xl border border-leta-gray-200"
                    onError={(e) => {
                        e.target.onerror = null; 
                        e.target.src = 'https://via.placeholder.com/400x300?text=Error+Loading+Image';
                    }}
                />
            </div>
         ) : (
            <div className="flex flex-col items-center text-center p-10 max-w-md mx-auto">
               <div className="p-6 bg-leta-gray-50 rounded-full mb-6">
                  {isWord ? <FileText size={48} className="text-leta-gray-900" /> : <FileQuestion size={48} className="text-leta-gray-500" />}
               </div>
               <h3 className="text-xl font-bold text-leta-gray-900 mb-2 font-mono uppercase">Preview Unavailable</h3>
               <p className="text-leta-gray-600 text-sm mb-8 font-mono leading-relaxed">
                  The {fileType.toUpperCase()} format does not support live browser preview in the console. 
                  Please download the file for full statutory analysis.
               </p>
               <a 
                  href={url} 
                  download 
                  className="px-8 py-3 bg-sentinel-blue/20 border border-sentinel-blue text-leta-gray-900 hover:bg-sentinel-blue hover:text-leta-gray-900 transition-all font-mono font-bold uppercase tracking-widest text-xs"
               >
                  [ DOWNLOAD_ORIGINAL_FILE ]
               </a>
            </div>
         )}
      </div>
      
      {/* Footer */}
      <div className='px-4 py-1.5 bg-[#05080B] border-t border-leta-gray-200 flex justify-between items-center text-[10px] font-mono text-leta-gray-600 uppercase'>
         <span>STATUS: {isPDF ? 'ADVANCED_READING_MODE' : 'RAW_FILE_INSPECTION'}</span>
         <span>SECURE_CONNECTION</span>
      </div>
    </div>
  );
};

export default DocumentViewer;
