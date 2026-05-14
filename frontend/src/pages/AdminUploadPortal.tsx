import React, { useState, useCallback, useRef, useEffect } from 'react';
import { BASE_URL } from '../config/api';

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

const statusStyleMap = {
  queued:     { dot: 'bg-amber-400',       text: 'text-amber-400',       card: 'border-amber-400/20 bg-amber-400/5' },
  processing: { dot: 'bg-[#67E8F9] animate-pulse', text: 'text-[#67E8F9]',  card: 'border-[#67E8F9]/20 bg-[#67E8F9]/5' },
  done:       { dot: 'bg-emerald-500',   text: 'text-emerald-500',   card: 'border-emerald-500/20 bg-emerald-500/5' },
  error:      { dot: 'bg-red-500',          text: 'text-red-500',          card: 'border-red-500/20 bg-red-500/5' },
};

const statusStyle = (s: string) => (statusStyleMap[s as keyof typeof statusStyleMap] || { dot: 'bg-neutral-500', text: 'text-neutral-600', card: 'border-white/[0.05] bg-secondary' });

interface StatCardProps {
  label: string;
  value?: string | number;
  sub?: string;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, sub }) => (
  <div className="bg-secondary border border-white/[0.05] rounded-leta p-5 hover:bg-hover hover:border-white/[0.1] transition-all duration-300 shadow-xl">
    <p className="text-[11px] text-[#9a9a9a] uppercase tracking-wider font-mono">{label}</p>
    <p className="text-2xl font-bold text-white mt-1 font-display tracking-tight">{value ?? '—'}</p>
    {sub && <p className="text-xs text-[#9a9a9a]/60 mt-0.5 font-mono">{sub}</p>}
  </div>
);

