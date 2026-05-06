import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, FileText, CheckCircle, AlertCircle, Trash2, Edit3, Loader } from 'lucide-react';
import { BASE_URL } from '../config/api';

const AdminTemplateDashboard: React.FC = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadResults, setUploadResults] = useState<any>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    // Append new files to existing state
    setFiles(prev => [...prev, ...acceptedFiles]);
    setUploadResults(null); 
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png']
    }
  });

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleBulkUpload = async () => {
    if (files.length === 0) return;
    setIsUploading(true);
    setUploadResults(null);

    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    try {
      const baseUrl = BASE_URL;
      const response = await fetch(`${baseUrl}/api/templates/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Upload failed. Server responded with an error.");
      }

      const data = await response.json();
      setUploadResults(data);
      if (data.successful > 0) {
          setFiles([]); // Clear success
      }
    } catch (error: any) {
      console.error("Bulk upload error:", error);
      setUploadResults({ failed: files.length, successful: 0, errors: [error.message] });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#FFFFFF] text-leta-gray-200 pt-32 pb-12 px-4 sm:px-6 lg:px-8 mt-4">
      <div className="max-w-7xl mx-auto space-y-12">
        
        {/* Header Section */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl md:text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-sentinel-green via-teal-400 to-emerald-300 tracking-tight">
            Template Intelligence Portal
          </h1>
          <p className="text-xl text-leta-gray-600 max-w-2xl mx-auto">
            Bulk ingest legal frameworks, parse semantics, and vector-index templates into the main database.
          </p>
        </div>

        {/* Upload Interface */}
        <div className="bg-[#0a0a0a] border border-sentinel-green/20 rounded-2xl shadow-2xl p-8 backdrop-blur-sm">
          <h2 className="text-2xl font-bold text-leta-gray-900 mb-6 flex items-center">
            <UploadCloud className="mr-3 text-sentinel-green" size={28} />
            Bulk Ingestion Zone
          </h2>
          
          <div 
            {...getRootProps()} 
            className={`
              mt-2 flex justify-center rounded-leta border-2 border-dashed px-6 py-20 transition-all duration-300 ease-in-out cursor-pointer
              ${isDragActive 
                ? 'border-sentinel-green bg-sentinel-green/10 scale-[1.02]' 
                : 'border-leta-gray-200 hover:border-sentinel-green/50 hover:bg-leta-white/[0.02]'
              }
            `}
          >
            <div className="text-center">
              <input {...getInputProps()} />
              <UploadCloud className="mx-auto h-16 w-16 text-sentinel-green/70 mb-4 animate-pulse" aria-hidden="true" />
              <div className="mt-4 flex text-lg leading-6 text-leta-gray-600 justify-center">
                <span className="relative font-semibold text-sentinel-green hover:text-emerald-400 focus-within:outline-none focus-within:ring-2 focus-within:ring-sentinel-green focus-within:ring-offset-2 focus-within:ring-offset-gray-900 rounded-leta">
                  <span>Click to select files</span>
                </span>
                <p className="pl-2">or drag and drop</p>
              </div>
              <p className="text-sm leading-5 text-leta-gray-500 mt-2">
                PDF, DOCX, TXT, PNG, JPG (500+ files supported simultaneously)
              </p>
            </div>
          </div>

          {/* Staged Files List */}
          {files.length > 0 && (
            <div className="mt-10">
              <h3 className="text-lg font-medium text-leta-gray-900 flex items-center justify-between border-b border-leta-gray-200 pb-4">
                <span>Staged for Ingestion ({files.length} files)</span>
                <button 
                  onClick={() => setFiles([])}
                  className="text-sm text-red-400 hover:text-red-300 flex items-center transition-colors"
                >
                  <Trash2 size={16} className="mr-1" /> Clear All
                </button>
              </h3>
              <ul role="list" className="mt-6 divide-y divide-white/10 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                {files.map((file: File, index: number) => (
                  <li key={index} className="flex items-center justify-between py-4 group">
                    <div className="flex items-center">
                      <FileText className="h-8 w-8 text-sentinel-green/70 mr-4" />
                      <div className="flex flex-col">
                        <p className="text-sm font-medium text-leta-gray-200 truncate max-w-md">{file.name}</p>
                        <p className="text-xs text-leta-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                      </div>
                    </div>
                    <button
                      onClick={() => removeFile(index)}
                      className="text-leta-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Trash2 size={20} />
                    </button>
                  </li>
                ))}
              </ul>

              <div className="mt-8 flex justify-end">
                <button
                  onClick={handleBulkUpload}
                  disabled={isUploading}
                  className={`
                    flex items-center px-8 py-3 border border-transparent text-base font-medium rounded-leta shadow-lg
                    text-leta-black bg-sentinel-green hover:bg-emerald-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sentinel-green focus:ring-offset-black transition-all duration-300
                    ${isUploading ? 'opacity-70 cursor-not-allowed' : ''}
                  `}
                >
                  {isUploading ? (
                    <>
                      <Loader className="animate-spin -ml-1 mr-3 h-5 w-5 text-leta-black" />
                      Processing & Embedding Vectors...
                    </>
                  ) : (
                    <>
                      <UploadCloud className="-ml-1 mr-3 h-5 w-5" />
                      Commence Bulk Ingestion
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Upload Results Summary */}
          {uploadResults && (
            <div className={`mt-8 p-6 rounded-leta border ${uploadResults.failed === 0 ? 'bg-emerald-900/20 border-emerald-500/30' : 'bg-amber-900/20 border-amber-500/30'}`}>
              <h3 className="text-lg font-medium text-leta-gray-900 mb-4 flex items-center">
                {uploadResults.failed === 0 ? <CheckCircle className="mr-2 text-emerald-400" /> : <AlertCircle className="mr-2 text-amber-400" />}
                Ingestion Report
              </h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="bg-leta-black/30 p-4 rounded-leta border border-leta-gray-100">
                  <p className="text-sm text-leta-gray-600">Successfully Vectorized</p>
                  <p className="text-3xl font-bold text-emerald-400">{uploadResults.successful}</p>
                </div>
                <div className="bg-leta-black/30 p-4 rounded-leta border border-leta-gray-100">
                  <p className="text-sm text-leta-gray-600">Failed Processed</p>
                  <p className="text-3xl font-bold text-red-400">{uploadResults.failed}</p>
                </div>
              </div>
              {uploadResults.errors && uploadResults.errors.length > 0 && (
                <div className="mt-4">
                  <p className="text-sm font-medium text-leta-gray-300 mb-2">Error Logs:</p>
                  <ul className="list-disc pl-5 text-xs text-red-300 space-y-1 max-h-32 overflow-y-auto">
                    {uploadResults.errors.map((err: string, i: number) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Management Table Placeholder */}
        <div className="bg-[#0a0a0a] border border-leta-gray-200 rounded-2xl shadow-xl p-8 backdrop-blur-sm opacity-50 relative overflow-hidden group">
          <div className="absolute inset-0 bg-leta-black/60 z-10 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <Edit3 size={40} className="text-sentinel-green mb-4" />
            <p className="text-xl font-semibold text-leta-gray-900">Metadata Management Table</p>
            <p className="text-sm text-leta-gray-600 mt-2">Coming in v2.1. Enables direct editing of tags, categories, and stages.</p>
          </div>
          
          <h2 className="text-2xl font-bold text-leta-gray-900 mb-6">Database Management</h2>
          <div className="animate-pulse flex space-x-4">
             <div className="flex-1 space-y-4 py-1">
               <div className="h-10 bg-leta-white/10 rounded-leta"></div>
               <div className="space-y-3">
                 <div className="grid grid-cols-3 gap-4">
                   <div className="h-6 bg-leta-white/10 rounded-leta col-span-2"></div>
                   <div className="h-6 bg-leta-white/10 rounded-leta col-span-1"></div>
                 </div>
                 <div className="h-6 bg-leta-white/10 rounded-leta"></div>
               </div>
             </div>
           </div>
        </div>

      </div>
    </div>
  );
};

export default AdminTemplateDashboard;
