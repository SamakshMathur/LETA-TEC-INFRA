import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Send, Sparkles, Menu, Paperclip,
  ChevronLeft, Folder, Star, Landmark, FileCheck,
  Bookmark, BookmarkCheck, Trash2, Calendar, ShieldCheck, Plus, Square, Upload,
  ArrowLeft, Eye, Mic, MicOff, FileText
} from 'lucide-react';
import axios from 'axios';
import { BASE_URL } from '../config/api';
import { LetaResponse } from '../components/leta';
import { SimpleSearchLoader } from '../components/effects';
import { DocumentViewer } from '../components/documents';

// ─── Interfaces ───────────────────────────────────────────────────────────────

interface Session {
  session_id: string;
  title: string;
  updated_at: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  confidence?: number;
  citations?: string[];
  consulted_sources?: any[];
  current_status?: string;
  isHistory?: boolean;
}

interface OpenDoc {
  id: string;
  url: string;
  title: string;
  page?: number;
  search?: string;
}

interface SavedItem {
  id: string;
  content: string;        // full assistant response
  query: string;          // user question that triggered this response
  title: string;          // auto-generated display title
  date: string;           // ISO timestamp
  type: 'saved' | 'starred';
  domain: string;         // gst | fema | company-law | income-tax
  sessionId?: string;
}

// ─── Repository section config ────────────────────────────────────────────────

type RepoKey = 'saved' | 'starred' | 'notices' | 'bookmarks';

const REPO_SECTIONS: {
  key: RepoKey;
  label: string;
  icon: React.ElementType;
  countLabel: string;
}[] = [
  { key: 'saved',     label: 'Saved Matter Drafts',       icon: Folder,   countLabel: 'Files'   },
  { key: 'starred',   label: 'Starred Advisory Briefs',   icon: Star,     countLabel: 'Starred' },
  { key: 'notices',   label: 'Department Notice Files',   icon: Landmark, countLabel: 'Notices' },
  { key: 'bookmarks', label: 'Custom Reference Bookmarks',icon: Bookmark, countLabel: 'Refs'    },
];

const STORAGE_KEY = 'leta_repository';

// ─── Main Component ───────────────────────────────────────────────────────────

