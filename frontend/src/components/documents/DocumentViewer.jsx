import React, { useState, useEffect } from 'react';
import { X, Minimize2, Maximize2, Download, FileQuestion, Loader } from 'lucide-react';
import PDFViewer from './PDFViewer';

const getFileType = (url) => {
  if (!url) return '';

  // view_by_path?path=Act%2FCGST%20Act.pdf  →  extract from path= param
  if (url.includes('path=')) {
    try {
      const pathParam = new URLSearchParams(url.split('?')[1]).get('path');
      if (pathParam) {
        const ext = decodeURIComponent(pathParam).split('.').pop().toLowerCase();
        if (ext && ext.length <= 5) return ext;
      }
    } catch {
      // Malformed path= param — fall through to the next detection strategy.
    }
  }

  // view?category=all&filename=CGST%20Act.pdf  →  extract from filename= param
  if (url.includes('filename=')) {
    try {
      const fileParam = new URLSearchParams(url.split('?')[1]).get('filename');
      if (fileParam) return fileParam.split('.').pop().toLowerCase();
    } catch {
      // Malformed filename= param — fall through to the direct-URL check below.
    }
  }

  // Direct URL with extension
  const clean = url.split('?')[0].split('#')[0];
  const ext = clean.split('.').pop().toLowerCase();
  if (ext && ext.length <= 5 && ext !== clean) return ext;

  return '';
};

// Renders DOCX as HTML using mammoth (bundled via npm, no CDN)
const DocxViewer = ({ url }) => {
  const [html, setHtml]       = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    let cancelled = false;

    const render = async () => {
      setLoading(true);
      setError('');
      setHtml('');
      try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const arrayBuffer = await resp.arrayBuffer();

        const mammoth = (await import('mammoth')).default;
        const result = await mammoth.convertToHtml({ arrayBuffer });
        if (!cancelled) setHtml(result.value);
      } catch (e) {
        if (!cancelled) setError(e.message || 'Failed to render document');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    render();
    return () => { cancelled = true; };
  }, [url]);

  if (loading) return (
    <div className="flex flex-col items-center justify-center h-full gap-3 text-[#4FB7C5]">
      <Loader size={22} className="animate-spin" />
      <span className="text-[11px] font-mono uppercase tracking-widest">Rendering Document...</span>
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center justify-center h-full gap-3 p-8 text-center">
      <FileQuestion size={36} className="text-[#475569]" />
      <p className="text-[12px] font-mono text-[#6B7280]">Could not render document: {error}</p>
      <a href={url} download className="mt-2 px-4 py-2 text-[11px] font-mono uppercase tracking-widest border border-[#4FB7C5]/30 text-[#4FB7C5] hover:bg-[#4FB7C5]/10 transition-colors rounded">
        Download Instead
      </a>
    </div>
  );

  return (
    <div className="h-full overflow-auto bg-white">
      <div
        className="max-w-3xl mx-auto p-8 text-sm leading-relaxed"
        style={{ fontFamily: 'Georgia, serif', color: '#1a1a1a' }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
};

const DocumentViewer = ({ url, onClose, title = 'Document', initialPage, keyword }) => {
  const [isFullscreen, setIsFullscreen] = useState(false);

  if (!url) return null;

  const fileType = getFileType(url);
  const isPDF    = fileType === 'pdf';
  const isImage  = ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(fileType);
  const isDocx   = ['doc', 'docx'].includes(fileType);

  return (
    <div
      className={`flex flex-col relative shadow-2xl z-20 ${
        isFullscreen ? 'fixed inset-0 z-[10000]' : 'h-full'
      }`}
      style={{ background: '#0A0F1A' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-2.5 flex-shrink-0"
        style={{ borderBottom: '1px solid rgba(79,183,197,0.12)', background: '#080D15' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[9px] font-mono font-bold uppercase tracking-[0.2em] flex-shrink-0" style={{ color: '#4FB7C5' }}>
            {isPDF ? 'PDF' : isDocx ? 'DOCX' : isImage ? 'IMG' : fileType.toUpperCase() || 'DOC'}
          </span>
          <span className="text-[11px] font-mono truncate" style={{ color: '#6B7280' }} title={title}>
            {title}
          </span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded transition-colors"
            style={{ color: '#475569' }}
            onMouseEnter={e => e.currentTarget.style.color = '#CBD5E1'}
            onMouseLeave={e => e.currentTarget.style.color = '#475569'}
            title="Open / Download"
          >
            <Download size={13} />
          </a>
          <button
            onClick={() => setIsFullscreen(f => !f)}
            className="p-1.5 rounded transition-colors hidden lg:block"
            style={{ color: '#475569' }}
            onMouseEnter={e => e.currentTarget.style.color = '#CBD5E1'}
            onMouseLeave={e => e.currentTarget.style.color = '#475569'}
          >
            {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded transition-colors"
            style={{ color: '#475569' }}
            onMouseEnter={e => e.currentTarget.style.color = '#EF4444'}
            onMouseLeave={e => e.currentTarget.style.color = '#475569'}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden relative">
        {isPDF ? (
          <PDFViewer
            url={url}
            onClose={onClose}
            title={title}
            initialPage={initialPage}
            keyword={keyword}
            embedded={true}
          />
        ) : isImage ? (
          <div className="h-full overflow-auto flex items-center justify-center p-4">
            <img
              src={url}
              alt={title}
              className="max-w-full h-auto shadow-2xl"
              onError={e => { e.target.style.display = 'none'; }}
            />
          </div>
        ) : isDocx ? (
          <DocxViewer url={url} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-4 p-8 text-center">
            <FileQuestion size={40} style={{ color: '#475569' }} />
            <p className="text-[12px] font-mono" style={{ color: '#6B7280' }}>
              Preview not available for .{fileType || 'unknown'} files
            </p>
            <a
              href={url}
              download
              className="px-5 py-2 text-[11px] font-mono uppercase tracking-widest rounded-lg transition-colors"
              style={{ border: '1px solid rgba(79,183,197,0.3)', color: '#4FB7C5' }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(79,183,197,0.08)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              Download File
            </a>
          </div>
        )}
      </div>

      {/* Footer */}
      <div
        className="px-4 py-1 flex justify-between items-center text-[9px] font-mono uppercase tracking-widest flex-shrink-0"
        style={{ borderTop: '1px solid rgba(255,255,255,0.03)', color: '#2a3050', background: '#050810' }}
      >
        <span>LETA TEC · DOCUMENT VIEWER</span>
        <span>{isPDF ? 'PDF_RENDER' : isDocx ? 'DOCX_RENDER' : 'RAW'}</span>
      </div>
    </div>
  );
};

export default DocumentViewer;
