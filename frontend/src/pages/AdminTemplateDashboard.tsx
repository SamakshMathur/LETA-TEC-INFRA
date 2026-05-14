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
    <div className="min-h-screen bg-[#07070A] text-[#A1A1AA] pt-32 pb-12 px-4 sm:px-6 lg:px-8 mt-4">
      <div className="max-w-7xl mx-auto space-y-12">
        
        {/* Header Section */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl md:text-5xl font-bold font-display tracking-tight text-white uppercase">
            Template Intelligence Portal
          </h1>
          <p className="text-xl text-[#9a9a9a] max-w-2xl mx-auto font-light">
            Bulk ingest legal frameworks, parse semantics, and vector-index templates into the main database.
          </p>
        </div>

        {/* Upload Interface */}
        <div className="bg-secondary border border-white/[0.05] rounded-2xl shadow-2xl p-8 backdrop-blur-sm">
          <h2 className="text-2xl font-bold text-white mb-6 flex items-center font-display uppercase tracking-wide">
            <UploadCloud className="mr-3 text-[#67E8F9]" size={28} />
            Bulk Ingestion Zone
          </h2>
          
          <div 
            {...getRootProps()} 
            className={`
              mt-2 flex justify-center rounded-leta border-2 border-dashed px-6 py-20 transition-all duration-300 ease-in-out cursor-pointer
              ${isDragActive 
                ? 'border-[#67E8F9] bg-[#67E8F9]/5 scale-[1.01]' 
                : 'border-white/[0.05] hover:border-white/[0.15] hover:bg-white/[0.01]'
              }
            `}
          >
            <div className="text-center">
              <input {...getInputProps()} />
              <UploadCloud className="mx-auto h-16 w-16 text-[#67E8F9]/70 mb-4 animate-pulse" aria-hidden="true" />
              <div className="mt-4 flex text-lg leading-6 text-[#9a9a9a] justify-center">
                <span className="relative font-semibold text-[#67E8F9] hover:text-[#22D3EE] rounded-leta">
                  <span>Click to select files</span>
                </span>
                <p className="pl-2">or drag and drop</p>
              </div>
              <p className="text-sm leading-5 text-[#9a9a9a]/40 mt-2 font-mono">
                PDF, DOCX, TXT, PNG, JPG (500+ files supported simultaneously)
              </p>
            </div>
          </div>

          {/* Staged Files List */}
          {files.length > 0 && (
            <div className="mt-10">
              <h3 className="text-lg font-medium text-white flex items-center justify-between border-b border-white/[0.05] pb-4">
                <span>Staged for Ingestion ({files.length} files)</span>
                <button 
                  onClick={() => setFiles([])}
                  className="text-sm text-red-400 hover:text-red-300 flex items-center transition-colors font-mono"
                >
                  <Trash2 size={16} className="mr-1" /> Clear All
                </button>
              </h3>
              <ul role="list" className="mt-6 divide-y divide-white/10 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                {files.map((file: File, index: number) => (
                  <li key={index} className="flex items-center justify-between py-4 group">
                    <div className="flex items-center">
                      <FileText className="h-8 w-8 text-[#67E8F9]/70 mr-4" />
                      <div className="flex flex-col">
                        <p className="text-sm font-medium text-white truncate max-w-md">{file.name}</p>
                        <p className="text-xs text-[#9a9a9a]/40">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                      </div>
                    </div>
                    <button
                      onClick={() => removeFile(index)}
                      className="text-[#9a9a9a]/40 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
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
                    flex items-center px-8 py-3.5 text-base font-semibold rounded-leta shadow-lg
                    text-[#07070A] bg-[#67E8F9] hover:bg-[#22D3EE] transition-all duration-300
                    ${isUploading ? 'opacity-70 cursor-not-allowed' : ''}
                  `}
                >
                  {isUploading ? (
                    <>
                      <Loader className="animate-spin -ml-1 mr-3 h-5 w-5 text-[#07070A]" />
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
            <div className={`mt-8 p-6 rounded-leta border ${uploadResults.failed === 0 ? 'bg-emerald-950/20 border-emerald-500/30' : 'bg-amber-950/20 border-amber-500/30'}`}>
              <h3 className="text-lg font-medium text-white mb-4 flex items-center font-display">
                {uploadResults.failed === 0 ? <CheckCircle className="mr-2 text-emerald-400" /> : <AlertCircle className="mr-2 text-amber-400" />}
                Ingestion Report
              </h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="bg-[#07070A] p-4 rounded-leta border border-white/[0.05]">
                  <p className="text-sm text-[#9a9a9a]">Successfully Vectorized</p>
                  <p className="text-3xl font-bold text-emerald-400">{uploadResults.successful}</p>
                </div>
                <div className="bg-[#07070A] p-4 rounded-leta border border-white/[0.05]">
                  <p className="text-sm text-[#9a9a9a]">Failed Processed</p>
                  <p className="text-3xl font-bold text-red-400">{uploadResults.failed}</p>
                </div>
              </div>
              {uploadResults.errors && uploadResults.errors.length > 0 && (
                <div className="mt-4">
                  <p className="text-sm font-medium text-white mb-2">Error Logs:</p>
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
        <div className="bg-secondary border border-white/[0.05] rounded-2xl shadow-xl p-8 backdrop-blur-sm opacity-50 relative overflow-hidden group">
          <div className="absolute inset-0 bg-[#07070A]/85 z-10 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <Edit3 size={40} className="text-[#67E8F9] mb-4" />
            <p className="text-xl font-semibold text-white font-display uppercase tracking-wide">Metadata Management Table</p>
            <p className="text-sm text-[#9a9a9a] mt-2">Coming in v2.1. Enables direct editing of tags, categories, and stages.</p>
          </div>
          
          <h2 className="text-2xl font-bold text-white mb-6 font-display uppercase tracking-wide">Database Management</h2>
          <div className="animate-pulse flex space-x-4">
             <div className="flex-1 space-y-4 py-1">
               <div className="h-10 bg-white/5 rounded-leta"></div>
               <div className="space-y-3">
                 <div className="grid grid-cols-3 gap-4">
                   <div className="h-6 bg-white/5 rounded-leta col-span-2"></div>
                   <div className="h-6 bg-white/5 rounded-leta col-span-1"></div>
                 </div>
                 <div className="h-6 bg-white/5 rounded-leta"></div>
               </div>
             </div>
           </div>
        </div>

      </div>
    </div>
  );
};

export default AdminTemplateDashboard;
