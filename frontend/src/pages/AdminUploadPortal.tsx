import React, { useState, useCallback, useEffect, useRef } from 'react';
import { 
  UploadCloud, FileText, CheckCircle, AlertCircle, Trash2, 
  RefreshCw, Archive, Search, Filter, History, Eye, BookOpen, AlertTriangle, Cpu, Database,
  Users, Key, Webhook, CreditCard, Settings, Terminal, Compass, Activity, Server, HardDrive, BarChart3, BellRing
} from 'lucide-react';
import { BASE_URL } from '../config/api';
import { useAuth } from '../hooks/useAuth';
import { useKnowledgePolling } from '../hooks/useKnowledgePolling';
import { KnowledgeDocument, AuditLog, SystemStatus, IngestionJob } from '../types/admin';
import { hasRole, getActiveRole } from '../lib/permissions';
import { AXIOS_INSTANCE } from '../utils/api';

const CATEGORIES = [
  { key: 'acts', label: 'Acts' },
  { key: 'cgst', label: 'CGST' },
  { key: 'igst', label: 'IGST' },
  { key: 'rules', label: 'Rules' },
  { key: 'notifications', label: 'Notifications' },
  { key: 'circulars', label: 'Circulars' },
  { key: 'aars', label: 'AARs' },
  { key: 'highcourt', label: 'High Court' },
  { key: 'supremecourt', label: 'Supreme Court' },
  { key: 'forms', label: 'Forms' },
  { key: 'faqs', label: 'FAQs' },
  { key: 'icai', label: 'ICAI' },
  { key: 'export', label: 'Export' },
  { key: 'brochures', label: 'Brochures' },
  { key: 'flyers', label: 'Flyers' },
  { key: 'reports', label: 'Reports' },
];

const statusStyles: Record<string, { dot: string; text: string; bg: string }> = {
  'Queued': { dot: 'bg-amber-400', text: 'text-amber-400', bg: 'bg-amber-400/10' },
  'Extracting': { dot: 'bg-cyan-400 animate-pulse', text: 'text-cyan-400', bg: 'bg-cyan-400/10' },
  'Cleaning': { dot: 'bg-sky-400 animate-pulse', text: 'text-sky-400', bg: 'bg-sky-400/10' },
  'Chunking': { dot: 'bg-blue-400 animate-pulse', text: 'text-blue-400', bg: 'bg-blue-400/10' },
  'Embedding': { dot: 'bg-indigo-400 animate-pulse', text: 'text-indigo-400', bg: 'bg-indigo-400/10' },
  'Indexing': { dot: 'bg-purple-400 animate-pulse', text: 'text-purple-400', bg: 'bg-purple-400/10' },
  'Refreshing Retriever': { dot: 'bg-pink-400 animate-pulse', text: 'text-pink-400', bg: 'bg-pink-400/10' },
  'Completed': { dot: 'bg-emerald-500', text: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  'Failed': { dot: 'bg-red-500', text: 'text-red-500', bg: 'bg-red-500/10' },
  'Archived': { dot: 'bg-neutral-500', text: 'text-neutral-500', bg: 'bg-neutral-500/10' },
};

interface StatCardProps {
  label: string;
  value?: string | number;
  sub?: string;
  icon?: React.ReactNode;
  dataSource?: string;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, sub, icon, dataSource }) => (
  <div className="bg-[#0F1722] border border-white/[0.05] rounded-xl p-5 hover:bg-hover hover:border-white/[0.1] transition-all duration-300 shadow-xl relative overflow-hidden group">
    <div className="flex justify-between items-start">
      <div>
        <p className="text-[11px] text-[#9a9a9a] uppercase tracking-wider font-mono">{label}</p>
        <p className="text-2xl font-bold text-white mt-1.5 font-display tracking-tight">{value ?? '—'}</p>
      </div>
      {icon && <div className="text-[#67E8F9] opacity-75 group-hover:opacity-100 transition-opacity">{icon}</div>}
    </div>
    <div className="flex justify-between items-center mt-2.5">
      {sub && <p className="text-xs text-[#9a9a9a]/60 font-mono">{sub}</p>}
      {dataSource && (
        <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.02] text-white/35 font-mono border border-white/[0.05]">
          {dataSource}
        </span>
      )}
    </div>
  </div>
);

interface ServiceStatus {
  status: "online" | "offline" | "ok" | "connected" | "degraded" | "disconnected" | "unavailable";
  ping_ms?: number;
  keys?: number;
  vectors?: number;
  collections?: number;
  indexes?: number;
}

interface HealthInfo {
  overall_status: string;
  score: number;
  startup_checks: Record<string, string>;
  telemetry: {
    cpu_percent: number;
    ram_percent: number;
    disk_percent: number;
    cpu_history_10: number[];
    ram_history_10: number[];
  };
  services: {
    ocr_engine: ServiceStatus;
    faiss: ServiceStatus;
    redis: ServiceStatus;
    mongodb: ServiceStatus;
    embedding_provider: ServiceStatus;
    llm_provider: ServiceStatus;
  };
  storage: {
    disk_usage_mb: number;
    documents_count: number;
    vectors_count: number;
  };
}

