import React, { useState, useEffect } from 'react';
import { X, ExternalLink, Minimize2, Maximize2 } from 'lucide-react';
import { Worker, Viewer } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import { searchPlugin } from '@react-pdf-viewer/search';

import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';
import '@react-pdf-viewer/search/lib/styles/index.css';

const PDFViewer = ({ url, onClose, title = 'Document Viewer', initialPage, keyword }) => {
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Initialize plugins
  const defaultLayoutPluginInstance = defaultLayoutPlugin({
    sidebarTabs: () => [], // hide default sidebar for cleaner look
  });
  
  const searchPluginInstance = searchPlugin({
    keyword: keyword ? [keyword] : [],
  });
  
  const { highlight } = searchPluginInstance;

  // Whenever the keyword prop changes, trigger a robust highlight pass
  useEffect(() => {
    if (keyword) {
       // A small timeout ensures the page is rendered before highlighting
       setTimeout(() => {
          highlight({
             keyword: keyword,
             matchCase: false,
          });
       }, 500);
    }
  }, [keyword, highlight]);

  if (!url) return null;

  return (
    <div className={`flex flex-col bg-[#050A10] border-r border-white/10 relative shadow-2xl z-20 ${isFullscreen ? 'fixed inset-0 z-[10000]' : 'h-full'}`}>
      <div className='flex items-center justify-between px-4 py-3 border-b border-white/10 bg-[#020202]'>
         <div className='flex items-center gap-2 overflow-hidden'>
            <span className='text-xs font-mono font-bold text-sentinel-green uppercase tracking-wider whitespace-nowrap'>
              DOC_VIEWER
            </span>
            <span className='text-gray-500 text-xs truncate max-w-[200px]' title={title}>
               // {title}
            </span>
         </div>
         <div className='flex items-center gap-1'>
            <a 
              href={url} 
              target='_blank' 
              rel='noopener noreferrer'
              className='p-1.5 text-gray-500 hover:text-white hover:bg-white/5 rounded transition-colors'
              title='Open in New Tab'
            >
               <ExternalLink size={14} />
            </a>
            <button 
              onClick={() => setIsFullscreen(!isFullscreen)}
              className='p-1.5 text-gray-500 hover:text-white hover:bg-white/5 rounded transition-colors hidden lg:block'
              title='Toggle Fullscreen'
            >
               {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
            <button 
              onClick={onClose}
              className='p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors'
              title='Close Viewer'
            >
               <X size={16} />
            </button>
         </div>
      </div>

      <div className='flex-1 bg-[#1A1A1A] relative custom-pdf-viewer-container overflow-hidden'>
         <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.worker.min.js">
           <Viewer 
             fileUrl={url} 
             plugins={[defaultLayoutPluginInstance, searchPluginInstance]} 
             initialPage={initialPage ? parseInt(initialPage) - 1 : 0} // PDF pages are 0-indexed
             theme="dark"
           />
         </Worker>
      </div>
      
      <div className='px-4 py-1.5 bg-[#05080B] border-t border-white/10 flex justify-between items-center text-[10px] font-mono text-gray-600 uppercase'>
         <span>STATUS: ADVANCED_READING_MODE</span>
         <span>SECURE_CONNECTION</span>
      </div>
    </div>
  );
};

export default PDFViewer;