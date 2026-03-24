import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

const BASE_URL = import.meta.env.PROD ? '/api_proxy' : 'http://localhost:8000';

const CATEGORIES = [
  { key: 'acts',         label: 'Acts' },
  { key: 'cgst',         label: 'CGST' },
  { key: 'igst',         label: 'IGST' },
  { key: 'rules',        label: 'Rules' },
  { key: 'notifications',label: 'Notifications' },
  { key: 'circulars',    label: 'Circulars' },
  { key: 'aars',         label: 'AARs' },
  { key: 'highcourt',    label: 'High Court' },
  { key: 'supremecourt', label: 'Supreme Court' },
  { key: 'forms',        label: 'Forms' },
  { key: 'faqs',         label: 'FAQs' },
  { key: 'icai',         label: 'ICAI' },
  { key: 'export',       label: 'Export' },
  { key: 'brochures',    label: 'Brochures' },
  { key: 'flyers',       label: 'Flyers' },
  { key: 'reports',      label: 'Reports' },
];

const ALLOWED = /\.(pdf|docx|xlsx|xls|txt)$/i;

const statusStyle = (s) => ({
  queued:     { dot: 'bg-yellow-400',       text: 'text-yellow-400',       card: 'border-yellow-400/20 bg-yellow-400/5' },
  processing: { dot: 'bg-blue-400 animate-pulse', text: 'text-blue-400',  card: 'border-blue-400/20 bg-blue-400/5' },
  done:       { dot: 'bg-sentinel-green',   text: 'text-sentinel-green',   card: 'border-sentinel-green/20 bg-sentinel-green/5' },
  error:      { dot: 'bg-red-400',          text: 'text-red-400',          card: 'border-red-400/20 bg-red-500/5' },
}[s] || { dot: 'bg-gray-500', text: 'text-gray-400', card: 'border-white/10 bg-white/5' });

