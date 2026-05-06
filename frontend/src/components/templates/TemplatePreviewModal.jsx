import React, { useState, useEffect } from 'react';
import { X, Loader2 } from 'lucide-react';
import { BASE_URL } from '../../config/api';

const TemplatePreviewModal = ({ templateId, onClose }) => {
  const [template, setTemplate] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchTemplate = async () => {
      try {
        const response = await fetch(`${BASE_URL}/api/templates/${templateId}`);
        const data = await response.json();
        setTemplate(data);
      } catch (error) {
        console.error("Failed to fetch template details:", error);
      } finally {
        setIsLoading(false);
      }
    };
    
    if (templateId) {
      fetchTemplate();
    }
  }, [templateId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-leta-black/80 backdrop-blur-sm p-4">
      <div className="bg-[#111] border border-leta-gray-700 w-full max-w-4xl h-[85vh] rounded-leta shadow-2xl flex flex-col relative animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-leta-gray-800">
          <h2 className="text-2xl font-bold text-leta-gray-100 pr-8 line-clamp-1">
            {isLoading ? 'Loading Template...' : template?.title}
          </h2>
          <button 
            onClick={onClose}
            className="absolute top-6 right-6 text-leta-gray-600 hover:text-leta-gray-900 bg-leta-gray-800 hover:bg-leta-gray-700 rounded-full p-2 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-8 bg-leta-white text-leta-gray-900 font-serif leading-relaxed">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-full">
              <Loader2 className="animate-spin text-leta-gray-500 w-12 h-12 mb-4" />
              <p className="text-leta-gray-500">Retrieving full document...</p>
            </div>
          ) : (
            <div className="whitespace-pre-wrap max-w-3xl mx-auto shadow-sm p-8 bg-[#fafafa] border border-leta-gray-200">
              {template?.content || "No content available for this template."}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-leta-gray-800 bg-[#0a0a0a] flex justify-end gap-4 rounded-leta-b-lg">
          <button 
            onClick={onClose}
            className="px-6 py-2 text-leta-gray-300 hover:text-leta-gray-900 transition-colors"
          >
            Close
          </button>
          <a 
            href={`${BASE_URL}/api/templates/${template?.id}/download`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-2 border border-leta-gray-600 text-leta-gray-200 rounded-leta hover:bg-leta-gray-800 transition-colors flex items-center gap-2"
          >
            Download Original
          </a>
          <a 
            href={`/gst/templates/${template?.id}/customize`}
            className="px-6 py-2 bg-sentinel-green text-leta-black font-bold rounded-leta shadow hover:bg-teal-400 transition-colors pointer-events-auto"
          >
            Customize with AI
          </a>
        </div>
        
      </div>
    </div>
  );
};

export default TemplatePreviewModal;