const formatBytes = (b: number) => {
  if (!b) return '0 B';
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(b) / Math.log(1024));
  return `${(b / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
};

const fileIcon = (name: string) => {
  if (/\.pdf$/i.test(name)) return '📕';
  if (/\.docx?$/i.test(name)) return '📘';
  if (/\.xlsx?$/i.test(name)) return '📗';
  return '📄';
};

// ─── Main Component ───────────────────────────────────────────────────────────
const AdminUploadPortal: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>('circulars');
  const [dragging, setDragging]   = useState<boolean>(false);
  const [fileQueue, setFileQueue] = useState<any[]>([]);   // { id, file }
  const [jobs, setJobs]           = useState<any[]>([]);
  const [sysStatus, setSysStatus] = useState<any>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError]         = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef   = useRef<Record<string, any>>({});

  const authHdr = () => ({});

  // ── System status ──────────────────────────────────────────────────────────
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/admin/status`, { headers: authHdr() });
      if (res.ok) setSysStatus(await res.json());
    } catch {}
  };

  useEffect(() => { fetchStatus(); }, []);

  // ── Drag & Drop ────────────────────────────────────────────────────────────
  const onDragOver  = useCallback((e: React.DragEvent) => { e.preventDefault(); setDragging(true);  }, []);
  const onDragLeave = useCallback(()  => setDragging(false), []);
  const onDrop      = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  }, []);

  const addFiles = (incoming: File[]) => {
    const valid   = incoming.filter(f => ALLOWED.test(f.name));
    const skipped = incoming.length - valid.length;
    if (skipped) setError(`${skipped} file(s) skipped — only PDF, DOCX, XLSX, TXT allowed.`);
    else setError('');
    setFileQueue(prev => [...prev, ...valid.map(f => ({ id: Math.random().toString(36).slice(2), file: f }))]);
  };

  const removeFile = (id: string) => setFileQueue(prev => prev.filter(f => f.id !== id));

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
  const startPolling = (jobId: string) => {
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`${BASE_URL}/api/admin/jobs/${jobId}`, { headers: authHdr() });
        if (res.ok) {
          const job = await res.json();
          setJobs(prev => prev.map((j: any) => j.job_id === jobId ? { ...j, ...job } : j));
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

  const catLabel = (key: string) => CATEGORIES.find(c => c.key === key)?.label ?? key;

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#07070A] text-[#A1A1AA] pt-[140px] pb-16 px-4 sm:px-6">
      <div className="max-w-5xl mx-auto space-y-8">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4 border-b border-white/[0.05] pb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-leta bg-white/[0.02] border border-white/[0.05] flex items-center justify-center text-[#67E8F9]">
                <span className="text-sm">⬆</span>
              </div>
              <h1 className="text-2xl font-bold text-white tracking-tight font-display uppercase">Admin Upload Portal</h1>
              <span className="text-[10px] font-black tracking-[0.2em] uppercase text-[#67E8F9] bg-white/[0.02] border border-white/[0.05] px-2.5 py-0.5 rounded-full">TITAN</span>
            </div>
            <p className="text-sm text-[#9a9a9a] ml-13">Upload documents → auto-chunk → embed → FAISS index update</p>
          </div>
          <button onClick={fetchStatus}
            className="shrink-0 text-xs text-[#9a9a9a] hover:text-[#67E8F9] border border-white/[0.05] hover:border-white/[0.1] rounded-leta px-4 py-2 bg-white/[0.01] transition-all">
            ↻ Refresh
          </button>
        </div>

        {/* ── System Stats ───────────────────────────────────────────────── */}
        {sysStatus && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Total Vectors" value={sysStatus.faiss?.total_vectors?.toLocaleString()} sub="FAISS index" />
            <StatCard label="Embedding Dim" value={sysStatus.faiss?.dimension} sub="BGE-large" />
            <StatCard label="Total Chunks"  value={sysStatus.faiss?.total_chunks?.toLocaleString()} sub="chunks.jsonl" />
            <StatCard label="Documents"
              value={Object.values(sysStatus.categories || {}).reduce((a: any, b: any) => a + b, 0) as number}
              sub={`across ${Object.keys(sysStatus.categories || {}).length} categories`} />
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ── Upload Panel ─────────────────────────────────────────────── */}
          <div className="lg:col-span-2 space-y-6">

            {/* Category selector */}
            <div className="bg-secondary rounded-2xl border border-white/[0.05] p-6 shadow-xl">
              <p className="text-xs font-semibold text-white uppercase tracking-wider mb-4 font-mono">Target Category</p>
              <div className="grid grid-cols-4 gap-2">
                {CATEGORIES.map(({ key, label }) => (
                  <button key={key} onClick={() => setSelectedCategory(key)}
                    className={`py-2 px-1 rounded-leta text-[11px] font-medium transition-all text-center ${
                      selectedCategory === key
                        ? 'bg-[#67E8F9] text-[#07070A] shadow-lg shadow-[#67E8F9]/10 scale-[1.01] font-semibold'
                        : 'bg-[#07070A] text-[#9a9a9a] hover:text-white border border-white/[0.05] hover:border-white/[0.1] hover:bg-hover'
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
              className={`relative border-2 border-dashed rounded-2xl p-14 text-center cursor-pointer transition-all select-none ${
                dragging
                  ? 'border-[#67E8F9] bg-[#67E8F9]/5 scale-[1.01]'
                  : 'border-white/[0.05] hover:border-white/[0.1] bg-secondary hover:bg-hover'
              }`}>
              <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.xlsx,.xls,.txt"
                className="hidden" onChange={(e) => addFiles(Array.from(e.target.files || []))} />
              <div className="text-5xl mb-4 transition-transform">{dragging ? '📂' : '📄'}</div>
              <p className="text-white font-semibold text-sm">
                {dragging ? 'Drop files here' : 'Drag & drop files, or click to browse'}
              </p>
              <p className="text-[#9a9a9a]/60 text-xs mt-1.5 font-mono">PDF · DOCX · XLSX · XLS · TXT</p>
            </div>

            {/* File queue */}
            {fileQueue.length > 0 && (
              <div className="bg-secondary rounded-2xl border border-white/[0.05] overflow-hidden shadow-xl">
                <div className="px-5 py-4 border-b border-white/[0.05] flex items-center justify-between">
                  <span className="text-sm font-medium text-white">
                    {fileQueue.length} file{fileQueue.length > 1 ? 's' : ''} ready
                  </span>
                  <button onClick={() => setFileQueue([])}
                    className="text-xs text-red-400 hover:text-red-300 transition-colors font-mono">
                    Clear all
                  </button>
                </div>
                <div className="max-h-52 overflow-y-auto divide-y divide-white/[0.05] custom-scrollbar">
                  {fileQueue.map(({ id, file }) => (
                    <div key={id} className="flex items-center gap-3 px-5 py-3 hover:bg-hover">
                      <span className="text-xl shrink-0">{fileIcon(file.name)}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-white truncate">{file.name}</p>
                        <p className="text-xs text-[#9a9a9a]/40 font-mono">{formatBytes(file.size)}</p>
                      </div>
                      <button onClick={() => removeFile(id)}
                        className="text-[#9a9a9a]/40 hover:text-red-400 transition-colors text-sm shrink-0 ml-2">
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="p-4 rounded-leta bg-red-500/5 border border-red-500/20 text-red-400 text-sm font-mono">{error}</div>
            )}

            {/* Upload button */}
            <button onClick={handleUpload} disabled={uploading || !fileQueue.length}
              className={`w-full py-4 rounded-leta text-sm font-semibold transition-all ${
                uploading || !fileQueue.length
                  ? 'bg-white/[0.02] border border-white/[0.05] text-[#52525B] cursor-not-allowed'
                  : 'bg-[#67E8F9] hover:bg-[#22D3EE] text-[#07070A] shadow-lg shadow-[#67E8F9]/10'
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
            <p className="text-xs font-semibold text-white uppercase tracking-wider mb-4 font-mono">Ingestion Jobs</p>
            {jobs.length === 0 ? (
              <div className="bg-secondary rounded-2xl border border-white/[0.05] p-10 text-center shadow-xl">
                <p className="text-3xl mb-3">🗂</p>
                <p className="text-[#9a9a9a] text-sm font-medium">No jobs yet</p>
                <p className="text-[#9a9a9a]/40 text-xs mt-1.5 font-mono">Upload files to start</p>
              </div>
            ) : (
              <div className="space-y-4 max-h-[560px] overflow-y-auto pr-1 custom-scrollbar">
                {jobs.map(job => {
                  const st = statusStyle(job.status);
                  return (
                    <div key={job.job_id} className={`rounded-leta border p-5 transition-all ${st.card}`}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-[10px] font-mono text-[#9a9a9a]/40 truncate">#{job.job_id}</p>
                          <p className="text-xs text-white font-semibold mt-0.5 font-display uppercase tracking-wider">
                            {catLabel(job.category)}
                          </p>
                          <p className="text-[11px] text-[#9a9a9a] mt-0.5 font-mono">
                            {job.files?.length} file{job.files?.length > 1 ? 's' : ''}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className={`w-2 h-2 rounded-full ${st.dot}`} />
                          <span className={`text-[10px] font-bold uppercase tracking-wide font-mono ${st.text}`}>
                            {job.status}
                          </span>
                        </div>
                      </div>

                      {/* File list */}
                      <div className="mt-3 space-y-1.5">
                        {job.files?.slice(0, 3).map((f: string, i: number) => (
                          <p key={i} className="text-[11px] text-[#9a9a9a] truncate flex items-center gap-1.5 font-mono">
                            <span>{fileIcon(f)}</span> {f}
                          </p>
                        ))}
                        {job.files?.length > 3 && (
                          <p className="text-[11px] text-[#9a9a9a]/40 font-mono">+{job.files.length - 3} more</p>
                        )}
                      </div>

                      {/* Result stats */}
                      {job.result && job.status === 'done' && (
                        <div className="mt-3 pt-3 border-t border-white/[0.05] flex gap-4 font-mono text-[11px]">
                          <span className="text-[#9a9a9a]">
                            <span className="text-emerald-400 font-semibold">{job.result.chunks_added ?? 0}</span> chunks
                          </span>
                          <span className="text-[#9a9a9a]">
                            <span className="text-emerald-400 font-semibold">{job.result.vectors_added ?? 0}</span> vectors
                          </span>
                        </div>
                      )}

                      {/* Error detail */}
                      {job.status === 'error' && job.error && (
                        <p className="text-[11px] text-red-400 mt-2 truncate font-mono">{job.error}</p>
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