const StatCard = ({ label, value, sub }) => (
  <div className="bg-white/5 border border-white/10 rounded-xl p-4 hover:bg-white/[0.07] transition-colors">
    <p className="text-[11px] text-gray-500 uppercase tracking-wider">{label}</p>
    <p className="text-2xl font-bold text-white mt-1">{value ?? '—'}</p>
    {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
  </div>
);

const formatBytes = (b) => {
  if (!b) return '0 B';
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(b) / Math.log(1024));
  return `${(b / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
};

const fileIcon = (name) => {
  if (/\.pdf$/i.test(name)) return '📕';
  if (/\.docx?$/i.test(name)) return '📘';
  if (/\.xlsx?$/i.test(name)) return '📗';
  return '📄';
};

// ─── Main Component ───────────────────────────────────────────────────────────
const AdminUploadPortal = () => {
  const { token } = useAuth();

  const [selectedCategory, setSelectedCategory] = useState('circulars');
  const [dragging, setDragging]   = useState(false);
  const [fileQueue, setFileQueue] = useState([]);   // { id, file }
  const [jobs, setJobs]           = useState([]);
  const [sysStatus, setSysStatus] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError]         = useState('');

  const fileInputRef = useRef(null);
  const pollingRef   = useRef({});

  const authHdr = () => ({ Authorization: `Bearer ${token}` });

  // ── System status ──────────────────────────────────────────────────────────
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/admin/status`, { headers: authHdr() });
      if (res.ok) setSysStatus(await res.json());
    } catch {}
  };

  useEffect(() => { fetchStatus(); }, []);

  // ── Drag & Drop ────────────────────────────────────────────────────────────
  const onDragOver  = useCallback((e) => { e.preventDefault(); setDragging(true);  }, []);
  const onDragLeave = useCallback(()  => setDragging(false), []);
  const onDrop      = useCallback((e) => {
    e.preventDefault(); setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  }, []);

  const addFiles = (incoming) => {
    const valid   = incoming.filter(f => ALLOWED.test(f.name));
    const skipped = incoming.length - valid.length;
    if (skipped) setError(`${skipped} file(s) skipped — only PDF, DOCX, XLSX, TXT allowed.`);
    else setError('');
    setFileQueue(prev => [...prev, ...valid.map(f => ({ id: Math.random().toString(36).slice(2), file: f }))]);
  };

  const removeFile = (id) => setFileQueue(prev => prev.filter(f => f.id !== id));

  // ── Upload ─────────────────────────────────────────────────────────────────
  const handleUpload = async () => {
    if (!fileQueue.length) { setError('Add at least one file before uploading.'); return; }
    setError(''); setUploading(true);

    const fd = new FormData();
    fd.append('category', selectedCategory);
    fileQueue.forEach(({ file }) => fd.append('files', file));

    try {
      const res = await fetch(`${BASE_URL}/api/admin/upload`, {
        method: 'POST', headers: authHdr(), body: fd,
      });
      const data = await res.json();
      if (res.ok) {
        setJobs(prev => [{
          job_id: data.job_id,
          category: selectedCategory,
          files: fileQueue.map(f => f.file.name),
          status: 'queued',
          created_at: new Date().toISOString(),
        }, ...prev]);
        setFileQueue([]);
        startPolling(data.job_id);
      } else {
        setError(data.detail || 'Upload failed.');
      }
    } catch { setError('Network error during upload.'); }
    finally { setUploading(false); }
  };

  // ── Job polling ────────────────────────────────────────────────────────────
  const startPolling = (jobId) => {
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`${BASE_URL}/api/admin/jobs/${jobId}`, { headers: authHdr() });
        if (res.ok) {
          const job = await res.json();
          setJobs(prev => prev.map(j => j.job_id === jobId ? { ...j, ...job } : j));
          if (job.status === 'done' || job.status === 'error') {
            clearInterval(iv);
            delete pollingRef.current[jobId];
            fetchStatus();
          }
        }
      } catch {}
    }, 2000);
    pollingRef.current[jobId] = iv;
  };

  useEffect(() => () => Object.values(pollingRef.current).forEach(clearInterval), []);

  const catLabel = (key) => CATEGORIES.find(c => c.key === key)?.label ?? key;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-sentinel-dark py-8 px-4 sm:px-6">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="w-8 h-8 rounded-lg bg-sentinel-green/15 border border-sentinel-green/30 flex items-center justify-center">
                <span className="text-sentinel-green text-sm">⬆</span>
              </div>
              <h1 className="text-xl font-bold text-white tracking-tight">Admin Upload Portal</h1>
              <span className="text-[10px] font-black tracking-[0.2em] uppercase text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">TITAN</span>
            </div>
            <p className="text-sm text-gray-500 ml-11">Upload documents → auto-chunk → embed → FAISS index update</p>
          </div>
          <button onClick={fetchStatus}
            className="shrink-0 text-xs text-gray-500 hover:text-sentinel-green border border-white/10 hover:border-sentinel-green/30 rounded-lg px-3 py-2 transition-all">
            ↻ Refresh
          </button>
        </div>

        {/* ── System Stats ───────────────────────────────────────────────── */}
        {sysStatus && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Total Vectors" value={sysStatus.faiss?.total_vectors?.toLocaleString()} sub="FAISS index" />
            <StatCard label="Embedding Dim" value={sysStatus.faiss?.dimension} sub="BGE-large" />
            <StatCard label="Total Chunks"  value={sysStatus.faiss?.total_chunks?.toLocaleString()} sub="chunks.jsonl" />
            <StatCard label="Documents"
              value={Object.values(sysStatus.categories || {}).reduce((a, b) => a + b, 0)}
              sub={`across ${Object.keys(sysStatus.categories || {}).length} categories`} />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ── Upload Panel ─────────────────────────────────────────────── */}
          <div className="lg:col-span-2 space-y-4">

            {/* Category selector */}
            <div className="bg-white/5 rounded-2xl border border-white/10 p-5">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Target Category</p>
              <div className="grid grid-cols-4 gap-2">
                {CATEGORIES.map(({ key, label }) => (
                  <button key={key} onClick={() => setSelectedCategory(key)}
                    className={`py-2 px-2 rounded-lg text-xs font-medium transition-all text-center ${
                      selectedCategory === key
                        ? 'bg-sentinel-green text-white shadow-lg shadow-sentinel-green/20 scale-[1.02]'
                        : 'bg-black/30 text-gray-500 hover:text-gray-200 border border-white/5 hover:border-white/15'
                    }`}>
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Drop zone */}
            <div
              onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`relative border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all select-none ${
                dragging
                  ? 'border-sentinel-green bg-sentinel-green/5 scale-[1.01] shadow-[0_0_30px_rgba(16,185,129,0.1)]'
                  : 'border-white/10 hover:border-white/25 bg-black/20 hover:bg-black/30'
              }`}>
              <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.xlsx,.xls,.txt"
                className="hidden" onChange={(e) => addFiles(Array.from(e.target.files))} />
              <div className="text-5xl mb-3 transition-transform">{dragging ? '📂' : '📄'}</div>
              <p className="text-white font-semibold text-sm">
                {dragging ? 'Drop files here' : 'Drag & drop files, or click to browse'}
              </p>
              <p className="text-gray-600 text-xs mt-1.5">PDF · DOCX · XLSX · XLS · TXT</p>
            </div>

            {/* File queue */}
            {fileQueue.length > 0 && (
              <div className="bg-white/5 rounded-2xl border border-white/10 overflow-hidden">
                <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                  <span className="text-sm font-medium text-white">
                    {fileQueue.length} file{fileQueue.length > 1 ? 's' : ''} ready
                  </span>
                  <button onClick={() => setFileQueue([])}
                    className="text-xs text-gray-600 hover:text-red-400 transition-colors">
                    Clear all
                  </button>
                </div>
                <div className="max-h-52 overflow-y-auto divide-y divide-white/5">
                  {fileQueue.map(({ id, file }) => (
                    <div key={id} className="flex items-center gap-3 px-4 py-3 hover:bg-white/[0.03]">
                      <span className="text-xl shrink-0">{fileIcon(file.name)}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-white truncate">{file.name}</p>
                        <p className="text-xs text-gray-600">{formatBytes(file.size)}</p>
                      </div>
                      <button onClick={() => removeFile(id)}
                        className="text-gray-600 hover:text-red-400 transition-colors text-sm shrink-0 ml-2">
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>
            )}

            {/* Upload button */}
            <button onClick={handleUpload} disabled={uploading || !fileQueue.length}
              className={`w-full py-3.5 rounded-xl text-sm font-semibold text-white transition-all ${
                uploading || !fileQueue.length
                  ? 'bg-gray-700/60 cursor-not-allowed opacity-50'
                  : 'bg-sentinel-green hover:bg-[#096646] shadow-lg shadow-sentinel-green/20 hover:shadow-sentinel-green/30 hover:scale-[1.01]'
              }`}>
              {uploading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Ingesting documents...
                </span>
              ) : `Upload to ${catLabel(selectedCategory)} →`}
            </button>
          </div>

          {/* ── Jobs Panel ───────────────────────────────────────────────── */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Ingestion Jobs</p>
            {jobs.length === 0 ? (
              <div className="bg-white/5 rounded-2xl border border-white/10 p-8 text-center">
                <p className="text-3xl mb-2">🗂</p>
                <p className="text-gray-600 text-sm">No jobs yet</p>
                <p className="text-gray-700 text-xs mt-1">Upload files to start</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[560px] overflow-y-auto pr-1">
                {jobs.map(job => {
                  const st = statusStyle(job.status);
                  return (
                    <div key={job.job_id} className={`rounded-xl border p-4 transition-all ${st.card}`}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-[10px] font-mono text-gray-600 truncate">#{job.job_id}</p>
                          <p className="text-xs text-gray-300 font-medium mt-0.5">
                            {catLabel(job.category)}
                          </p>
                          <p className="text-[11px] text-gray-600 mt-0.5">
                            {job.files?.length} file{job.files?.length > 1 ? 's' : ''}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className={`w-2 h-2 rounded-full ${st.dot}`} />
                          <span className={`text-xs font-semibold uppercase tracking-wide ${st.text}`}>
                            {job.status}
                          </span>
                        </div>
                      </div>

                      {/* File list */}
                      <div className="mt-2 space-y-1">
                        {job.files?.slice(0, 3).map((f, i) => (
                          <p key={i} className="text-[11px] text-gray-600 truncate flex items-center gap-1">
                            <span>{fileIcon(f)}</span> {f}
                          </p>
                        ))}
                        {job.files?.length > 3 && (
                          <p className="text-[11px] text-gray-700">+{job.files.length - 3} more</p>
                        )}
                      </div>

                      {/* Result stats */}
                      {job.result && job.status === 'done' && (
                        <div className="mt-2 pt-2 border-t border-white/10 flex gap-4">
                          <span className="text-[11px] text-gray-500">
                            <span className="text-sentinel-green font-semibold">{job.result.chunks_added ?? 0}</span> chunks
                          </span>
                          <span className="text-[11px] text-gray-500">
                            <span className="text-sentinel-green font-semibold">{job.result.vectors_added ?? 0}</span> vectors
                          </span>
                        </div>
                      )}

                      {/* Error detail */}
                      {job.status === 'error' && job.error && (
                        <p className="text-[11px] text-red-400 mt-2 truncate">{job.error}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default AdminUploadPortal;