const AdminUploadPortal: React.FC = () => {
  const { session, isLoggedIn } = useAuth();
  
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState<'overview' | 'kb' | 'upload' | 'jobs' | 'team' | 'analytics' | 'health' | 'keys' | 'billing' | 'settings'>('overview');
  
  // Command Palette & Assistant States
  const [showPalette, setShowPalette] = useState<boolean>(false);
  const [paletteQuery, setPaletteQuery] = useState<string>('');
  const [assistantOpen, setAssistantOpen] = useState<boolean>(false);
  const [assistantPrompt, setAssistantPrompt] = useState<string>('');
  const [assistantReplies, setAssistantReplies] = useState<Array<{ sender: 'user' | 'ai'; text: string }>>([
    { sender: 'ai', text: 'LETA TEC Administrative Console active. How can I help you query operational data today?' }
  ]);
  
  // Data States
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [sysStatus, setSysStatus] = useState<SystemStatus | null>(null);
  
  // Team Management States
  const [members, setMembers] = useState<any[]>([]);
  const [invitations, setInvitations] = useState<any[]>([]);
  const [organizations, setOrganizations] = useState<any[]>([]);
  const [inviteEmail, setInviteEmail] = useState<string>('');
  const [inviteRole, setInviteRole] = useState<string>('viewer');
  
  // Health & System Metrics
  const [healthInfo, setHealthInfo] = useState<HealthInfo | null>(null);
  const [analyticsInfo, setAnalyticsInfo] = useState<any>(null);
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [webhooks, setWebhooks] = useState<any[]>([]);
  const [billingInfo, setBillingInfo] = useState<any>(null);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');
  
  // Input fields for Keys / Webhooks / Settings
  const [newKeyName, setNewKeyName] = useState<string>('');
  const [newKeyRole, setNewKeyRole] = useState<string>('viewer');
  const [newWebhookName, setNewWebhookName] = useState<string>('');
  const [newWebhookUrl, setNewWebhookUrl] = useState<string>('');
  
  // Settings States
  const [chunkSize, setChunkSize] = useState<number>(1000);
  const [chunkOverlap, setChunkOverlap] = useState<number>(200);
  const [retrieverTopK, setRetrieverTopK] = useState<number>(8);
  const [temperature, setTemperature] = useState<number>(0.2);

  // Filters
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  
  // Upload States
  const [selectedCategory, setSelectedCategory] = useState<string>('circulars');
  const [uploadQueue, setUploadQueue] = useState<Array<{ id: string; file: File; hash: string; duplicateDoc?: any; status: 'ready' | 'duplicate' | 'uploading' | 'success' | 'failed'; progress: number }>>([]);
  const [error, setError] = useState<string>('');
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [dragging, setDragging] = useState<boolean>(false);
  
  // Detail Modals
  const [previewDoc, setPreviewDoc] = useState<KnowledgeDocument | null>(null);
  const [versionHistoryDoc, setVersionHistoryDoc] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const authHeaders = useCallback(() => {
    return {
      'Authorization': `Bearer ${session?.tokens?.accessToken}`,
    };
  }, [session]);

  const fetchDocuments = useCallback(async () => {
    try {
      const queryParams = new URLSearchParams();
      if (categoryFilter) queryParams.append('category', categoryFilter);
      if (statusFilter) queryParams.append('status', statusFilter);
      if (searchTerm) queryParams.append('search', searchTerm);
      
      const res = await AXIOS_INSTANCE.get(`/api/admin/knowledge/list?${queryParams.toString()}`);
      setDocuments(res.data);
    } catch (e) {
      console.error(e);
    }
  }, [categoryFilter, statusFilter, searchTerm]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await AXIOS_INSTANCE.get('/api/admin/status');
      setSysStatus(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchAuditLogs = useCallback(async () => {
    try {
      const res = await AXIOS_INSTANCE.get('/api/admin/knowledge/audit-logs');
      setAuditLogs(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchJobs = useCallback(async () => {
    try {
      const res = await AXIOS_INSTANCE.get('/api/admin/jobs');
      setJobs(res.data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchControlCenterData = useCallback(async () => {
    try {
      const hRes = await AXIOS_INSTANCE.get('/api/admin/control-center/health');
      setHealthInfo(hRes.data);
      
      const aRes = await AXIOS_INSTANCE.get('/api/admin/control-center/analytics');
      setAnalyticsInfo(aRes.data);
      
      const tRes = await AXIOS_INSTANCE.get('/api/admin/control-center/team');
      const teamData = tRes.data;
      setMembers(teamData.members || []);
      setInvitations(teamData.invitations || []);
      setOrganizations(teamData.organizations || []);
      
      const kRes = await AXIOS_INSTANCE.get('/api/admin/control-center/keys');
      setApiKeys(kRes.data);
      
      const wRes = await AXIOS_INSTANCE.get('/api/admin/control-center/webhooks');
      setWebhooks(wRes.data);
      
      const bRes = await AXIOS_INSTANCE.get('/api/admin/control-center/billing');
      setBillingInfo(bRes.data);
      
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("Failed to load control center stats", err);
    }
  }, []);

  // Hook up keyboard shortcut for Command Palette (Cmd/Ctrl + K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowPalette(v => !v);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const hasActiveJobs = jobs.some(j => ['queued', 'processing'].includes(j.status)) ||
    documents.some(doc => !['Completed', 'Failed', 'Archived'].includes(doc.status));

  // Run polling
  useKnowledgePolling(fetchDocuments, fetchStatus, fetchAuditLogs, fetchJobs, hasActiveJobs, isLoggedIn);
  
  const prevActiveRef = useRef(hasActiveJobs);
  useEffect(() => {
    if (prevActiveRef.current && !hasActiveJobs) {
      // Ingestion successfully finished - automatically refresh control center
      fetchControlCenterData();
    }
    prevActiveRef.current = hasActiveJobs;
  }, [hasActiveJobs, fetchControlCenterData]);

  useEffect(() => {
    fetchControlCenterData();
  }, [fetchControlCenterData]);

  const getFileSHA256 = async (file: File): Promise<string> => {
    const arrayBuffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragging(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files) {
      await addFilesToQueue(Array.from(e.dataTransfer.files));
    }
  }, []);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      await addFilesToQueue(Array.from(e.target.files));
    }
  };

  const addFilesToQueue = async (files: File[]) => {
    setError('');
    const newItems: typeof uploadQueue = [];
    for (const file of files) {
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
      const allowed = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.csv', '.txt', '.md'];
      if (!allowed.includes(ext)) {
        setError(`File extension ${ext} not supported.`);
        continue;
      }
      
      const hash = await getFileSHA256(file);
      let duplicateDoc = undefined;
      try {
        const res = await AXIOS_INSTANCE.post('/api/admin/knowledge/check-duplicate', { sha256: hash });
        if (res.data.duplicate) {
          duplicateDoc = res.data.document;
        }
      } catch (err) {
        console.error(err);
      }

      newItems.push({
        id: Math.random().toString(36).substring(7),
        file,
        hash,
        duplicateDoc,
        status: duplicateDoc ? 'duplicate' : 'ready',
        progress: 0
      });
    }
    setUploadQueue(prev => [...prev, ...newItems]);
  };

  const handleUploadQueueItem = async (itemId: string, overrideAction?: 'force' | 'replace') => {
    const item = uploadQueue.find(i => i.id === itemId);
    if (!item) return;

    setUploadQueue(prev => prev.map(i => i.id === itemId ? { ...i, status: 'uploading' } : i));
    const formData = new FormData();
    formData.append('file', item.file);
    formData.append('category', selectedCategory);
    if (overrideAction === 'force') formData.append('force', 'true');

    try {
      let relativeUrl = `/api/admin/knowledge/upload`;
      if (overrideAction === 'replace' && item.duplicateDoc) {
        relativeUrl = `/api/admin/knowledge/replace/${item.duplicateDoc.document_id}`;
      }

      await AXIOS_INSTANCE.post(relativeUrl, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      setUploadQueue(prev => prev.map(i => i.id === itemId ? { ...i, status: 'success', progress: 100 } : i));
      fetchDocuments();
      fetchAuditLogs();
      fetchJobs();
    } catch (e) {
      setUploadQueue(prev => prev.map(i => i.id === itemId ? { ...i, status: 'failed' } : i));
    }
  };

  const processUploadAll = async () => {
    setIsUploading(true);
    const pendingItems = uploadQueue.filter(i => i.status === 'ready');
    for (const item of pendingItems) {
      await handleUploadQueueItem(item.id);
    }
    setIsUploading(false);
  };

  const archiveAction = async (docId: string) => {
    if (!confirm('Are you sure you want to archive this document? Chunks will be dynamically ignored from retrieval.')) return;
    try {
      await AXIOS_INSTANCE.post(`/api/admin/knowledge/archive/${docId}`);
      fetchDocuments();
      fetchAuditLogs();
    } catch (e) {
      console.error(e);
    }
  };

  const reindexAction = async (docId: string) => {
    try {
      await AXIOS_INSTANCE.post(`/api/admin/knowledge/reindex/${docId}`);
      fetchDocuments();
      fetchAuditLogs();
      fetchJobs();
    } catch (e) {
      console.error(e);
    }
  };

  // Team Invite action
  const inviteMemberAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail) return;
    try {
      await AXIOS_INSTANCE.post(`/api/admin/control-center/team/invite`, { email: inviteEmail, role: inviteRole });
      setInviteEmail('');
      fetchControlCenterData();
    } catch (err) {
      console.error(err);
    }
  };

  // Team toggle suspend action
  const toggleSuspendAction = async (username: string) => {
    try {
      await AXIOS_INSTANCE.post(`/api/admin/control-center/team/suspend`, { username });
      fetchControlCenterData();
    } catch (err) {
      console.error(err);
    }
  };

  // Key create action
  const createApiKeyAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName) return;
    try {
      await AXIOS_INSTANCE.post(`/api/admin/control-center/keys`, { name: newKeyName, role: newKeyRole });
      setNewKeyName('');
      fetchControlCenterData();
    } catch (err) {
      console.error(err);
    }
  };

  // Webhook create action
  const createWebhookAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWebhookUrl) return;
    try {
      await AXIOS_INSTANCE.post(`/api/admin/control-center/webhooks`, { name: newWebhookName || 'Webhook Endpoint', url: newWebhookUrl });
      setNewWebhookName('');
      setNewWebhookUrl('');
      fetchControlCenterData();
    } catch (err) {
      console.error(err);
    }
  };

  // Embedded AI Console query
  const queryAdminAssistant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assistantPrompt.trim()) return;
    const queryText = assistantPrompt;
    setAssistantPrompt('');
    setAssistantReplies(prev => [...prev, { sender: 'user', text: queryText }]);
    try {
      const res = await AXIOS_INSTANCE.post(`/api/admin/control-center/assistant`, { prompt: queryText });
      setAssistantReplies(prev => [...prev, { sender: 'ai', text: res.data.answer }]);
    } catch (err) {
      console.error(err);
    }
  };

  const activeVersions = documents.filter(doc => doc.is_active);
  const versionHistoryList = documents.filter(doc => versionHistoryDoc && doc.filename === versionHistoryDoc);

  // Command palette search items
  const paletteItems = [
    { name: 'Dashboard Overview', path: 'overview', tab: 'overview' },
    { name: 'Knowledge Base Catalog', path: 'kb', tab: 'kb' },
    { name: 'Document Ingestion Queue', path: 'upload', tab: 'upload' },
    { name: 'Background Jobs Monitor', path: 'jobs', tab: 'jobs' },
    { name: 'Team directory & Invitations', path: 'team', tab: 'team' },
    { name: 'AI query Analytics', path: 'analytics', tab: 'analytics' },
    { name: 'Systems Health status', path: 'health', tab: 'health' },
    { name: 'API keys & Webhooks configuration', path: 'keys', tab: 'keys' },
    { name: 'Billing subscriptions & Usage', path: 'billing', tab: 'billing' },
    { name: 'Retriever Settings & Parameters', path: 'settings', tab: 'settings' }
  ];
  const filteredPaletteItems = paletteItems.filter(item => 
    item.name.toLowerCase().includes(paletteQuery.toLowerCase())
  );

  const services = {
    ocr: healthInfo?.services?.ocr_engine?.status ?? "Offline",
    redis: healthInfo?.services?.redis?.status ?? "Disconnected",
    faiss: healthInfo?.services?.faiss?.status ?? "Degraded",
    mongodb: healthInfo?.services?.mongodb?.status ?? "Disconnected",
  };

  return (
    <div className="min-h-screen bg-[#07070A] text-[#A1AAB8] pt-[100px] pb-16 px-6 font-sans">
      <div className="max-w-7xl mx-auto flex flex-col lg:flex-row gap-8">
        
        {/* Left Sidebar Navigation */}
        <aside className="w-full lg:w-64 shrink-0 flex flex-col gap-2">
          <div className="px-3 py-4 border-b border-white/[0.05] mb-2 flex items-center gap-2">
            <Compass className="text-[#67E8F9]" size={20} />
            <span className="text-xs font-bold uppercase tracking-wider text-white">Control Panel</span>
          </div>
          {[
            { id: 'overview', label: 'Executive Dashboard', icon: Compass },
            { id: 'kb', label: 'Knowledge Base', icon: BookOpen },
            { id: 'upload', label: 'Upload Center', icon: UploadCloud },
            { id: 'jobs', label: 'Pipeline Jobs', icon: Cpu },
            { id: 'team', label: 'Team Directory', icon: Users },
            { id: 'analytics', label: 'AI Analytics', icon: BarChart3 },
            { id: 'health', label: 'System Health', icon: Server },
            { id: 'keys', label: 'API & Webhooks', icon: Key },
            { id: 'billing', label: 'Billing & Sub', icon: CreditCard },
            { id: 'settings', label: 'System Settings', icon: Settings },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id as any)}
                className={`w-full flex items-center gap-3 px-4 py-3 text-xs font-semibold rounded-xl transition-all ${
                  activeTab === item.id
                    ? 'bg-[#67E8F9]/10 border border-[#67E8F9]/20 text-[#67E8F9]'
                    : 'text-[#9a9a9a] hover:text-white hover:bg-white/[0.02] border border-transparent'
                }`}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </aside>

        {/* Right Dashboard Area */}
        <main className="flex-grow space-y-8 min-w-0">

          {/* Header Panel */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-white/[0.05] pb-6 gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold font-display tracking-tight text-white uppercase">LETA TEC Control Center</h1>
                <span className="text-[10px] font-black tracking-[0.2em] uppercase text-[#67E8F9] bg-[#67E8F9]/10 border border-[#67E8F9]/20 px-2.5 py-0.5 rounded-full">v1.5 Enterprise</span>
                {healthInfo?.score !== undefined && (
                  <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full font-mono ${
                    healthInfo.score >= 80 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                    healthInfo.score >= 50 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                    'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                  }`}>
                    Health: {healthInfo.score}% ({healthInfo.overall_status})
                  </span>
                )}
              </div>
              <p className="text-xs text-[#9a9a9a] mt-1 flex items-center gap-2">
                <span>Press <kbd className="bg-white/[0.05] px-1 rounded text-[10px] border border-white/[0.1] font-mono">Cmd + K</kbd> anywhere to navigate instantly.</span>
                {lastRefreshed && <span className="text-[10px] text-white/30 font-mono">| Updated: {lastRefreshed}</span>}
              </p>
            </div>
            
            <div className="flex gap-2">
              <button 
                onClick={() => setAssistantOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-[#67E8F9]/10 hover:bg-[#67E8F9]/20 border border-[#67E8F9]/20 hover:border-[#67E8F9]/40 rounded-xl text-xs font-semibold text-[#67E8F9] transition-all"
              >
                <Terminal size={14} /> AI Assistant
              </button>
              <button 
                onClick={() => { fetchDocuments(); fetchStatus(); fetchControlCenterData(); }}
                className="flex items-center gap-2 px-4 py-2 bg-secondary border border-white/[0.05] hover:bg-hover rounded-xl text-xs font-semibold text-white transition-all"
              >
                <RefreshCw size={13} /> Sync Panel
              </button>
            </div>
          </div>

          {/* tab contents */}

          {/* OVERVIEW / DASHBOARD TAB */}
          {activeTab === 'overview' && (
            <div className="space-y-8 animate-in fade-in duration-200">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard label="Pipeline Latency" value={analyticsInfo?.usage?.average_latency_ms ? `${analyticsInfo.usage.average_latency_ms} ms` : "—"} sub="Average query timing" icon={<Activity size={18} />} dataSource="MongoDB Analytics" />
                <StatCard label="Storage Utilization" value={analyticsInfo?.storage?.disk_usage_mb ? `${analyticsInfo.storage.disk_usage_mb} MB` : "—"} sub="Disk storage allocation" icon={<HardDrive size={18} />} dataSource="System File Disk" />
                <StatCard label="Monthly Tokens" value={analyticsInfo?.usage?.token_count_monthly?.toLocaleString() || "—"} sub="Tokens generated" icon={<Server size={18} />} dataSource="MongoDB Analytics" />
                <StatCard label="FAISS Database Vectors" value={sysStatus?.faiss_index?.total_vectors?.toLocaleString() || "—"} sub="Total embedding records" icon={<Database size={18} />} dataSource="FAISS Index System" />
              </div>

              {/* Ingestion progress, latest uploads queue, alerts */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                {/* Active documents block */}
                <div className="lg:col-span-2 bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <Database size={16} className="text-[#67E8F9]" /> Centralized Knowledge Base Registry
                    </h3>
                    <p className="text-[11px] text-[#9a9a9a]">Summary of documents loaded per category.</p>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                    {sysStatus && Object.entries(sysStatus.categories || {}).map(([key, info]: [string, any]) => (
                      <div key={key} className="bg-[#07070A] border border-white/[0.03] rounded-xl p-4 flex flex-col justify-between">
                        <span className="text-[11px] font-semibold font-mono text-[#9a9a9a] uppercase truncate">{key}</span>
                        <span className="text-lg font-bold text-white mt-1">{info.files} <span className="text-xs text-[#9a9a9a]/40 font-normal">files</span></span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Notifications & timelines block */}
                <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <BellRing size={16} className="text-[#67E8F9]" /> Notification Center
                    </h3>
                    <p className="text-[11px] text-[#9a9a9a]">System telemetry status indicators.</p>
                  </div>
                  <div className="space-y-4 text-xs font-mono">
                    <div className="flex justify-between items-center py-2 border-b border-white/[0.03]">
                      <span className="text-[#9a9a9a]">OCR Engine Status</span>
                      <span className={`font-bold ${services.ocr === 'online' ? 'text-emerald-400' : 'text-amber-500'}`}>
                        {services.ocr}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-white/[0.03]">
                      <span className="text-[#9a9a9a]">Retriever Hot-Reload</span>
                      <span className={`font-bold ${services.faiss === 'ok' ? 'text-emerald-400' : 'text-amber-500'}`}>
                        {services.faiss === 'ok' ? 'Ready' : 'Degraded'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-white/[0.03]">
                      <span className="text-[#9a9a9a]">Redis Cache Status</span>
                      <span className={`font-bold ${services.redis === 'connected' || services.redis === 'ok' ? 'text-emerald-400' : 'text-amber-500'}`}>
                        {services.redis}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-white/[0.03]">
                      <span className="text-[#9a9a9a]">MongoDB Connection</span>
                      <span className={`font-bold ${services.mongodb === 'connected' ? 'text-emerald-400' : 'text-amber-500'}`}>
                        {services.mongodb}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Recent administrative trail logs */}
              <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <History size={16} className="text-[#67E8F9]" /> Administrative Audit logs
                  </h3>
                  <p className="text-[11px] text-[#9a9a9a]">Latest administrative events recorded.</p>
                </div>
                <div className="space-y-3">
                  {auditLogs.slice(0, 5).map((log, idx) => (
                    <div key={idx} className="bg-[#07070A] rounded-xl p-4 border border-white/[0.03] flex flex-col sm:flex-row justify-between sm:items-center gap-2 text-xs">
                      <div className="flex items-center gap-3">
                        <span className="px-2 py-0.5 bg-[#67E8F9]/10 text-[#67E8F9] font-mono text-[9px] uppercase font-bold rounded">
                          {log.action}
                        </span>
                        <p className="text-white font-medium">{log.details}</p>
                      </div>
                      <div className="flex items-center gap-3 font-mono text-[10px] text-[#9a9a9a]/40 self-end sm:self-auto">
                        <span>By: {log.user_id}</span>
                        <span>{new Date(log.timestamp).toLocaleString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* KNOWLEDGE BASE TAB */}
          {activeTab === 'kb' && (
            <div className="space-y-6 animate-in fade-in duration-200">
              <div className="bg-[#0F1722] rounded-2xl border border-white/[0.05] p-4 shadow-md flex flex-wrap gap-4 items-center justify-between">
                <div className="flex gap-3 items-center flex-1 min-w-[240px]">
                  <Search size={18} className="text-[#9a9a9a]" />
                  <input 
                    type="text" 
                    placeholder="Search filename or title..." 
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="bg-transparent text-sm text-white placeholder-[#9a9a9a]/40 border-none outline-none w-full"
                  />
                </div>
                <div className="flex gap-3">
                  <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#07070A] border border-white/[0.05] rounded-lg">
                    <Filter size={12} className="text-[#67E8F9]" />
                    <select 
                      value={categoryFilter} 
                      onChange={(e) => setCategoryFilter(e.target.value)}
                      className="bg-transparent text-xs text-white border-none outline-none cursor-pointer font-mono"
                    >
                      <option value="">All Categories</option>
                      {CATEGORIES.map(c => <option key={c.key} value={c.key} className="bg-[#07070A]">{c.label}</option>)}
                    </select>
                  </div>
                  <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#07070A] border border-white/[0.05] rounded-lg">
                    <select 
                      value={statusFilter} 
                      onChange={(e) => setStatusFilter(e.target.value)}
                      className="bg-transparent text-xs text-white border-none outline-none cursor-pointer font-mono"
                    >
                      <option value="">All Statuses</option>
                      {Object.keys(statusStyles).map(s => <option key={s} value={s} className="bg-[#07070A]">{s}</option>)}
                    </select>
                  </div>
                </div>
              </div>

              <div className="bg-[#0F1722] rounded-2xl border border-white/[0.05] overflow-hidden shadow-xl">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-white/[0.05] text-[11px] font-semibold text-[#9a9a9a] uppercase tracking-wider font-mono">
                        <th className="px-6 py-4">Filename</th>
                        <th className="px-6 py-4">Category</th>
                        <th className="px-6 py-4">Chunks</th>
                        <th className="px-6 py-4">Version</th>
                        <th className="px-6 py-4">Status</th>
                        <th className="px-6 py-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.05]">
                      {documents.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="px-6 py-12 text-center text-[#9a9a9a]/40 font-medium">
                            No documents matching filter parameters
                          </td>
                        </tr>
                      ) : (
                        documents.map((doc) => {
                          const style = statusStyles[doc.status] || { dot: 'bg-neutral-500', text: 'text-neutral-500', bg: 'bg-neutral-500/10' };
                          return (
                            <tr key={doc.document_id} className={`hover:bg-hover transition-colors group ${!doc.is_active ? 'opacity-50' : ''}`}>
                              <td className="px-6 py-4">
                                <p className="font-semibold text-white truncate max-w-[200px]">{doc.filename}</p>
                                <p className="text-[9px] text-[#9a9a9a]/40 font-mono mt-0.5">{new Date(doc.uploaded_at).toLocaleString()}</p>
                              </td>
                              <td className="px-6 py-4 capitalize font-mono text-[#9a9a9a]">
                                {doc.category}
                              </td>
                              <td className="px-6 py-4 font-mono text-white">
                                {doc.chunk_count || '—'}
                              </td>
                              <td className="px-6 py-4 font-mono">
                                v{doc.version}
                              </td>
                              <td className="px-6 py-4">
                                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9px] font-bold uppercase tracking-wider ${style.text} ${style.bg}`}>
                                  <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                                  {doc.status}
                                </span>
                              </td>
                              <td className="px-6 py-4 text-right">
                                <div className="flex gap-2 justify-end opacity-80 group-hover:opacity-100 transition-opacity">
                                  <button 
                                    onClick={() => setPreviewDoc(doc)}
                                    className="p-1.5 bg-[#07070A] hover:bg-hover border border-white/[0.05] rounded-lg text-[#67E8F9]"
                                    title="Preview document"
                                  >
                                    <Eye size={13} />
                                  </button>
                                  <button 
                                    onClick={() => setVersionHistoryDoc(doc.filename)}
                                    className="p-1.5 bg-[#07070A] hover:bg-hover border border-white/[0.05] rounded-lg text-indigo-400"
                                    title="Version history"
                                  >
                                    <History size={13} />
                                  </button>
                                  {doc.is_active && (
                                    <>
                                      <button 
                                        onClick={() => reindexAction(doc.document_id)}
                                        className="p-1.5 bg-[#07070A] hover:bg-hover border border-white/[0.05] rounded-lg text-amber-400"
                                        title="Reindex document"
                                      >
                                        <RefreshCw size={13} />
                                      </button>
                                      <button 
                                        onClick={() => archiveAction(doc.document_id)}
                                        className="p-1.5 bg-[#07070A] hover:bg-hover border border-white/[0.05] rounded-lg text-red-400"
                                        title="Archive (Soft Delete)"
                                      >
                                        <Archive size={13} />
                                      </button>
                                    </>
                                  )}
                                </div>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* UPLOAD CENTER TAB */}
          {activeTab === 'upload' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-in fade-in duration-200">
              <div className="lg:col-span-1 space-y-6">
                <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                  <div>
                    <h3 className="text-sm font-bold text-white">Database Ingestion Inbound</h3>
                    <p className="text-[11px] text-[#9a9a9a]">Select category and trigger ingestion parser tasks.</p>
                  </div>
                  
                  <div className="space-y-2">
                    <label className="text-[11px] font-semibold text-[#9a9a9a] uppercase tracking-wider font-mono">Category</label>
                    <div className="grid grid-cols-2 gap-1.5 max-h-48 overflow-y-auto custom-scrollbar border border-white/[0.05] p-1 bg-[#07070A] rounded-xl">
                      {CATEGORIES.map(({ key, label }) => (
                        <button 
                          key={key} 
                          onClick={() => setSelectedCategory(key)}
                          className={`py-1.5 px-2 rounded-lg text-left text-[11px] font-medium transition-all truncate ${
                            selectedCategory === key
                              ? 'bg-[#67E8F9] text-[#07070A] font-semibold'
                              : 'text-[#9a9a9a] hover:text-white hover:bg-hover'
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div 
                    onDragOver={handleDragOver} 
                    onDragLeave={handleDragLeave} 
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed border-white/[0.05] hover:border-[#67E8F9] rounded-xl p-8 text-center cursor-pointer transition-all space-y-3 ${
                      dragging ? 'bg-[#67E8F9]/5 border-[#67E8F9]' : 'bg-[#07070A]/50'
                    }`}
                  >
                    <input 
                      type="file" 
                      ref={fileInputRef} 
                      className="hidden" 
                      onChange={handleFileChange} 
                      multiple 
                      accept=".pdf,.docx,.doc,.txt,.md,.csv,.xlsx,.xls"
                    />
                    <UploadCloud size={36} className="mx-auto text-[#67E8F9]" />
                    <div>
                      <p className="text-sm text-white font-semibold">Drag & drop files or click</p>
                      <p className="text-[9px] text-[#9a9a9a]/40 mt-1">PDF · DOCX · XLSX · CSV · TXT · MD</p>
                    </div>
                  </div>

                  {error && (
                    <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-xs p-3 rounded-lg flex gap-2">
                      <AlertCircle size={16} className="shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="lg:col-span-2 bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="text-sm font-bold text-white">Upload Queue</h3>
                    <p className="text-[11px] text-[#9a9a9a]">Inbound queue backlog awaiting indexing.</p>
                  </div>
                  {uploadQueue.length > 0 && (
                    <div className="flex gap-2">
                      <button 
                        onClick={processUploadAll}
                        disabled={isUploading}
                        className="px-3 py-1.5 bg-[#67E8F9] text-[#07070A] hover:bg-[#67E8F9]/90 disabled:opacity-50 text-xs font-bold rounded-lg transition-all"
                      >
                        Upload All
                      </button>
                      <button 
                        onClick={() => setUploadQueue([])}
                        className="px-3 py-1.5 bg-[#07070A] hover:bg-hover text-xs font-medium border border-white/[0.05] rounded-lg text-white"
                      >
                        Clear Queue
                      </button>
                    </div>
                  )}
                </div>

                {uploadQueue.length === 0 ? (
                  <div className="py-16 text-center text-sm text-[#9a9a9a]/30 font-medium">
                    Queue is empty. Drop files to configure ingestion.
                  </div>
                ) : (
                  <div className="space-y-4 max-h-[450px] overflow-y-auto custom-scrollbar pr-2">
                    {uploadQueue.map((item) => (
                      <div key={item.id} className="bg-[#07070A] rounded-xl p-4 border border-white/[0.03] space-y-3">
                        <div className="flex items-center justify-between gap-4">
                          <div className="flex items-center gap-3 min-w-0">
                            <FileText className="text-[#67E8F9] shrink-0" size={18} />
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-white truncate max-w-[320px]">{item.file.name}</p>
                              <p className="text-[9px] text-[#9a9a9a]/40 font-mono mt-0.5">Hash: {item.hash.substring(0, 16)}...</p>
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-[10px] font-semibold text-[#9a9a9a] uppercase font-mono">
                              {item.status}
                            </span>
                            <button 
                              onClick={() => setUploadQueue(prev => prev.filter(q => q.id !== item.id))}
                              className="text-[#9a9a9a]/40 hover:text-red-400 p-1"
                            >
                              ✕
                            </button>
                          </div>
                        </div>

                        {item.status === 'duplicate' && item.duplicateDoc && (
                          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                            <div className="flex gap-2 items-start">
                              <AlertTriangle className="text-amber-400 shrink-0 mt-0.5" size={16} />
                              <div>
                                <p className="font-semibold text-white">Duplicate Conflict</p>
                                <p className="text-[#9a9a9a] text-[10px] mt-0.5">Existing version registered on {new Date(item.duplicateDoc.uploaded_at).toLocaleDateString()}.</p>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <button 
                                onClick={() => handleUploadQueueItem(item.id, 'force')}
                                className="px-2.5 py-1 bg-amber-500 text-black hover:bg-amber-400 font-bold rounded text-[10px]"
                              >
                                Force Upload
                              </button>
                              <button 
                                onClick={() => handleUploadQueueItem(item.id, 'replace')}
                                className="px-2.5 py-1 bg-cyan-400 text-black hover:bg-cyan-300 font-bold rounded text-[10px]"
                              >
                                Replace Version
                              </button>
                            </div>
                          </div>
                        )}

                        {item.status === 'uploading' && (
                          <div className="h-1 bg-[#0F1722] rounded-full overflow-hidden">
                            <div className="h-full bg-[#67E8F9] animate-pulse" style={{ width: '40%' }} />
                          </div>
                        )}
                        
                        {item.status === 'ready' && (
                          <button 
                            onClick={() => handleUploadQueueItem(item.id)}
                            className="w-full py-1.5 bg-[#0F1722] hover:bg-hover border border-white/[0.05] hover:border-[#67E8F9] text-xs font-semibold rounded-lg text-white transition-all"
                          >
                            Start Ingestion
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PIPELINE JOBS TAB */}
          {activeTab === 'jobs' && (
            <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6 animate-in fade-in duration-200">
              <div>
                <h3 className="text-sm font-bold text-white">Ingestion Pipeline Monitor</h3>
                <p className="text-[11px] text-[#9a9a9a]">Active background thread pools extracting, embedding, and indexing documents.</p>
              </div>

              <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
                {jobs.length === 0 ? (
                  <p className="text-center text-xs text-[#9a9a9a]/30 py-16 font-medium">No ingestion jobs currently recorded</p>
                ) : (
                  jobs.map((job) => (
                    <div key={job.job_id} className="bg-[#07070A] rounded-xl p-5 border border-white/[0.03] space-y-4">
                      <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm text-white font-bold">Job {job.job_id}</span>
                            <span className={`px-2 py-0.5 text-[9px] font-bold uppercase rounded font-mono ${
                              job.status === 'done' ? 'bg-emerald-500/10 text-emerald-500' :
                              job.status === 'processing' ? 'bg-cyan-500/10 text-cyan-500 animate-pulse' : 'bg-amber-500/10 text-amber-500'
                            }`}>
                              {job.status}
                            </span>
                          </div>
                          <p className="text-[10px] text-[#9a9a9a]/40 font-mono mt-1">Started: {new Date(job.started_at).toLocaleString()}</p>
                        </div>
                        <div className="text-right font-mono text-xs">
                          <span className="text-[#9a9a9a]">Uploaded by: </span><span className="text-white">{job.uploaded_by}</span>
                        </div>
                      </div>

                      <div className="border-t border-white/[0.03] pt-3 text-xs space-y-2">
                        <p className="font-semibold text-white">Target files:</p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
                          {job.files.map((file, idx) => (
                            <div key={idx} className="flex justify-between py-1 px-3 bg-[#0F1722]/50 border border-white/[0.02] rounded-lg">
                              <span className="text-[#9a9a9a] truncate max-w-[240px]">{file}</span>
                              <span className="text-[#67E8F9]">Ingested</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* TEAM DIRECTORY TAB */}
          {activeTab === 'team' && (
            <div className="space-y-8 animate-in fade-in duration-200">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                {/* Directory panel */}
                <div className="lg:col-span-2 bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                  <div>
                    <h3 className="text-sm font-bold text-white">Member Directory</h3>
                    <p className="text-[11px] text-[#9a9a9a]">Manage active administrative users and capability credentials.</p>
                  </div>
                  
                  <div className="space-y-3">
                    {members.map((m, idx) => (
                      <div key={idx} className="bg-[#07070A] rounded-xl p-4 border border-white/[0.03] flex items-center justify-between gap-4 text-xs">
                        <div>
                          <p className="font-bold text-white">{m.username}</p>
                          <p className="text-[10px] text-[#9a9a9a] font-mono mt-0.5">{m.email || m.phone}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="px-2.5 py-0.5 bg-[#67E8F9]/10 text-[#67E8F9] font-mono text-[9px] uppercase font-bold rounded">
                            {m.role}
                          </span>
                          <button
                            onClick={() => toggleSuspendAction(m.username)}
                            className={`px-3 py-1 rounded text-[10px] font-bold font-mono transition-all ${
                              m.is_suspended
                                ? 'bg-red-500/10 text-red-500 border border-red-500/20'
                                : 'bg-secondary text-[#9a9a9a] border border-white/[0.05] hover:text-white'
                            }`}
                          >
                            {m.is_suspended ? 'Suspended' : 'Suspend'}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Invite panel */}
                <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                  <div>
                    <h3 className="text-sm font-bold text-white">Invite Team Member</h3>
                    <p className="text-[11px] text-[#9a9a9a]">Send invitation link to new operational staff.</p>
                  </div>

                  <form onSubmit={inviteMemberAction} className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-mono font-semibold text-[#9a9a9a] uppercase tracking-wider">Email Address</label>
                      <input 
                        type="email" 
                        placeholder="e.g. counsel@letatec.com" 
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                        className="w-full bg-[#07070A] border border-white/[0.05] rounded-xl px-4 py-2.5 text-xs text-white placeholder-[#9a9a9a]/20 outline-none focus:border-[#67E8F9]"
                      />
                    </div>
                    
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-mono font-semibold text-[#9a9a9a] uppercase tracking-wider">Default Role</label>
                      <select 
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value)}
                        className="w-full bg-[#07070A] border border-white/[0.05] rounded-xl px-4 py-2.5 text-xs text-white outline-none focus:border-[#67E8F9] cursor-pointer font-mono"
                      >
                        <option value="viewer">Viewer</option>
                        <option value="uploader">Uploader</option>
                        <option value="knowledge_manager">Knowledge Manager</option>
                        <option value="admin">Admin</option>
                      </select>
                    </div>

                    <button 
                      type="submit"
                      className="w-full py-2.5 bg-[#67E8F9] text-[#07070A] hover:bg-[#67E8F9]/90 font-bold rounded-xl text-xs transition-all shadow-lg"
                    >
                      Send Invite
                    </button>
                  </form>

                  {/* Pending Invitations list */}
                  <div className="border-t border-white/[0.05] pt-4 space-y-3">
                    <p className="text-[10px] font-mono font-bold text-[#9a9a9a] uppercase">Pending Invitations</p>
                    <div className="space-y-2">
                      {invitations.map((inv, idx) => (
                        <div key={idx} className="bg-[#07070A] p-3 rounded-xl border border-white/[0.03] flex justify-between items-center text-xs">
                          <div className="truncate max-w-[160px]">
                            <p className="font-semibold text-white truncate">{inv.email}</p>
                            <p className="text-[9px] text-[#9a9a9a]/40 font-mono mt-0.5">Sent: {new Date(inv.sent_at).toLocaleDateString()}</p>
                          </div>
                          <span className="px-2 py-0.5 bg-amber-500/10 text-amber-500 font-mono text-[9px] uppercase font-bold rounded">
                            {inv.role}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* AI ANALYTICS TAB */}
          {activeTab === 'analytics' && (
            <div className="space-y-8 animate-in fade-in duration-200">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard label="Retrieval Quality Index" value={analyticsInfo?.quality?.retrieval_score_percent ? `${analyticsInfo.quality.retrieval_score_percent}%` : "—"} sub="Average segment recall score" icon={<Activity size={18} />} dataSource="MongoDB Analytics" />
                <StatCard label="Citation Accuracy" value={analyticsInfo?.quality?.citation_accuracy_percent ? `${analyticsInfo.quality.citation_accuracy_percent}%` : "—"} sub="Validated source citations" icon={<CheckCircle size={18} />} dataSource="MongoDB Analytics" />
                <StatCard label="Hallucination Index" value={analyticsInfo?.quality?.hallucination_index_percent !== undefined ? `${analyticsInfo.quality.hallucination_index_percent}%` : "—"} sub="Unvalidated output ratio" icon={<AlertTriangle size={18} />} dataSource="MongoDB Analytics" />
              </div>

              {/* Charts or prompt trends */}
              <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                <div>
                  <h3 className="text-sm font-bold text-white">Daily Query Volume</h3>
                  <p className="text-[11px] text-[#9a9a9a]">Active chat and statutory lookup counts over past week.</p>
                </div>
                <div className="h-48 flex items-end justify-between gap-2 pt-6 px-4">
                  {(analyticsInfo?.usage?.daily_queries || [100, 120, 150, 180, 210, 250, 280]).map((val: number, idx: number) => (
                    <div key={idx} className="flex-1 flex flex-col items-center gap-2">
                      <div className="w-full bg-[#67E8F9]/10 border border-[#67E8F9]/20 rounded-t-lg transition-all hover:bg-[#67E8F9]/20" style={{ height: `${(val / 300) * 120}px` }} />
                      <span className="text-[10px] font-mono text-[#9a9a9a]">Day {idx + 1}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* SYSTEM HEALTH MONITOR TAB */}
          {activeTab === 'health' && (() => {
            const cpuVal = healthInfo?.telemetry?.cpu_percent ?? 0;
            const ramVal = healthInfo?.telemetry?.ram_percent ?? 0;
            const diskVal = healthInfo?.telemetry?.disk_percent ?? 0;

            return (
              <div className="space-y-8 animate-in fade-in duration-200">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {/* CPU monitor */}
                  <div className="bg-[#0F1722] border border-white/[0.05] rounded-xl p-5 shadow-lg">
                    <div className="flex justify-between items-center text-xs font-mono mb-2">
                      <span className="text-[#9a9a9a]">CPU Utilization</span>
                      <span className="text-white font-bold">{cpuVal}%</span>
                    </div>
                    <div className="h-1.5 bg-[#07070A] rounded-full overflow-hidden">
                      <div className="h-full bg-[#67E8F9]" style={{ width: `${cpuVal}%` }} />
                    </div>
                  </div>
                  {/* RAM monitor */}
                  <div className="bg-[#0F1722] border border-white/[0.05] rounded-xl p-5 shadow-lg">
                    <div className="flex justify-between items-center text-xs font-mono mb-2">
                      <span className="text-[#9a9a9a]">RAM Allocation</span>
                      <span className="text-white font-bold">{ramVal}%</span>
                    </div>
                    <div className="h-1.5 bg-[#07070A] rounded-full overflow-hidden">
                      <div className="h-full bg-[#67E8F9]" style={{ width: `${ramVal}%` }} />
                    </div>
                  </div>
                  {/* Disk monitor */}
                  <div className="bg-[#0F1722] border border-white/[0.05] rounded-xl p-5 shadow-lg">
                    <div className="flex justify-between items-center text-xs font-mono mb-2">
                      <span className="text-[#9a9a9a]">Disk Space</span>
                      <span className="text-white font-bold">{diskVal}%</span>
                    </div>
                    <div className="h-1.5 bg-[#07070A] rounded-full overflow-hidden">
                      <div className="h-full bg-[#67E8F9]" style={{ width: `${diskVal}%` }} />
                    </div>
                  </div>
                </div>

                {/* Startup checks panel */}
                {healthInfo?.startup_checks && (
                  <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-4">
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        <CheckCircle size={16} className="text-[#67E8F9]" /> Startup Integrity Verification
                      </h3>
                      <p className="text-[11px] text-[#9a9a9a]">Static verification checks executed on system launch.</p>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
                      {Object.entries(healthInfo.startup_checks).map(([chk, val]: [string, any]) => (
                        <div key={chk} className="bg-[#07070A] border border-white/[0.03] rounded-xl p-3 flex flex-col justify-between">
                          <span className="text-[9px] font-mono text-[#9a9a9a] uppercase truncate">{chk.replace('_', ' ')}</span>
                          <span className={`text-[10px] font-bold mt-1 ${val === 'passed' ? 'text-emerald-400' : val === 'optional' ? 'text-amber-400' : 'text-rose-400'}`}>
                            {val.toUpperCase()}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Service health loops */}
                <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      <Server size={16} className="text-[#67E8F9]" /> Microservices & Integration Checks
                    </h3>
                    <p className="text-[11px] text-[#9a9a9a]">Real-time connectivity and status latency checks.</p>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {healthInfo?.services && Object.entries(healthInfo.services).map(([service, status]: [string, any]) => {
                      const serviceStatus = typeof status === 'object' ? status.status : status;
                      const hasDetails = typeof status === 'object';
                      const isOk = serviceStatus === 'ok' || serviceStatus === 'online' || serviceStatus === 'connected';

                      return (
                        <div key={service} className="bg-[#07070A] border border-white/[0.03] rounded-xl p-4 flex items-center justify-between">
                          <div className="flex flex-col">
                            <span className="text-xs font-semibold font-mono text-white capitalize">{service.replace('_', ' ')}</span>
                            {hasDetails && (
                              <span className="text-[9px] text-[#9a9a9a]/40 font-mono mt-0.5">
                                {status.ping_ms !== undefined ? `ping: ${status.ping_ms}ms` : ''}
                                {status.vectors !== undefined ? `vectors: ${status.vectors}` : ''}
                                {status.keys !== undefined ? `keys: ${status.keys}` : ''}
                              </span>
                            )}
                          </div>
                          <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider font-mono ${
                            isOk ? 'bg-emerald-500/10 text-emerald-500' : 'bg-amber-500/10 text-amber-500'
                          }`}>
                            {serviceStatus}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })()}

          {/* API KEYS & WEBHOOKS TAB */}
          {activeTab === 'keys' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 animate-in fade-in duration-200">
              
              {/* API Keys Panel */}
              <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Key size={16} className="text-[#67E8F9]" /> API Access Keys
                  </h3>
                  <p className="text-[11px] text-[#9a9a9a]">Generate and revoke tokens for external system requests.</p>
                </div>

                <form onSubmit={createApiKeyAction} className="flex gap-2">
                  <input 
                    type="text" 
                    placeholder="e.g. Gateway Token" 
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    className="flex-grow bg-[#07070A] border border-white/[0.05] rounded-xl px-4 py-2 text-xs text-white placeholder-[#9a9a9a]/20 outline-none focus:border-[#67E8F9]"
                  />
                  <button 
                    type="submit"
                    className="px-4 py-2 bg-[#67E8F9] text-[#07070A] hover:bg-[#67E8F9]/90 font-bold rounded-xl text-xs transition-all shrink-0"
                  >
                    Generate
                  </button>
                </form>

                <div className="space-y-3 max-h-72 overflow-y-auto pr-1 custom-scrollbar">
                  {apiKeys.map((k) => (
                    <div key={k.id} className="bg-[#07070A] rounded-xl p-3 border border-white/[0.03] flex justify-between items-center text-xs">
                      <div>
                        <p className="font-bold text-white">{k.name}</p>
                        <p className="text-[9px] text-[#9a9a9a] font-mono mt-0.5">{k.prefix}</p>
                      </div>
                      <button 
                        onClick={async () => {
                          try {
                            await AXIOS_INSTANCE.delete(`/api/admin/control-center/keys/${k.id}`);
                            fetchControlCenterData();
                          } catch (e) {
                            console.error(e);
                          }
                        }}
                        className="text-red-400 hover:text-red-300 font-mono text-[10px]"
                      >
                        Revoke
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Webhooks Panel */}
              <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <Webhook size={16} className="text-[#67E8F9]" /> Event Webhooks
                  </h3>
                  <p className="text-[11px] text-[#9a9a9a]">Deliver live event messages to webhook target URLs.</p>
                </div>

                <form onSubmit={createWebhookAction} className="space-y-3">
                  <input 
                    type="text" 
                    placeholder="Webhook Name" 
                    value={newWebhookName}
                    onChange={(e) => setNewWebhookName(e.target.value)}
                    className="w-full bg-[#07070A] border border-white/[0.05] rounded-xl px-4 py-2 text-xs text-white placeholder-[#9a9a9a]/20 outline-none focus:border-[#67E8F9]"
                  />
                  <div className="flex gap-2">
                    <input 
                      type="url" 
                      placeholder="https://your-domain.com/webhook" 
                      value={newWebhookUrl}
                      onChange={(e) => setNewWebhookUrl(e.target.value)}
                      className="flex-grow bg-[#07070A] border border-white/[0.05] rounded-xl px-4 py-2 text-xs text-white placeholder-[#9a9a9a]/20 outline-none focus:border-[#67E8F9]"
                    />
                    <button 
                      type="submit"
                      className="px-4 py-2 bg-[#67E8F9] text-[#07070A] hover:bg-[#67E8F9]/90 font-bold rounded-xl text-xs transition-all shrink-0"
                    >
                      Subscribe
                    </button>
                  </div>
                </form>

                <div className="space-y-3 max-h-72 overflow-y-auto pr-1 custom-scrollbar">
                  {webhooks.map((w) => (
                    <div key={w.id} className="bg-[#07070A] rounded-xl p-3 border border-white/[0.03] text-xs space-y-1">
                      <p className="font-bold text-white">{w.name}</p>
                      <p className="text-[9px] text-[#9a9a9a] font-mono truncate">{w.url}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* BILLING & SUBSCRIPTIONS TAB */}
          {activeTab === 'billing' && (() => {
            const docUploaded = billingInfo?.monthly_usage?.documents_uploaded || 0;
            const docLimit = billingInfo?.monthly_usage?.documents_limit || 1000;
            const docPercent = docLimit > 0 ? Math.min((docUploaded / docLimit) * 100, 100) : 0;

            const queryExecuted = billingInfo?.monthly_usage?.queries_executed || 0;
            const queryLimit = billingInfo?.monthly_usage?.queries_limit || 50000;
            const queryPercent = queryLimit > 0 ? Math.min((queryExecuted / queryLimit) * 100, 100) : 0;

            return (
              <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6 animate-in fade-in duration-200">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <CreditCard size={16} className="text-[#67E8F9]" /> Plan & Storage Thresholds
                  </h3>
                  <p className="text-[11px] text-[#9a9a9a]">Active corporate subscriptions and billing usage limits.</p>
                </div>

                <div className="bg-[#07070A] rounded-xl p-6 border border-white/[0.03] space-y-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="text-[11px] font-mono text-[#9a9a9a] uppercase">Active Plan</p>
                      <p className="text-xl font-bold text-white mt-1">{billingInfo?.plan || 'Enterprise Titan'}</p>
                    </div>
                    <span className="px-3 py-1 bg-[#67E8F9]/10 text-[#67E8F9] border border-[#67E8F9]/20 font-bold rounded-lg text-xs">
                      Subscription Active
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-4 border-t border-white/[0.03]">
                    {/* Document Limit */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs font-mono">
                        <span className="text-[#9a9a9a]">Ingested Documents</span>
                        <span className="text-white font-bold">
                          {docUploaded} / {docLimit}
                        </span>
                      </div>
                      <div className="h-1.5 bg-[#0F1722] rounded-full overflow-hidden">
                        <div className="h-full bg-[#67E8F9]" style={{ width: `${docPercent}%` }} />
                      </div>
                    </div>

                    {/* Query Limit */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs font-mono">
                        <span className="text-[#9a9a9a]">Queries Executed</span>
                        <span className="text-white font-bold">
                          {queryExecuted} / {queryLimit}
                        </span>
                      </div>
                      <div className="h-1.5 bg-[#0F1722] rounded-full overflow-hidden">
                        <div className="h-full bg-[#67E8F9]" style={{ width: `${queryPercent}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* SYSTEM SETTINGS TAB */}
          {activeTab === 'settings' && (
            <div className="bg-[#0F1722] border border-white/[0.05] rounded-2xl p-6 shadow-xl space-y-6 animate-in fade-in duration-200">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Settings size={16} className="text-[#67E8F9]" /> RAG Parameters & System Overrides
                </h3>
                <p className="text-[11px] text-[#9a9a9a]">Configure vector storage block splits and dynamic retriever parameters.</p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-xs">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono font-semibold text-[#9a9a9a] uppercase tracking-wider">Semantic Chunk Size (chars)</label>
                  <input 
                    type="number" 
                    value={chunkSize}
                    onChange={(e) => setChunkSize(Number(e.target.value))}
                    className="w-full bg-[#07070A] border border-white/[0.05] rounded-xl px-4 py-2.5 text-white outline-none focus:border-[#67E8F9]"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono font-semibold text-[#9a9a9a] uppercase tracking-wider">Chunk Overlap</label>
                  <input 
                    type="number" 
                    value={chunkOverlap}
                    onChange={(e) => setChunkOverlap(Number(e.target.value))}
                    className="w-full bg-[#07070A] border border-white/[0.05] rounded-xl px-4 py-2.5 text-white outline-none focus:border-[#67E8F9]"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono font-semibold text-[#9a9a9a] uppercase tracking-wider">Retriever Top K Matches</label>
                  <input 
                    type="number" 
                    value={retrieverTopK}
                    onChange={(e) => setRetrieverTopK(Number(e.target.value))}
                    className="w-full bg-[#07070A] border border-white/[0.05] rounded-xl px-4 py-2.5 text-white outline-none focus:border-[#67E8F9]"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-mono font-semibold text-[#9a9a9a] uppercase tracking-wider">LLM Temperature</label>
                  <input 
                    type="number" 
                    step="0.1"
                    value={temperature}
                    onChange={(e) => setTemperature(Number(e.target.value))}
                    className="w-full bg-[#07070A] border border-white/[0.05] rounded-xl px-4 py-2.5 text-white outline-none focus:border-[#67E8F9]"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-4 border-t border-white/[0.03]">
                <button 
                  onClick={() => alert('Operational parameter configurations updated successfully!')}
                  className="px-5 py-2.5 bg-[#67E8F9] text-[#07070A] hover:bg-[#67E8F9]/90 font-bold rounded-xl text-xs transition-all shadow-lg"
                >
                  Save Parameters
                </button>
              </div>
            </div>
          )}

        </main>
      </div>

      {/* Embedded AI Assistant Panel */}
      {assistantOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-96 h-[480px] bg-[#0F1722] border border-white/[0.08] rounded-2xl flex flex-col shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-6 duration-300">
          <div className="px-4 py-3 bg-[#07070A] border-b border-white/[0.05] flex justify-between items-center">
            <span className="text-xs font-bold text-white flex items-center gap-1.5">
              <Terminal size={14} className="text-[#67E8F9]" /> AI Admin Assistant
            </span>
            <button onClick={() => setAssistantOpen(false)} className="text-[#9a9a9a]/40 hover:text-white transition-colors">✕</button>
          </div>
          
          <div className="flex-grow p-4 overflow-y-auto space-y-3 custom-scrollbar text-xs">
            {assistantReplies.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`p-3 rounded-xl max-w-[80%] ${
                  msg.sender === 'user'
                    ? 'bg-[#67E8F9]/10 text-[#67E8F9] rounded-tr-none border border-[#67E8F9]/20'
                    : 'bg-[#07070A]/50 text-white rounded-tl-none border border-white/[0.03]'
                }`}>
                  {msg.text}
                </div>
              </div>
            ))}
          </div>

          <form onSubmit={queryAdminAssistant} className="p-3 bg-[#07070A] border-t border-white/[0.05] flex gap-2">
            <input 
              type="text" 
              placeholder="Ask anything about database states..." 
              value={assistantPrompt}
              onChange={(e) => setAssistantPrompt(e.target.value)}
              className="flex-grow bg-[#0F1722] border border-white/[0.05] rounded-xl px-4 py-2 text-xs text-white placeholder-[#9a9a9a]/20 outline-none focus:border-[#67E8F9]"
            />
            <button type="submit" className="px-3 py-2 bg-[#67E8F9] text-[#07070A] hover:bg-[#67E8F9]/90 font-bold rounded-xl text-xs transition-all">
              Ask
            </button>
          </form>
        </div>
      )}

      {/* Command Palette Overlay */}
      {showPalette && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/75 backdrop-blur-sm p-4 pt-24">
          <div className="bg-[#0F1722] w-full max-w-lg rounded-2xl border border-white/[0.08] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-4 bg-[#07070A] border-b border-white/[0.05] flex items-center gap-3">
              <Search className="text-[#9a9a9a]" size={16} />
              <input 
                type="text" 
                placeholder="Search navigational shortcuts..." 
                value={paletteQuery}
                onChange={(e) => setPaletteQuery(e.target.value)}
                className="bg-transparent text-sm text-white placeholder-[#9a9a9a]/30 border-none outline-none w-full"
                autoFocus
              />
              <button onClick={() => setShowPalette(false)} className="text-[#9a9a9a]/40 hover:text-white font-mono text-[10px]">ESC</button>
            </div>
            
            <div className="p-2 max-h-64 overflow-y-auto custom-scrollbar text-xs">
              {filteredPaletteItems.length === 0 ? (
                <p className="text-center text-[#9a9a9a]/30 py-6">No matching actions or navigation shortcuts</p>
              ) : (
                filteredPaletteItems.map((item, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setActiveTab(item.tab as any);
                      setShowPalette(false);
                    }}
                    className="w-full text-left px-4 py-2.5 rounded-xl hover:bg-white/[0.03] text-white hover:text-[#67E8F9] transition-all"
                  >
                    {item.name}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Document Detail Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#0F1722] rounded-2xl border border-white/[0.05] max-w-lg w-full overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-white/[0.05] flex justify-between items-center">
              <h3 className="text-sm font-bold text-white">Document Metadata Detail</h3>
              <button onClick={() => setPreviewDoc(null)} className="text-[#9a9a9a]/40 hover:text-white transition-colors">✕</button>
            </div>
            <div className="p-6 space-y-4 text-xs font-mono">
              <div className="space-y-1">
                <span className="text-[9px] text-[#9a9a9a] uppercase tracking-wider">Document ID</span>
                <p className="text-white bg-[#07070A] p-2 rounded-lg border border-white/[0.05] overflow-x-auto">{previewDoc.document_id}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-[9px] text-[#9a9a9a] uppercase tracking-wider">Title</span>
                  <p className="text-white font-semibold mt-0.5 truncate max-w-[200px]" title={previewDoc.title}>{previewDoc.title}</p>
                </div>
                <div>
                  <span className="text-[9px] text-[#9a9a9a] uppercase tracking-wider">Category</span>
                  <p className="text-white font-semibold mt-0.5 capitalize">{previewDoc.category}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-[9px] text-[#9a9a9a] uppercase tracking-wider">Document Type</span>
                  <p className="text-white font-semibold mt-0.5">{previewDoc.document_type}</p>
                </div>
                <div>
                  <span className="text-[9px] text-[#9a9a9a] uppercase tracking-wider">Version</span>
                  <p className="text-white font-semibold mt-0.5">v{previewDoc.version}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-[9px] text-[#9a9a9a] uppercase tracking-wider">Chunk Count</span>
                  <p className="text-white font-semibold mt-0.5">{previewDoc.chunk_count}</p>
                </div>
                <div>
                  <span className="text-[9px] text-[#9a9a9a] uppercase tracking-wider">Uploaded By</span>
                  <p className="text-white font-semibold mt-0.5">{previewDoc.uploader}</p>
                </div>
              </div>
              <div className="space-y-1">
                <span className="text-[9px] text-[#9a9a9a] uppercase tracking-wider">SHA-256 Hash</span>
                <p className="text-white bg-[#07070A] p-2 rounded-lg border border-white/[0.05] truncate">{previewDoc.sha256}</p>
              </div>
              {previewDoc.error_message && (
                <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-lg space-y-1">
                  <p className="font-semibold uppercase tracking-wider text-[9px]">Pipeline Error</p>
                  <p>{previewDoc.error_message}</p>
                </div>
              )}
            </div>
            <div className="px-6 py-4 bg-[#07070A] border-t border-white/[0.05] flex justify-end">
              <button 
                onClick={() => setPreviewDoc(null)}
                className="px-4 py-2 bg-secondary border border-white/[0.05] hover:bg-hover text-xs font-semibold rounded-lg transition-all text-white"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Version History Drawer */}
      {versionHistoryDoc && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
          <div className="bg-[#0F1722] w-full max-w-md h-full flex flex-col border-l border-white/[0.05] shadow-2xl animate-in slide-in-from-right duration-300">
            <div className="px-6 py-5 border-b border-white/[0.05] flex justify-between items-center">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <History className="text-[#67E8F9]" /> Version Archive
              </h3>
              <button onClick={() => setVersionHistoryDoc(null)} className="text-[#9a9a9a]/40 hover:text-white transition-colors">✕</button>
            </div>
            <div className="px-6 py-3 border-b border-white/[0.02]">
              <p className="text-xs text-[#9a9a9a] font-semibold truncate">File: {versionHistoryDoc}</p>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
              {versionHistoryList.map((doc, index) => (
                <div key={index} className={`bg-[#07070A] rounded-xl p-4 border border-white/[0.03] space-y-2 ${!doc.is_active ? 'opacity-65' : ''}`}>
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-bold text-white font-mono">Version {doc.version}</span>
                    <span className={`px-2 py-0.5 rounded text-[9px] uppercase font-bold tracking-wider font-mono ${
                      doc.is_active ? 'bg-emerald-500/10 text-emerald-500' : 'bg-neutral-500/10 text-[#9a9a9a]'
                    }`}>
                      {doc.is_active ? 'Active' : 'Archived'}
                    </span>
                  </div>
                  <p className="text-[10px] text-[#9a9a9a] font-mono">Uploaded: {new Date(doc.uploaded_at).toLocaleString()}</p>
                  <p className="text-[10px] text-[#9a9a9a] font-mono">By: {doc.uploader}</p>
                  <div className="flex gap-2 justify-end pt-2">
                    <button 
                      onClick={() => setPreviewDoc(doc)}
                      className="px-2.5 py-1 bg-secondary border border-white/[0.05] hover:bg-hover rounded text-[10px] font-semibold text-white"
                    >
                      Details
                    </button>
                    {!doc.is_active && (
                      <button 
                        onClick={async () => {
                          if (confirm(`Are you sure you want to promote Version ${doc.version} back to active?`)) {
                            try {
                              await AXIOS_INSTANCE.post(`/api/admin/knowledge/reindex/${doc.document_id}`);
                              fetchDocuments();
                              fetchAuditLogs();
                              fetchJobs();
                            } catch (e) {
                              console.error(e);
                            }
                          }
                        }}
                        className="px-2.5 py-1 bg-[#67E8F9] text-[#07070A] hover:bg-[#67E8F9]/90 font-bold rounded text-[10px]"
                      >
                        Restore
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default AdminUploadPortal;