const LetaWorkspace: React.FC = () => {
  const { domainId = 'gst' } = useParams<{ domainId: string }>();

  // Active configurations based on current domain
  const domainConfig = {
    gst: {
      title: 'LETA GST',
      subtitle: 'Professional GST Intelligence Workspace',
      contextDesc: 'GST compliance or notice issue',
      placeholder: 'Enter your query, notice issue, or drafting requirement...',
      suggestedQueries: [
        { title: 'Reply to GST Notice', query: 'What is the reply structure for delayed GSTR-3B penalty under Section 47?' },
        { title: 'Refund Rejection Assistance', query: 'Draft an appeal outline for GST refund rejection under Section 54.' },
        { title: 'Input Tax Credit Clarification', query: 'Is input tax credit available on factory warehouse construction under Section 17(5)?' },
        { title: 'Penalty Notice Drafting', query: 'How to draft a representation letter for mitigation of interest/penalty under Section 50?' }
      ],
      drafts: [
        { name: 'GSTR-3B Notice Reply Draft', section: 'Sec 47' },
        { name: 'Rule 86A Ledger Blocking Appeal', section: 'Rule 86A' },
        { name: 'Sec 73 SCN Response Outline', section: 'Sec 73' }
      ]
    },
    fema: {
      title: 'LETA FEMA',
      subtitle: 'Professional FEMA Compliance Workspace',
      contextDesc: 'cross-border regulatory query',
      placeholder: 'Describe your FEMA compliance, regulatory issue, or cross-border transaction...',
      suggestedQueries: [
        { title: 'FDI Compliance Review', query: 'What are the reporting requirements and timelines for FDI inflows under FEMA?' },
        { title: 'Export Realization Advice', query: 'Explain the rules for export realization and repatriation of foreign exchange.' },
        { title: 'Overseas Direct Investment Rules', query: 'Draft a summary of regulatory guidelines for Overseas Direct Investment (ODI).' },
        { title: 'External Commercial Borrowings', query: 'What is the compliance checklist for raising External Commercial Borrowings (ECB)?' }
      ],
      drafts: [
        { name: 'FDI Compliance Advisory Format', section: 'FDI Regs' },
        { name: 'ODI Reporting Representation Letter', section: 'ODI Rule' },
        { name: 'ECB Approval Application Draft', section: 'ECB Frame' }
      ]
    },
    'company-law': {
      title: 'LETA Company Law',
      subtitle: 'Professional Company Law Compliance Workspace',
      contextDesc: 'secretarial or corporate filing query',
      placeholder: 'Describe your ROC filing, board procedure, or corporate governance requirement...',
      suggestedQueries: [
        { title: 'ROC Filing Assistance', query: 'What is the step-by-step procedure for condonation of delay in filing form MGT-14?' },
        { title: 'Director Disqualifications', query: 'Draft an advisory memo on director disqualifications under Section 164(2).' },
        { title: 'Board Resolution Structure', query: 'How do we structure a board resolution for corporate borrowing under Section 179(3)?' },
        { title: 'Related Party Transactions', query: 'What are the disclosure requirements for related party transactions under Section 188?' }
      ],
      drafts: [
        { name: 'ROC Delay Condonation Petition', section: 'Sec 137' },
        { name: 'Director Disqualification Board Memo', section: 'Sec 164' },
        { name: 'Sec 188 RPT Audit Checklist', section: 'Sec 188' }
      ]
    },
    'income-tax': {
      title: 'LETA Income Tax',
      subtitle: 'Professional Income Tax Workspace',
      contextDesc: 'litigation, scrutiny, or assessment query',
      placeholder: 'Describe your scrutiny notice, direct tax query, or litigation draft requirements...',
      suggestedQueries: [
        { title: 'Scrutiny Notice Advice', query: 'What are the key defenses for a scrutiny notice issued under Section 143(2) for cash deposits?' },
        { title: 'Assessment Appeal Guide', query: 'Draft an appeal outline to CIT(Appeals) against assessment order under Section 147.' },
        { title: 'Sec 56(2)(x) Inflow Taxability', query: 'Explain the tax implications of shares received at less than Fair Market Value under Section 56(2)(x).' },
        { title: 'Delay Condonation Filing', query: 'How to file a delay condonation petition under Section 119(2)(b) for refund claims?' }
      ],
      drafts: [
        { name: 'Sec 143(2) Scrutiny Reply Format', section: 'Sec 143(2)' },
        { name: 'CIT Appeal Grounds of Appeal Form', section: 'Sec 246A' },
        { name: 'Sec 119 Delay Condonation Appeal', section: 'Sec 119' }
      ]
    }
  }[domainId] || {
    title: 'LETA Workspace',
    subtitle: 'Professional Legal & Advisory Workspace',
    contextDesc: 'notice or statutory query',
    placeholder: 'Describe the issue you are facing...',
    suggestedQueries: [
      { title: 'Statutory Reply Format', query: 'Provide a structured legal reply outline for statutory notices.' }
    ],
    drafts: []
  };

  // ─── Core State ─────────────────────────────────────────────────────────────
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);

  // Document Viewer splits
  const [openDocuments, setOpenDocuments] = useState<OpenDoc[]>([]);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);

  // ─── Repository State ────────────────────────────────────────────────────────
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [activeRepo, setActiveRepo] = useState<RepoKey | null>(null);   // which repo section is open
  const [viewingItem, setViewingItem] = useState<SavedItem | null>(null); // full-view modal

  // ─── Refs ────────────────────────────────────────────────────────────────────
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const wakeLockRef = useRef<WakeLockSentinel | null>(null);
  const pendingRetryRef = useRef<{ query: string; file: File | null } | null>(null);
  const isActiveQueryRef = useRef(false);

  // ─── Voice Recording State ────────────────────────────────────────────────────
  const [isRecording, setIsRecording]       = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [audioLevels, setAudioLevels]       = useState<number[]>(Array(28).fill(0));
  const [micError, setMicError]             = useState<string | null>(null);

  // Voice refs
  const isRecordingRef    = useRef(false);
  const mediaRecorderRef  = useRef<MediaRecorder | null>(null);
  const audioChunksRef    = useRef<Blob[]>([]);
  const audioCtxRef       = useRef<AudioContext | null>(null);
  const animFrameRef      = useRef<number | null>(null);
  const streamRef         = useRef<MediaStream | null>(null);
  const recordingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const formatDuration = (secs: number) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  // ── Tear-down helper (called on stop AND on unmount) ──────────────────────────
  const _cleanupAudio = () => {
    if (animFrameRef.current)  { cancelAnimationFrame(animFrameRef.current); animFrameRef.current = null; }
    if (audioCtxRef.current)   { try { audioCtxRef.current.close(); } catch {} audioCtxRef.current = null; }
    if (streamRef.current)     { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    if (recordingTimerRef.current) { clearInterval(recordingTimerRef.current); recordingTimerRef.current = null; }
    setAudioLevels(Array(28).fill(0));
  };

  // ── Stop recording + send to Whisper ─────────────────────────────────────────
  const stopVoiceRecording = () => {
    if (!isRecordingRef.current) return;
    isRecordingRef.current = false;
    setIsRecording(false);

    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      _cleanupAudio();
      return;
    }

    // onstop fires after the final chunk is flushed
    recorder.onstop = async () => {
      _cleanupAudio();
      const chunks = audioChunksRef.current;
      if (!chunks.length) return;

      const mimeType = recorder.mimeType || 'audio/webm';
      const audioBlob = new Blob(chunks, { type: mimeType });
      audioChunksRef.current = [];

      // ── Send to backend Whisper endpoint ─────────────────────────────────
      setIsTranscribing(true);
      try {
        const formData = new FormData();
        // Use .webm extension — Whisper accepts it natively
        formData.append('file', audioBlob, 'recording.webm');

        const res = await fetch(`${BASE_URL}/api/transcribe`, {
          method: 'POST',
          body: formData,
        });

        if (res.ok) {
          const data = await res.json();
          const text = (data.transcript || '').trim();
          if (text) {
            setQuery(prev => prev ? `${prev} ${text}` : text);
            // Resize textarea
            requestAnimationFrame(() => {
              const el = textareaRef.current;
              if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 300) + 'px'; }
            });
          }
        } else {
          const err = await res.json().catch(() => ({ detail: 'Transcription failed' }));
          setMicError(err.detail || 'Transcription failed — please try again.');
        }
      } catch {
        setMicError('Could not reach the transcription service. Is the backend running?');
      } finally {
        setIsTranscribing(false);
      }
    };

    recorder.stop();
  };

  // ── Start recording ───────────────────────────────────────────────────────────
  const startVoiceRecording = async () => {
    if (isRecordingRef.current) { stopVoiceRecording(); return; }
    setMicError(null);

    // Request microphone access
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      streamRef.current = stream;
    } catch {
      setMicError('Microphone access denied — click the 🔒 icon in the address bar and allow microphone.');
      return;
    }

    // ── Live waveform via Web Audio API ──────────────────────────────────────
    try {
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 64;
      audioCtx.createMediaStreamSource(stream).connect(analyser);
      const dataArr = new Uint8Array(analyser.frequencyBinCount);
      const drawFrame = () => {
        analyser.getByteFrequencyData(dataArr);
        setAudioLevels(Array.from(dataArr.slice(0, 28)).map(v => v / 255));
        animFrameRef.current = requestAnimationFrame(drawFrame);
      };
      drawFrame();
    } catch { /* waveform is optional — continue without it */ }

    // ── MediaRecorder — prefer opus/webm (smallest, widest Whisper support) ──
    const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/ogg']
      .find(t => MediaRecorder.isTypeSupported(t)) || '';

    const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    mediaRecorderRef.current = recorder;
    audioChunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunksRef.current.push(e.data);
    };

    recorder.start(250); // flush every 250 ms so we always have data on stop

    isRecordingRef.current = true;
    setIsRecording(true);
    setRecordingDuration(0);
    recordingTimerRef.current = setInterval(() => setRecordingDuration(d => d + 1), 1000);
  };

  // Cleanup on unmount
  useEffect(() => () => {
    isRecordingRef.current = false;
    mediaRecorderRef.current?.stop();
    _cleanupAudio();
  }, []);

  // ─── Persistence: load & sync savedItems ─────────────────────────────────────
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setSavedItems(JSON.parse(raw));
    } catch {}
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(savedItems));
    } catch {}
  }, [savedItems]);

  // ─── Repository helpers ───────────────────────────────────────────────────────

  const isNoticeItem = (item: SavedItem): boolean =>
    /notice|scn|drc|asmt|appeal|show cause|demand|adjudication|drc-01|drc-07/i
      .test(item.query + ' ' + item.content);

  const getRepoItems = (key: RepoKey): SavedItem[] => {
    switch (key) {
      case 'saved':     return savedItems.filter(i => i.type === 'saved');
      case 'starred':   return savedItems.filter(i => i.type === 'starred');
      case 'notices':   return savedItems.filter(isNoticeItem);
      case 'bookmarks': return [...savedItems].reverse(); // newest first
      default:          return [];
    }
  };

  const repoCounts: Record<RepoKey, number> = {
    saved:     savedItems.filter(i => i.type === 'saved').length,
    starred:   savedItems.filter(i => i.type === 'starred').length,
    notices:   savedItems.filter(isNoticeItem).length,
    bookmarks: savedItems.length,
  };

  const getSaveStatus = (content: string): 'saved' | 'starred' | null => {
    const item = savedItems.find(i => i.content === content);
    return item ? item.type : null;
  };

  const generateItemTitle = (query: string, content: string): string => {
    if (query && query.trim()) {
      const q = query.trim();
      return q.length > 55 ? q.substring(0, 53) + '...' : q;
    }
    const first = content.split('\n').find(l => l.replace(/[#*`\s]/g, '').length > 5) || '';
    const clean = first.replace(/[#*`]/g, '').trim();
    return clean.length > 55 ? clean.substring(0, 53) + '...' : clean || 'Advisory Note';
  };

  const handleSaveMessage = (msg: Message, idx: number, type: 'saved' | 'starred') => {
    const userQuery = messages[idx - 1]?.content || '';
    const existing = savedItems.find(i => i.content === msg.content);

    if (existing) {
      if (existing.type === type) {
        // Toggle off — remove
        setSavedItems(prev => prev.filter(i => i.id !== existing.id));
      } else {
        // Switch type (saved ↔ starred)
        setSavedItems(prev => prev.map(i => i.id === existing.id ? { ...i, type } : i));
      }
    } else {
      const newItem: SavedItem = {
        id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        content: msg.content,
        query: userQuery,
        title: generateItemTitle(userQuery, msg.content),
        date: new Date().toISOString(),
        type,
        domain: domainId,
        sessionId: currentSessionId || undefined,
      };
      setSavedItems(prev => [...prev, newItem]);
    }
  };

  const handleRemoveItem = (id: string) => {
    setSavedItems(prev => prev.filter(i => i.id !== id));
    if (viewingItem?.id === id) setViewingItem(null);
  };

  // ─── Domain label for saved items ────────────────────────────────────────────
  const DOMAIN_LABEL: Record<string, string> = {
    gst:           'GST',
    fema:          'FEMA',
    'company-law': 'Company Law',
    'income-tax':  'Income Tax',
  };

  // ─── Quick Take helper ────────────────────────────────────────────────────────

  /** True when the response is a Quick Take (has POSITION / CONFIDENCE markers) */
  const isQuickTake = (content: string): boolean =>
    /\*\*POSITION:\*\*|POSITION:|CONFIDENCE:|✅|⚠️|🔴/.test(content);

  // ─── UI helpers ───────────────────────────────────────────────────────────────
  const autoResize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 300) + 'px';
  };

  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  useEffect(() => { scrollToBottom(); }, [messages, isLoading]);

  // ─── Sessions ────────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 60000);
    return () => clearInterval(interval);
  }, [currentSessionId]);

  useEffect(() => {
    setMessages([]);
    setCurrentSessionId(null);
    setQuery('');
    setOpenDocuments([]);
    setActiveDocId(null);
  }, [domainId]);

  // ─── Wake Lock + Visibility auto-retry ────────────────────────────────────────
  // Acquires a screen wake lock while a query is in-flight so the laptop
  // sleep / screen timeout cannot pause the stream mid-response.
  const acquireWakeLock = async () => {
    try {
      if ('wakeLock' in navigator) {
        wakeLockRef.current = await (navigator as any).wakeLock.request('screen');
      }
    } catch { /* silently ignore — not critical */ }
  };

  const releaseWakeLock = async () => {
    try {
      if (wakeLockRef.current) {
        await wakeLockRef.current.release();
        wakeLockRef.current = null;
      }
    } catch { /* ignore */ }
  };

  // When the page becomes visible again (user opens lid / wakes screen) and we
  // detect the stream was forcibly interrupted, re-acquire wake lock (browser
  // auto-releases it on hide) and replay the pending query.
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        // Re-acquire wake lock if a query is still active (browser releases it on hide)
        if (isActiveQueryRef.current) {
          acquireWakeLock();
        }
        // If we were processing when the screen went to sleep, auto-retry
        if (pendingRetryRef.current) {
          const { query: retryQuery, file: retryFile } = pendingRetryRef.current;
          pendingRetryRef.current = null;
          setSelectedFile(retryFile);
          handleAsk(retryQuery);
        }
      }
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  const fetchSessions = async () => {
    try {
      const res = await axios.get(`${BASE_URL}/api/sessions/list`);
      setSessions(res.data);
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    try {
      setIsLoading(true);
      setCurrentSessionId(sessionId);
      const res = await axios.get(`${BASE_URL}/api/sessions/${sessionId}`);
      setMessages(res.data.messages.map((msg: any) => ({
        role: msg.role,
        content: msg.content,
        confidence: 1.0,
        citations: [],
        consulted_sources: msg.sources || [],
        isHistory: true,
      })));
      setIsLoading(false);
    } catch (err) {
      console.error('Failed to load session:', err);
      setIsLoading(false);
    }
  };

  const handleNewSession = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setQuery('');
    setSelectedFile(null);
    setIsLoading(false);
  };

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await axios.delete(`${BASE_URL}/api/sessions/${id}`);
      fetchSessions();
      if (currentSessionId === id) handleNewSession();
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    isActiveQueryRef.current = false;
    pendingRetryRef.current = null;
    releaseWakeLock();
    setIsStreaming(false);
    setIsLoading(false);
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ─── Main ask handler ─────────────────────────────────────────────────────────
  const handleAsk = async (queryOverride?: string) => {
    const activeQuery = typeof queryOverride === 'string' ? queryOverride : query;
    if (!activeQuery.trim() && !selectedFile) return;

    const userMsg: Message = { role: 'user', content: activeQuery || (selectedFile ? `[Attached: ${selectedFile.name}]` : '') };
    const newAiMsg: Message = { role: 'assistant', content: '', confidence: 0.95, citations: [] };

    setMessages(prev => [...prev, userMsg, newAiMsg]);
    setQuery('');
    setIsLoading(true);
    setIsStreaming(false);
    if (textareaRef.current) textareaRef.current.style.height = '90px';

    // Prevent screen sleep from killing the stream
    isActiveQueryRef.current = true;
    pendingRetryRef.current = { query: activeQuery, file: selectedFile };
    await acquireWakeLock();

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      let activeSessionId = currentSessionId;
      if (!activeSessionId) {
        let title = activeQuery;
        if (title.length > 40) title = title.substring(0, 38) + '...';

        const lower = activeQuery.toLowerCase();
        if (domainId === 'gst') {
          if (lower.includes('refund')) title = 'GST Refund Claim Matter';
          else if (lower.includes('itc') || lower.includes('input tax')) title = 'ITC Eligibility Verification';
          else if (lower.includes('notice') || lower.includes('73') || lower.includes('scn')) title = 'Section 73 SCN Representation';
          else if (lower.includes('ledger') || lower.includes('86a') || lower.includes('block')) title = 'Rule 86A Credit Blocking Appeal';
          else if (lower.includes('penalty') || lower.includes('47')) title = 'Section 47 Delayed Filing Review';
        } else if (domainId === 'fema') {
          if (lower.includes('fdi') || lower.includes('investment')) title = 'FDI Regulatory Compliance Review';
          else if (lower.includes('export')) title = 'Export Repatriation Advisory';
        } else if (domainId === 'company-law') {
          if (lower.includes('roc') || lower.includes('delay')) title = 'ROC Filing Delay Condonation';
          else if (lower.includes('director') || lower.includes('164')) title = 'Director Disqualification Board Memo';
        } else if (domainId === 'income-tax') {
          if (lower.includes('scrutiny') || lower.includes('143')) title = 'Section 143(2) Scrutiny Reply';
          else if (lower.includes('appeal')) title = 'CIT(Appeals) Assessment Protest';
        }

        try {
          const sessionRes = await axios.post(`${BASE_URL}/api/sessions/new`, { title });
          activeSessionId = sessionRes.data.session_id;
          setCurrentSessionId(activeSessionId);
        } catch {
          // Session creation failed (CORS or backend unreachable) — proceed without session tracking
        }
      }

      if (selectedFile) {
        // File upload path: keep SSE streaming for /ask-with-file
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('question', userMsg.content);
        if (activeSessionId) formData.append('session_id', activeSessionId);
        const fileRes = await fetch(`${BASE_URL}/ask-with-file`, { method: 'POST', body: formData, signal: controller.signal });

        if (!fileRes.ok) throw new Error(`Server returned status: ${fileRes.status}`);

        const reader = fileRes.body?.getReader();
        const decoder = new TextDecoder('utf-8');
        setIsLoading(false);
        setIsStreaming(true);

        if (!reader) throw new Error('Response stream unavailable');

        let buffer = '';
        const appendChunk = (text: string) => {
          setMessages(prev => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last.role === 'assistant') {
              next[next.length - 1] = { ...last, content: last.content + text };
            }
            return next;
          });
        };

        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            if (buffer) appendChunk(buffer);
            break;
          }
          buffer += decoder.decode(value, { stream: true });

          let processed = true;
          while (processed) {
            processed = false;

            if (buffer.includes('__STATUS__:')) {
              const si = buffer.indexOf('__STATUS__:');
              const ei = buffer.indexOf('__END_STATUS__', si);
              if (ei !== -1) {
                if (buffer.substring(0, si)) appendChunk(buffer.substring(0, si));
                try {
                  const d = JSON.parse(buffer.substring(si + '__STATUS__:'.length, ei));
                  setMessages(prev => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last.role === 'assistant') {
                      next[next.length - 1] = { ...last, current_status: d.msg };
                    }
                    return next;
                  });
                } catch {}
                buffer = buffer.substring(ei + '__END_STATUS__'.length);
                processed = true;
                continue;
              }
            }

            if (buffer.includes('__METADATA__:')) {
              const si = buffer.indexOf('__METADATA__:');
              const ei = buffer.indexOf('__END_METADATA__', si);
              if (ei !== -1) {
                if (buffer.substring(0, si)) appendChunk(buffer.substring(0, si));
                try {
                  const meta = JSON.parse(buffer.substring(si + '__METADATA__:'.length, ei));
                  setMessages(prev => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last.role === 'assistant') {
                      next[next.length - 1] = { ...last, consulted_sources: meta.sources };
                    }
                    return next;
                  });
                } catch {}
                buffer = buffer.substring(ei + '__END_METADATA__'.length);
                processed = true;
                continue;
              }
            }

            const triggers = ['__STATUS__:', '__END_STATUS__', '__METADATA__:', '__END_METADATA__', '__'];
            let safePoint = buffer.length;
            const fsi = buffer.indexOf('__STATUS__:');
            const fmi = buffer.indexOf('__METADATA__:');
            if (fsi !== -1) safePoint = Math.min(safePoint, fsi);
            if (fmi !== -1) safePoint = Math.min(safePoint, fmi);
            for (const t of triggers) {
              const li = buffer.lastIndexOf(t);
              if (li !== -1 && li + t.length > buffer.length) {
                safePoint = Math.min(safePoint, li);
              }
            }
            if (safePoint > 0) {
              appendChunk(buffer.substring(0, safePoint));
              buffer = buffer.substring(safePoint);
            }
          }
        }

        setIsStreaming(false);
      } else {
        // Text query path: use /ask streaming (SSE) so long drafts don't hit API Gateway timeout
        const streamRes = await fetch(`${BASE_URL}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: userMsg.content, session_id: activeSessionId, intent: 'general' }),
          signal: controller.signal,
        });

        if (!streamRes.ok) throw new Error(`Server returned status: ${streamRes.status}`);

        const reader = streamRes.body?.getReader();
        const decoder = new TextDecoder('utf-8');
        setIsLoading(false);
        setIsStreaming(true);

        if (!reader) throw new Error('Response stream unavailable');

        let buffer = '';
        const appendChunk = (text: string) => {
          setMessages(prev => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last.role === 'assistant') {
              next[next.length - 1] = { ...last, content: last.content + text };
            }
            return next;
          });
        };

        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            if (buffer) appendChunk(buffer);
            break;
          }
          buffer += decoder.decode(value, { stream: true });

          let processed = true;
          while (processed) {
            processed = false;

            if (buffer.includes('__STATUS__:')) {
              const si = buffer.indexOf('__STATUS__:');
              const ei = buffer.indexOf('__END_STATUS__', si);
              if (ei !== -1) {
                if (buffer.substring(0, si)) appendChunk(buffer.substring(0, si));
                try {
                  const d = JSON.parse(buffer.substring(si + '__STATUS__:'.length, ei));
                  setMessages(prev => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last.role === 'assistant') {
                      next[next.length - 1] = { ...last, current_status: d.msg };
                    }
                    return next;
                  });
                } catch {}
                buffer = buffer.substring(ei + '__END_STATUS__'.length);
                processed = true;
                continue;
              }
            }

            if (buffer.includes('__METADATA__:')) {
              const si = buffer.indexOf('__METADATA__:');
              const ei = buffer.indexOf('__END_METADATA__', si);
              if (ei !== -1) {
                if (buffer.substring(0, si)) appendChunk(buffer.substring(0, si));
                try {
                  const meta = JSON.parse(buffer.substring(si + '__METADATA__:'.length, ei));
                  setMessages(prev => {
                    const next = [...prev];
                    const last = next[next.length - 1];
                    if (last.role === 'assistant') {
                      next[next.length - 1] = { ...last, consulted_sources: meta.sources };
                    }
                    return next;
                  });
                } catch {}
                buffer = buffer.substring(ei + '__END_METADATA__'.length);
                processed = true;
                continue;
              }
            }

            const triggers = ['__STATUS__:', '__END_STATUS__', '__METADATA__:', '__END_METADATA__', '__'];
            let safePoint = buffer.length;
            const fsi = buffer.indexOf('__STATUS__:');
            const fmi = buffer.indexOf('__METADATA__:');
            if (fsi !== -1) safePoint = Math.min(safePoint, fsi);
            if (fmi !== -1) safePoint = Math.min(safePoint, fmi);
            for (const t of triggers) {
              const li = buffer.lastIndexOf(t);
              if (li !== -1 && li + t.length > buffer.length) {
                safePoint = Math.min(safePoint, li);
              }
            }
            if (safePoint > 0) {
              appendChunk(buffer.substring(0, safePoint));
              buffer = buffer.substring(safePoint);
            }
          }
        }

        setIsStreaming(false);
      }

      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      abortControllerRef.current = null;
      isActiveQueryRef.current = false;
      pendingRetryRef.current = null;
      releaseWakeLock();
      fetchSessions();
    } catch (error: any) {
      isActiveQueryRef.current = false;
      releaseWakeLock();
      if ((error as any)?.name === 'AbortError') {
        pendingRetryRef.current = null;
        setIsStreaming(false);
        return;
      }
      // If the error looks like a network interruption (screen sleep / tab hidden),
      // keep pendingRetryRef so the visibilitychange handler can auto-retry.
      const isNetworkInterrupt = error?.name === 'TypeError' || error?.message?.includes('network') || error?.message?.includes('Failed to fetch');
      if (!isNetworkInterrupt) pendingRetryRef.current = null;
      console.error('LETA API Error:', error);
      setMessages(prev => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last.role === 'assistant') {
          next[next.length - 1] = { ...last, content: last.content + `\n\n[Advisory Workspace Error]: Unable to synthesize draft guidance. Please check connection.` };
        }
        return next;
      });
      setIsLoading(false);
      setIsStreaming(false);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDocumentClick = ({ url, page, search, title }: { url: string, page?: number, search?: string, title?: string }) => {
    let fullUrl = url.startsWith('/api/') ? BASE_URL + url : url;
    const derivedTitle = title
      || (() => { try { return decodeURIComponent(fullUrl.split('filename=')[1]?.split('&')[0] || ''); } catch { return ''; } })()
      || 'Statutory Reference';
    const id = fullUrl;
    const existing = openDocuments.find(d => d.id === id);
    if (!existing) {
      setOpenDocuments(prev => [...prev, { id, url: fullUrl, title: derivedTitle, page, search }]);
    } else {
      setOpenDocuments(prev => prev.map(d => d.id === id ? { ...d, page, search } : d));
    }
    setActiveDocId(id);
  };

  const closeDocument = (id: string) => {
    setOpenDocuments(prev => {
      const next = prev.filter(d => d.id !== id);
      if (activeDocId === id) {
        setActiveDocId(next.length > 0 ? next[next.length - 1].id : null);
      }
      return next;
    });
  };

  // ─── Session card metadata ───────────────────────────────────────────────────
  const getSessionDetails = (title: string) => {
    const cleanTitle = title.trim();
    let type = 'Statutory Consultation';
    let provision = 'Act Gen';
    let status = 'Consulting';
    let statusColor = '#3B82F6';

    const lower = cleanTitle.toLowerCase();
    if (domainId === 'gst') {
      if (lower.includes('refund')) { type = 'GST Refund Appeal'; provision = 'Sec 54'; status = 'Draft Ready'; statusColor = '#22C55E'; }
      else if (lower.includes('itc') || lower.includes('eligible') || lower.includes('16(4)')) { type = 'ITC Audit Review'; provision = 'Sec 16(4)'; status = 'Advisory Signed'; statusColor = '#67E8F9'; }
      else if (lower.includes('73') || lower.includes('notice') || lower.includes('scn')) { type = 'Sec 73 SCN Response'; provision = 'Section 73'; status = 'Vetting Needed'; statusColor = '#F59E0B'; }
      else if (lower.includes('86a') || lower.includes('block') || lower.includes('ledger')) { type = 'Ledger Blocking Contest'; provision = 'Rule 86A'; status = 'Active Workspace'; statusColor = '#EC4899'; }
      else if (lower.includes('penalty') || lower.includes('47')) { type = 'Section 47 Penalty'; provision = 'Section 47'; status = 'Case Closed'; statusColor = '#6B7280'; }
    } else if (domainId === 'fema') {
      type = 'FEMA Advisory'; provision = 'FEMA Sec 6';
      if (lower.includes('fdi')) { type = 'FDI Policy Clearance'; provision = 'FDI Schedule'; status = 'Verification Ok'; statusColor = '#22C55E'; }
      else if (lower.includes('export')) { type = 'Export Repatriation'; provision = 'Section 8'; status = 'Under Audit'; statusColor = '#F59E0B'; }
    } else if (domainId === 'company-law') {
      type = 'ROC Corporate Compliance'; provision = 'CA 2013';
      if (lower.includes('condonation') || lower.includes('delay')) { type = 'Delay Condonation filing'; provision = 'Sec 137'; status = 'In Consultation'; statusColor = '#EC4899'; }
      else if (lower.includes('director') || lower.includes('164')) { type = 'Board Director Briefing'; provision = 'Sec 164'; status = 'Brief Completed'; statusColor = '#67E8F9'; }
    } else if (domainId === 'income-tax') {
      type = 'Scrutiny Defense'; provision = 'ITA 1961';
      if (lower.includes('143')) { type = '143(2) Response Prep'; provision = 'Sec 143(2)'; status = 'Active Scrutiny'; statusColor = '#EC4899'; }
      else if (lower.includes('appeal')) { type = 'Assessment Appeal grounds'; provision = 'Sec 246A'; status = 'Draft Signed'; statusColor = '#22C55E'; }
    }

    if (type === 'Statutory Consultation' && cleanTitle) {
      type = cleanTitle.length > 25 ? cleanTitle.substring(0, 22) + '...' : cleanTitle;
    }

    return { type, provision, status, statusColor };
  };

  // ─── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="h-screen w-screen flex flex-col bg-[#000000] text-sm font-body overflow-hidden">

      {/* ── TOP HEADER NAVBAR ──────────────────────────────────────────────────── */}
      <header className="h-[72px] flex-shrink-0 flex items-center justify-between px-6 bg-[#000000] border-b border-[#4FB7C5]/10 relative z-20">
        <div className="flex items-center gap-4">
          {/* Brand mark */}
          <img
            src="/LETA_WHITE_ON_BLACK_4K.png"
            alt="LETA"
            className="h-8 w-8 object-contain flex-shrink-0"
            style={{ mixBlendMode: 'screen' }}
          />
          <div className="h-4 w-[1px] bg-white/[0.06]" />
          <Link
            to={`/${domainId}`}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/[0.05] bg-white/[0.01] text-xs hover:text-white hover:border-[#4FB7C5]/30 transition-colors"
          >
            <ChevronLeft size={14} />
            Back to Dashboard
          </Link>
          <div className="h-4 w-[1px] bg-white/[0.06]" />
          <div>
            <h1 className="font-display font-bold text-base text-white tracking-tight leading-none">
              {domainConfig.title}
            </h1>
            <span className="text-[11px] font-mono tracking-wide text-[#6B7280]">
              {domainConfig.subtitle}
            </span>
          </div>
        </div>

      </header>

      {/* ── WORKSPACE BODY ────────────────────────────────────────────────────────── */}
      <div className="flex-grow flex flex-row overflow-hidden relative">

        {/* ── LEFT SIDEBAR ─────────────────────────────────────────────────────── */}
        <aside
          className="h-full flex flex-col border-r border-[#4FB7C5]/10 bg-[#000000] flex-shrink-0 transition-all duration-300 overflow-hidden relative z-10"
          style={{ width: isSidebarOpen ? '320px' : '0px' }}
        >
          {/* New Consultation trigger */}
          <div className="p-4 flex-shrink-0 border-b border-[#4FB7C5]/10">
            {activeRepo ? (
              /* Back button when repository panel is open */
              <button
                onClick={() => setActiveRepo(null)}
                className="w-full flex items-center gap-2 py-3 rounded-xl font-sans font-semibold uppercase tracking-wider text-[10px] transition-all duration-200 text-[#4FB7C5] border border-[#4FB7C5]/20 hover:bg-[#4FB7C5]/5"
              >
                <ArrowLeft className="w-3.5 h-3.5 ml-3" />
                Back to Consultations
              </button>
            ) : (
              <button
                onClick={handleNewSession}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl font-sans font-semibold uppercase tracking-wider text-[10px] transition-all duration-200 text-black bg-[#4FB7C5] hover:bg-[#3EA6B4]"
              >
                <Plus className="w-4 h-4" />
                New Consultation
              </button>
            )}
          </div>

          {/* Sidebar content — conditional on activeRepo */}
          <div className="flex-grow min-h-0 overflow-y-auto px-3 py-4 space-y-4 scrollbar-thin">

            {/* ── REPOSITORY PANEL VIEW ─────────────────────────────────────── */}
            <AnimatePresence mode="wait">
              {activeRepo ? (
                <motion.div
                  key="repo-panel"
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -12 }}
                  transition={{ duration: 0.18 }}
                >
                  {/* Section header */}
                  <div className="flex items-center gap-2 px-2 mb-3">
                    {(() => {
                      const sec = REPO_SECTIONS.find(s => s.key === activeRepo)!;
                      return (
                        <>
                          {React.createElement(sec.icon, { size: 13, className: 'text-[#4FB7C5]' })}
                          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#4FB7C5]">
                            {sec.label}
                          </span>
                        </>
                      );
                    })()}
                  </div>

                  {/* Item list */}
                  {getRepoItems(activeRepo).length === 0 ? (
                    <div className="text-center py-10 px-4 text-xs text-[#475569] font-mono border border-dashed border-white/[0.03] rounded-xl">
                      <div className="mb-2 text-2xl opacity-30">
                        {activeRepo === 'starred' ? '★' : '📁'}
                      </div>
                      Nothing {activeRepo === 'starred' ? 'starred' : 'saved'} yet.
                      <br />
                      Use the{' '}
                      <span className="text-[#4FB7C5]">
                        {activeRepo === 'starred' ? '★ Star' : '⊡ Save'}
                      </span>{' '}
                      button on any LETA response.
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {getRepoItems(activeRepo).map(item => (
                        <div
                          key={item.id}
                          className="group relative p-3.5 rounded-xl border border-white/[0.03] bg-white/[0.01] hover:bg-[#131D2B] hover:border-[#4FB7C5]/20 transition-all duration-150 cursor-pointer"
                          onClick={() => setViewingItem(item)}
                        >
                          {/* Type badge */}
                          <div className="flex items-center justify-between mb-1.5">
                            <span
                              className="text-[9px] font-mono px-1.5 py-0.5 rounded-full border"
                              style={item.type === 'starred'
                                ? { color: '#FCD34D', borderColor: 'rgba(252,211,77,0.2)', background: 'rgba(252,211,77,0.06)' }
                                : { color: '#4FB7C5', borderColor: 'rgba(79,183,197,0.2)', background: 'rgba(79,183,197,0.06)' }
                              }
                            >
                              {item.type === 'starred' ? '★ Starred' : '⊡ Saved'}
                            </span>
                            <span className="text-[9px] font-mono text-[#374151] uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/[0.02]">
                              {DOMAIN_LABEL[item.domain] || item.domain}
                            </span>
                          </div>

                          {/* Title */}
                          <p className="text-xs font-semibold text-[#A1AAB8] group-hover:text-white transition-colors leading-snug line-clamp-2 mb-2">
                            {item.title}
                          </p>

                          {/* Date + View hint */}
                          <div className="flex items-center justify-between">
                            <span className="text-[9px] font-mono text-[#374151] flex items-center gap-1">
                              <Calendar size={9} />
                              {new Date(item.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                            </span>
                            <span className="text-[9px] font-mono text-[#4FB7C5] opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5">
                              <Eye size={9} /> View
                            </span>
                          </div>

                          {/* Delete button */}
                          <button
                            onClick={e => { e.stopPropagation(); handleRemoveItem(item.id); }}
                            className="absolute top-2.5 right-2.5 opacity-0 group-hover:opacity-100 p-1 rounded-md text-[#374151] hover:text-[#EF4444] hover:bg-red-500/10 transition-all"
                            title="Remove from repository"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </motion.div>
              ) : (
                /* ── NORMAL SIDEBAR VIEW ────────────────────────────────────── */
                <motion.div
                  key="normal-sidebar"
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 12 }}
                  transition={{ duration: 0.18 }}
                  className="space-y-4"
                >
                  {/* Session list */}
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-[0.2em] px-2 text-[#6B7280] block mb-2.5">
                      Saved Consultations
                    </span>
                    <div className="space-y-2">
                      {sessions.length === 0 ? (
                        <div className="text-center py-8 text-xs text-[#475569] font-mono border border-dashed border-white/[0.03] rounded-xl">
                          No consultation history
                        </div>
                      ) : (
                        sessions.map(session => {
                          const meta = getSessionDetails(session.title);
                          const isSelected = currentSessionId === session.session_id;
                          return (
                            <div
                              key={session.session_id}
                              onClick={() => handleSelectSession(session.session_id)}
                              className={`group p-3.5 rounded-xl cursor-pointer border transition-all duration-200 relative ${
                                isSelected
                                  ? 'bg-[#131D2B] border-[#4FB7C5]/30'
                                  : 'bg-transparent border-white/[0.02] hover:bg-white/[0.02] hover:border-white/[0.06]'
                              }`}
                            >
                              <div className="flex items-start justify-between gap-1">
                                <div className="flex-1 min-w-0">
                                  <span className="text-xs font-mono tracking-wider font-semibold" style={{ color: meta.statusColor }}>
                                    {meta.provision}
                                  </span>
                                  <h3 className={`text-xs font-semibold truncate mt-1 ${isSelected ? 'text-white' : 'text-[#A1AAB8]'}`}>
                                    {meta.type}
                                  </h3>
                                  <div className="flex items-center gap-2 mt-2">
                                    <span className="text-[9px] font-mono text-[#52525B] flex items-center gap-1">
                                      <Calendar size={10} />
                                      {new Date(session.updated_at).toLocaleDateString()}
                                    </span>
                                    <div className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.statusColor }} />
                                    <span className="text-[9px] font-mono uppercase tracking-wider text-[#52525B]">
                                      {meta.status}
                                    </span>
                                  </div>
                                </div>
                                <button
                                  onClick={e => handleDeleteSession(e, session.session_id)}
                                  className="opacity-0 group-hover:opacity-100 p-1 rounded-md text-[#475569] hover:text-[#EF4444] hover:bg-red-500/10 transition-all ml-1 flex-shrink-0"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>

                  {/* Advisory Repository sections */}
                  <div className="pt-4 border-t border-[#4FB7C5]/10 space-y-1">
                    <span className="text-[10px] font-mono uppercase tracking-[0.2em] px-2 text-[#6B7280] block mb-2.5">
                      Advisory Repository
                    </span>
                    {REPO_SECTIONS.map(sec => {
                      const count = repoCounts[sec.key];
                      const hasItems = count > 0;
                      return (
                        <button
                          key={sec.key}
                          onClick={() => setActiveRepo(sec.key)}
                          className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl transition-all duration-150 group ${
                            hasItems
                              ? 'text-[#A1AAB8] hover:bg-[#131D2B] hover:text-white cursor-pointer hover:border-[#4FB7C5]/10 border border-transparent'
                              : 'text-[#475569] hover:bg-white/[0.01] hover:text-[#6B7280] cursor-pointer border border-transparent'
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            {React.createElement(sec.icon, {
                              size: 14,
                              className: hasItems ? 'text-[#4FB7C5]' : 'text-[#374151]',
                              fill: sec.key === 'starred' && hasItems ? 'currentColor' : 'none',
                            })}
                            <span className="text-xs text-left">{sec.label}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span
                              className="text-[9px] font-mono px-1.5 py-0.5 rounded"
                              style={hasItems
                                ? { color: '#4FB7C5', background: 'rgba(79,183,197,0.08)' }
                                : { color: '#374151', background: 'rgba(255,255,255,0.02)' }
                              }
                            >
                              {count} {sec.countLabel}
                            </span>
                            {hasItems && (
                              <ChevronLeft
                                size={11}
                                className="text-[#4FB7C5] opacity-0 group-hover:opacity-100 transition-opacity rotate-180"
                              />
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Sidebar footer */}
          <div className="p-4 border-t border-[#4FB7C5]/10 flex items-center justify-between text-[11px] text-[#475569]">
            <div className="flex items-center gap-2">
              <ShieldCheck size={14} className="text-[#4FB7C5]" />
              <span className="font-sans font-semibold">Vault Storage Encrypted</span>
            </div>
            {savedItems.length > 0 && (
              <span className="text-[9px] font-mono text-[#374151]">
                {savedItems.length} item{savedItems.length !== 1 ? 's' : ''} stored
              </span>
            )}
          </div>
        </aside>

        {/* ── CENTER WORKSPACE ──────────────────────────────────────────────────── */}
        <section
          className="flex-grow min-h-0 flex flex-col bg-[#000000] overflow-hidden relative"
          onDragOver={e => { e.preventDefault(); e.stopPropagation(); }}
          onDragEnter={e => {
            e.preventDefault(); e.stopPropagation();
            if (e.dataTransfer.items && e.dataTransfer.items.length > 0) setIsDragging(true);
          }}
          onDragLeave={e => {
            e.preventDefault(); e.stopPropagation();
            if (!e.currentTarget.contains(e.relatedTarget as Node)) setIsDragging(false);
          }}
          onDrop={e => {
            e.preventDefault(); e.stopPropagation();
            setIsDragging(false);
            const dropped = Array.from(e.dataTransfer.files).find(f =>
              /\.(pdf|docx|txt|png|jpg|jpeg)$/i.test(f.name)
            );
            if (dropped) setSelectedFile(dropped);
          }}
        >
          {/* Drag-and-drop overlay */}
          <AnimatePresence>
            {isDragging && (
              <motion.div
                key="drag-overlay"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="absolute inset-0 z-50 flex flex-col items-center justify-center pointer-events-none"
                style={{
                  background: 'rgba(0,0,0,0.88)',
                  border: '2px dashed rgba(79,183,197,0.55)',
                }}
              >
                <motion.div
                  initial={{ scale: 0.85, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: 0.05 }}
                  className="flex flex-col items-center gap-4"
                >
                  <div className="p-5 rounded-2xl" style={{ background: 'rgba(79,183,197,0.1)', border: '1px solid rgba(79,183,197,0.25)' }}>
                    <Upload size={36} style={{ color: '#4FB7C5' }} />
                  </div>
                  <div className="text-center">
                    <p className="font-mono font-bold text-sm tracking-widest uppercase" style={{ color: '#4FB7C5' }}>
                      Drop to Analyze
                    </p>
                    <p className="font-mono text-xs mt-1.5" style={{ color: '#475569' }}>
                      PDF · DOCX · TXT · Image
                    </p>
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Collapse sidebar trigger */}
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="absolute left-4 top-4 z-10 p-2 rounded-lg border border-white/[0.05] bg-[#000000] text-[#475569] hover:text-white transition-colors"
            title="Toggle consultations list"
          >
            <Menu size={15} />
          </button>

          {/* CHAT MESSAGE AREA */}
          <div
            ref={chatScrollRef}
            className="flex-1 min-h-0 overflow-y-auto relative scrollbar-thin"
            style={{ overflowX: 'clip', WebkitOverflowScrolling: 'touch', touchAction: 'pan-y' }}
            onWheel={(e) => {
              if (chatScrollRef.current) {
                chatScrollRef.current.scrollTop += e.deltaY;
              }
            }}
          >
            <div className="max-w-[920px] mx-auto w-full px-6 md:px-12 pt-10 pb-40 flex flex-col gap-8">

              {messages.length === 0 ? (
                <div className="w-full max-w-[800px] mx-auto pt-6 flex flex-col">
                  <div className="text-left mb-8 animate-in fade-in slide-in-from-top-4 duration-300">
                    <h2
                      style={{
                        fontFamily: "'Playfair Display', Georgia, serif",
                        fontWeight: 400,
                        fontSize: 'clamp(1.6rem, 3vw, 2.2rem)',
                        color: '#E8DDD0',
                        letterSpacing: '0.01em',
                        lineHeight: 1.2,
                      }}
                    >
                      Hi Samaksh, LETA is here to assist you.
                    </h2>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
                    {domainConfig.suggestedQueries.map((card, idx) => (
                      <div
                        key={idx}
                        onClick={() => handleAsk(card.query)}
                        className="p-4 rounded-xl border border-[#4FB7C5]/10 bg-[#000000] hover:bg-[#0a1520] hover:border-[#4FB7C5]/30 cursor-pointer transition-all duration-200 group flex flex-col justify-between"
                      >
                        <div className="flex items-center gap-1.5 mb-2 text-[#4FB7C5]">
                          <FileCheck size={12} />
                          <span className="text-[10px] font-sans uppercase tracking-wider font-semibold">
                            {card.title}
                          </span>
                        </div>
                        <p className="text-xs leading-relaxed text-[#A7B3C2] group-hover:text-white transition-colors">
                          {card.query}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex flex-col gap-8 w-full">
                  {messages.map((msg, idx) => {
                    const isUser = msg.role === 'user';
                    const saveStatus = !isUser ? getSaveStatus(msg.content) : null;

                    return (
                      <div
                        key={idx}
                        className={`w-full flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}
                      >
                        {isUser ? (
                          <div className="max-w-[70%] rounded-2xl p-4 bg-[#000000] border border-[#4FB7C5]/15 shadow-md">
                            <span className="text-[9px] font-sans font-semibold text-[#4FB7C5]/80 uppercase tracking-wider block mb-1.5">
                              ADVISORY CONSULTATION QUERY
                            </span>
                            <p className="whitespace-pre-wrap leading-relaxed text-xs text-[#E4E4E7]">
                              {msg.content}
                            </p>
                          </div>
                        ) : (
                          /* Assistant message */
                          <div className="w-full">
                            <div className="flex items-center gap-2 mb-3.5 pl-1 text-[#4FB7C5]">
                              <Sparkles className="w-3.5 h-3.5 animate-pulse" />
                              <span className="text-[10px] font-mono uppercase tracking-widest font-bold">
                                LETA SYNTHESIS
                              </span>
                            </div>

                            <LetaResponse
                              onRegenerate={() => handleAsk(messages[idx - 1]?.content)}
                              data={{
                                query: messages[idx - 1]?.content || '',
                                answer: msg.content,
                                citations: msg.citations || [],
                                consulted_sources: msg.consulted_sources || [],
                                confidence: msg.confidence || 0.95,
                                status: msg.current_status,
                              }}
                              isDark
                              animate={!msg.isHistory}
                              onDocumentClick={handleDocumentClick}
                            />

                            {/* ── Get Detailed Advisory CTA — prominent, inline ── */}
                            {msg.content && !isStreaming && isQuickTake(msg.content) && (
                              <motion.button
                                initial={{ opacity: 0, y: 6 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.22, delay: 0.1 }}
                                onClick={() => handleAsk('Please produce the detailed advisory.')}
                                disabled={isLoading}
                                className="mt-4 w-full flex items-center justify-between px-5 py-3.5 rounded-xl transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed group"
                                style={{
                                  background: 'linear-gradient(135deg, rgba(79,183,197,0.08) 0%, rgba(79,183,197,0.04) 100%)',
                                  border: '1px solid rgba(79,183,197,0.28)',
                                  boxShadow: '0 0 24px rgba(79,183,197,0.06)',
                                }}
                                onMouseEnter={e => {
                                  (e.currentTarget as HTMLButtonElement).style.background = 'linear-gradient(135deg, rgba(79,183,197,0.14) 0%, rgba(79,183,197,0.08) 100%)';
                                  (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(79,183,197,0.5)';
                                  (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 32px rgba(79,183,197,0.12)';
                                }}
                                onMouseLeave={e => {
                                  (e.currentTarget as HTMLButtonElement).style.background = 'linear-gradient(135deg, rgba(79,183,197,0.08) 0%, rgba(79,183,197,0.04) 100%)';
                                  (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(79,183,197,0.28)';
                                  (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 0 24px rgba(79,183,197,0.06)';
                                }}
                              >
                                <div className="flex items-center gap-3">
                                  <div className="p-2 rounded-lg" style={{ background: 'rgba(79,183,197,0.12)', border: '1px solid rgba(79,183,197,0.2)' }}>
                                    <FileText size={15} style={{ color: '#4FB7C5' }} />
                                  </div>
                                  <div className="text-left">
                                    <p className="text-sm font-semibold text-white tracking-tight leading-none mb-0.5">
                                      Get Detailed Advisory
                                    </p>
                                    <p className="text-[11px] font-mono text-[#4FB7C5]/60 tracking-wide">
                                      Full legal opinion · statutory analysis · compliance checklist
                                    </p>
                                  </div>
                                </div>
                                <ChevronLeft
                                  size={16}
                                  className="text-[#4FB7C5]/50 group-hover:text-[#4FB7C5] transition-colors rotate-180 flex-shrink-0"
                                />
                              </motion.button>
                            )}

                            {/* ── Save / Star tray ──────────────────────────── */}
                            {msg.content && !isStreaming && (
                              <div className="flex items-center gap-1.5 mt-2.5 pl-1 flex-wrap">

                                <button
                                  onClick={() => handleSaveMessage(msg, idx, 'saved')}
                                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-mono uppercase tracking-wider transition-all duration-150 border ${
                                    saveStatus === 'saved'
                                      ? 'text-[#4FB7C5] bg-[#4FB7C5]/10 border-[#4FB7C5]/25'
                                      : 'text-[#475569] bg-transparent border-white/[0.04] hover:text-[#4FB7C5] hover:bg-[#4FB7C5]/5 hover:border-[#4FB7C5]/15'
                                  }`}
                                  title={saveStatus === 'saved' ? 'Remove from saved drafts' : 'Save to Matter Drafts'}
                                >
                                  {saveStatus === 'saved' ? <BookmarkCheck size={12} /> : <Bookmark size={12} />}
                                  {saveStatus === 'saved' ? 'Saved' : 'Save'}
                                </button>

                                <button
                                  onClick={() => handleSaveMessage(msg, idx, 'starred')}
                                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-mono uppercase tracking-wider transition-all duration-150 border ${
                                    saveStatus === 'starred'
                                      ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/25'
                                      : 'text-[#475569] bg-transparent border-white/[0.04] hover:text-yellow-400 hover:bg-yellow-400/5 hover:border-yellow-400/15'
                                  }`}
                                  title={saveStatus === 'starred' ? 'Remove star' : 'Star this advisory'}
                                >
                                  <Star size={12} fill={saveStatus === 'starred' ? 'currentColor' : 'none'} />
                                  {saveStatus === 'starred' ? 'Starred' : 'Star'}
                                </button>

                                {saveStatus && (
                                  <button
                                    onClick={() => setActiveRepo(saveStatus === 'starred' ? 'starred' : 'saved')}
                                    className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[9px] font-mono text-[#374151] hover:text-[#4FB7C5] transition-colors"
                                    title="View in repository"
                                  >
                                    <Eye size={11} />
                                    View in Repository
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {isLoading && (
                    <div className="flex justify-center py-6">
                      <SimpleSearchLoader />
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </div>

          {/* CHAT INPUT AREA */}
          <div className="p-6 md:px-10 py-6 border-t border-[#4FB7C5]/10 bg-[#000000] flex-shrink-0 relative z-20">
            <div className="max-w-[920px] mx-auto relative">

              {/* ── Voice recording live overlay ─────────────────────────── */}
              <AnimatePresence>
                {(isRecording || isTranscribing) && (
                  <motion.div
                    key="voice-bar"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 6 }}
                    transition={{ duration: 0.18 }}
                    className="absolute z-30 left-0 right-0"
                    style={{ bottom: 'calc(100% + 10px)' }}
                  >
                    {isTranscribing ? (
                      /* Transcribing state */
                      <div className="flex items-center gap-3 px-4 py-3 rounded-2xl border border-[#4FB7C5]/25 bg-[#000a0d]"
                        style={{ boxShadow: '0 0 30px rgba(79,183,197,0.08)' }}>
                        <span className="w-2 h-2 rounded-full bg-[#4FB7C5] flex-shrink-0 animate-pulse" />
                        <span className="flex-1 text-xs font-body text-[#A1AAB8] italic">
                          Transcribing audio…
                        </span>
                        <span className="text-[10px] font-mono text-[#4FB7C5]/60 tracking-wider flex-shrink-0">
                          WHISPER
                        </span>
                      </div>
                    ) : (
                      /* Recording state */
                      <div className="flex items-center gap-3 px-4 py-3 rounded-2xl border border-red-500/25 bg-[#0a0000]"
                        style={{ boxShadow: '0 0 30px rgba(239,68,68,0.08)' }}>

                        {/* Live waveform bars */}
                        <div className="flex items-center gap-[2px] h-7 flex-shrink-0">
                          {audioLevels.map((level, i) => (
                            <div
                              key={i}
                              className="w-[2px] rounded-full bg-red-400 transition-all"
                              style={{
                                height: `${Math.max(3, level * 28)}px`,
                                transitionDuration: '60ms',
                                opacity: 0.5 + level * 0.5,
                              }}
                            />
                          ))}
                        </div>

                        {/* Pulsing dot */}
                        <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0 animate-pulse" />

                        {/* Recording status label */}
                        <span className="flex-1 text-xs font-body text-[#A1AAB8] truncate italic min-w-0">
                          Recording — speak clearly
                        </span>

                        {/* Duration */}
                        <span className="text-[10px] font-mono text-[#6B7280] tabular-nums flex-shrink-0">
                          {formatDuration(recordingDuration)}
                        </span>

                        {/* Stop button */}
                        <button
                          onClick={stopVoiceRecording}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono uppercase tracking-wider bg-red-500/10 border border-red-500/25 text-red-400 hover:bg-red-500/20 transition-all flex-shrink-0"
                        >
                          <MicOff size={11} />
                          Stop
                        </button>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* ── Mic permission error ──────────────────────────────────────── */}
              <AnimatePresence>
                {micError && (
                  <motion.div
                    key="mic-error"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="absolute z-30 left-0 right-0"
                    style={{ bottom: 'calc(100% + 10px)' }}
                  >
                    <div className="flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl border border-red-500/20 bg-[#0a0000] text-xs font-mono text-red-400">
                      <span>{micError}</span>
                      <button onClick={() => setMicError(null)} className="hover:text-white transition-colors flex-shrink-0">
                        <X size={12} />
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <AnimatePresence>
                {selectedFile && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="absolute -top-12 left-4 flex items-center gap-2 px-3 py-1.5 rounded-lg border border-[#4FB7C5]/30 bg-[#000000] z-30"
                  >
                    <Paperclip size={11} className="text-[#4FB7C5]" />
                    <span className="text-[11px] font-mono max-w-[150px] truncate text-white">
                      {selectedFile.name}
                    </span>
                    <button
                      onClick={() => { setSelectedFile(null); if (fileInputRef.current) fileInputRef.current.value = ''; }}
                      className="text-[#6B7280] hover:text-[#EF4444] transition-colors ml-1"
                    >
                      <X size={12} />
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              <textarea
                ref={textareaRef}
                value={query}
                onChange={e => { setQuery(e.target.value); autoResize(); }}
                placeholder={domainConfig.placeholder}
                className="w-full p-4 pr-40 pb-14 font-body text-xs leading-relaxed outline-none resize-none transition-all duration-200 bg-[#000000] border border-[#4FB7C5]/15 rounded-2xl text-[#F4F7FA] overflow-y-auto"
                style={{ minHeight: '90px', maxHeight: '300px' }}
                onFocus={e => {
                  e.currentTarget.style.borderColor = 'rgba(79,183,197,0.3)';
                  e.currentTarget.style.boxShadow = '0 0 0 3px rgba(79,183,197,0.05)';
                }}
                onBlur={e => {
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.04)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleAsk();
                  }
                }}
              />

              <div className="absolute bottom-4 right-4 flex items-center gap-2">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={e => { if (e.target.files?.[0]) setSelectedFile(e.target.files[0]); }}
                  className="hidden"
                  accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isLoading || isRecording}
                  className="p-2.5 rounded-lg text-[#475569] hover:text-white hover:bg-white/[0.02] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  title="Attach document"
                >
                  <Paperclip size={15} />
                </button>

                {/* ── Mic / Voice button ─────────────────────────────────── */}
                {(
                  <button
                    onClick={startVoiceRecording}
                    disabled={isLoading || isStreaming}
                    title={isRecording ? 'Stop voice recording' : 'Voice input (click to speak)'}
                    className={`relative p-2.5 rounded-lg transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed ${
                      isRecording
                        ? 'text-red-400 bg-red-500/10 border border-red-500/30'
                        : 'text-[#475569] hover:text-white hover:bg-white/[0.02] border border-transparent'
                    }`}
                  >
                    {isRecording ? <MicOff size={15} /> : <Mic size={15} />}
                    {isRecording && (
                      <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                    )}
                  </button>
                )}

                {isStreaming ? (
                  <button
                    onClick={handleStop}
                    className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl font-sans font-semibold text-[10px] uppercase tracking-wider transition-all duration-200 border border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]"
                  >
                    <Square size={11} fill="currentColor" />
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={() => handleAsk()}
                    disabled={(!query.trim() && !selectedFile) || isLoading}
                    className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl font-sans font-semibold text-[10px] uppercase tracking-wider transition-all duration-200"
                    style={{
                      background: (!query.trim() && !selectedFile) || isLoading
                        ? 'rgba(79,183,197,0.15)'
                        : '#4FB7C5',
                      color: (!query.trim() && !selectedFile) || isLoading
                        ? 'rgba(79,183,197,0.7)'
                        : '#000000',
                      cursor: (!query.trim() && !selectedFile) || isLoading ? 'not-allowed' : 'pointer',
                    }}
                  >
                    <Send size={11} />
                    Analyze Query
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* ── RIGHT PANEL: PDF viewer ───────────────────────────────────────────── */}
        {openDocuments.length > 0 && (
          <aside className="w-[340px] h-full border-l border-[#4FB7C5]/10 bg-[#000000] flex-shrink-0 flex flex-col overflow-hidden relative z-10">
            <div className="h-full flex flex-col">
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.04] bg-[#131D2B] flex-shrink-0">
                <span className="text-[10px] font-sans uppercase tracking-wider text-[#4FB7C5] font-semibold">
                  Reference Viewer
                </span>
                <div className="flex gap-1 overflow-x-auto max-w-[180px] scrollbar-none">
                  {openDocuments.map(doc => (
                    <button
                      key={doc.id}
                      onClick={() => setActiveDocId(doc.id)}
                      className={`px-2.5 py-1 text-[9px] font-sans rounded max-w-[120px] truncate ${
                        activeDocId === doc.id ? 'bg-[#4FB7C5]/10 text-[#4FB7C5] border border-[#4FB7C5]/20' : 'text-[#6C7A99]'
                      }`}
                    >
                      {doc.title}
                    </button>
                  ))}
                </div>
              </div>

              {openDocuments.map(doc => doc.id === activeDocId && (
                <div key={doc.id} className="flex-grow overflow-hidden relative">
                  <DocumentViewer
                    url={doc.url}
                    onClose={() => closeDocument(doc.id)}
                    title={doc.title}
                    initialPage={doc.page}
                    keyword={doc.search}
                  />
                </div>
              ))}
            </div>
          </aside>
        )}

      </div>

      {/* ══ ITEM VIEWER MODAL ════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {viewingItem && (
          <motion.div
            key="item-viewer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[100] flex flex-col bg-[#000000]"
          >
            {/* Modal header */}
            <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-[#4FB7C5]/10 bg-[#000000]">
              <div className="flex items-center gap-3 min-w-0">
                <button
                  onClick={() => setViewingItem(null)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/[0.06] text-[#A1AAB8] hover:text-white hover:border-[#4FB7C5]/30 text-xs transition-colors flex-shrink-0"
                >
                  <ArrowLeft size={13} />
                  Back
                </button>
                <div className="h-4 w-[1px] bg-white/[0.06] flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-white truncate">{viewingItem.title}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span
                      className="text-[9px] font-mono px-1.5 py-0.5 rounded-full border"
                      style={viewingItem.type === 'starred'
                        ? { color: '#FCD34D', borderColor: 'rgba(252,211,77,0.2)', background: 'rgba(252,211,77,0.06)' }
                        : { color: '#4FB7C5', borderColor: 'rgba(79,183,197,0.2)', background: 'rgba(79,183,197,0.06)' }
                      }
                    >
                      {viewingItem.type === 'starred' ? '★ Starred Advisory' : '⊡ Saved Draft'}
                    </span>
                    <span className="text-[9px] font-mono text-[#374151] uppercase">
                      {DOMAIN_LABEL[viewingItem.domain] || viewingItem.domain}
                    </span>
                    <span className="text-[9px] font-mono text-[#374151] flex items-center gap-1">
                      <Calendar size={9} />
                      {new Date(viewingItem.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </span>
                  </div>
                </div>
              </div>

              {/* Header actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* Toggle star */}
                <button
                  onClick={() => {
                    const newType = viewingItem.type === 'starred' ? 'saved' : 'starred';
                    setSavedItems(prev => prev.map(i => i.id === viewingItem.id ? { ...i, type: newType } : i));
                    setViewingItem(prev => prev ? { ...prev, type: newType } : null);
                  }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono uppercase tracking-wider border transition-all ${
                    viewingItem.type === 'starred'
                      ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/25'
                      : 'text-[#475569] border-white/[0.04] hover:text-yellow-400 hover:border-yellow-400/15'
                  }`}
                >
                  <Star size={12} fill={viewingItem.type === 'starred' ? 'currentColor' : 'none'} />
                  {viewingItem.type === 'starred' ? 'Starred' : 'Star'}
                </button>

                {/* Delete */}
                <button
                  onClick={() => { handleRemoveItem(viewingItem.id); setViewingItem(null); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-mono uppercase tracking-wider border border-white/[0.04] text-[#475569] hover:text-[#EF4444] hover:bg-red-500/10 hover:border-red-500/20 transition-all"
                >
                  <Trash2 size={12} />
                  Remove
                </button>

                <button
                  onClick={() => setViewingItem(null)}
                  className="p-1.5 rounded-lg text-[#475569] hover:text-white hover:bg-white/[0.04] transition-colors"
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Original query context */}
            {viewingItem.query && (
              <div className="flex-shrink-0 px-8 pt-5 pb-0 max-w-[960px] mx-auto w-full">
                <div className="px-4 py-3 rounded-xl border border-[#4FB7C5]/10 bg-[#000000]">
                  <span className="text-[9px] font-sans font-semibold text-[#4FB7C5]/70 uppercase tracking-wider block mb-1">
                    Original Query
                  </span>
                  <p className="text-xs text-[#6B7280] leading-relaxed">{viewingItem.query}</p>
                </div>
              </div>
            )}

            {/* Content area */}
            <div className="flex-grow min-h-0 overflow-y-auto scrollbar-thin">
              <div className="max-w-[960px] mx-auto w-full px-8 pt-5 pb-16">
                <div className="flex items-center gap-2 mb-4 text-[#4FB7C5]">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span className="text-[10px] font-mono uppercase tracking-widest font-bold">LETA SYNTHESIS</span>
                </div>
                <LetaResponse
                  onRegenerate={() => {}}
                  data={{
                    query: viewingItem.query,
                    answer: viewingItem.content,
                    citations: [],
                    consulted_sources: [],
                    confidence: 0.95,
                  }}
                  isDark
                  animate={false}
                  onDocumentClick={handleDocumentClick}
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
};

export default LetaWorkspace;
