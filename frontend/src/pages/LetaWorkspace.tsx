import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Send, Sparkles, Menu, Paperclip,
  ChevronLeft, Folder, Star, Landmark, FileCheck,
  Bookmark, Trash2, Calendar, ShieldCheck, Scale, Download, Plus, Square, Upload
} from 'lucide-react';
import axios from 'axios';
import { BASE_URL } from '../config/api';
import { LetaResponse } from '../components/leta';
import { SimpleSearchLoader } from '../components/effects';
import { DocumentViewer } from '../components/documents';

// Define Interface types
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

  // State Management
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

  // Refs
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const autoResize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 300) + 'px';
  };

  // Auto scroll
  const scrollToBottom = () => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  useEffect(() => { scrollToBottom(); }, [messages, isLoading]);

  // Initial sessions fetch
  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 60000);
    return () => clearInterval(interval);
  }, [currentSessionId]);

  // Reset page state on domain change
  useEffect(() => {
    setMessages([]);
    setCurrentSessionId(null);
    setQuery('');
    setOpenDocuments([]);
    setActiveDocId(null);
  }, [domainId]);

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
    setIsStreaming(false);
    setIsLoading(false);
  };

  const handleAsk = async (queryOverride?: string) => {
    const activeQuery = typeof queryOverride === 'string' ? queryOverride : query;
    if (!activeQuery.trim()) return;

    const userMsg: Message = { role: 'user', content: activeQuery };
    const newAiMsg: Message = { role: 'assistant', content: '', confidence: 0.95, citations: [] };

    setMessages(prev => [...prev, userMsg, newAiMsg]);
    setQuery('');
    setSelectedFile(null);
    setIsLoading(true);
    setIsStreaming(false);
    if (textareaRef.current) textareaRef.current.style.height = '90px';

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      let activeSessionId = currentSessionId;
      if (!activeSessionId) {
        // Enforce beautifully capitalized matter style titles
        let title = activeQuery;
        if (title.length > 40) {
          title = title.substring(0, 38) + '...';
        }
        
        // Dynamic Case Name Generator to ensure legal/advisory outcome aesthetic
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

        const sessionRes = await axios.post(`${BASE_URL}/api/sessions/new`, { title });
        activeSessionId = sessionRes.data.session_id;
        setCurrentSessionId(activeSessionId);
      }

      let res;
      if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('question', userMsg.content);
        if (activeSessionId) formData.append('session_id', activeSessionId);
        res = await fetch(`${BASE_URL}/ask-with-file`, { method: 'POST', body: formData, signal: controller.signal });
      } else {
        res = await fetch(`${BASE_URL}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: userMsg.content, session_id: activeSessionId, intent: 'general' }),
          signal: controller.signal,
        });
      }

      if (!res.ok) throw new Error(`Server returned status: ${res.status}`);

      const reader = res.body?.getReader();
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
      abortControllerRef.current = null;
      // Update sidebar session list to sync names
      fetchSessions();
    } catch (error: any) {
      if ((error as any)?.name === 'AbortError') {
        // User stopped generation — leave partial content as-is
        setIsStreaming(false);
        return;
      }
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

  // Helper metadata generator for session cards
  const getSessionDetails = (title: string) => {
    const cleanTitle = title.trim();
    let type = 'Statutory Consultation';
    let provision = 'Act Gen';
    let status = 'Consulting';
    let statusColor = '#3B82F6';

    const lower = cleanTitle.toLowerCase();
    if (domainId === 'gst') {
      if (lower.includes('refund')) {
        type = 'GST Refund Appeal';
        provision = 'Sec 54';
        status = 'Draft Ready';
        statusColor = '#22C55E';
      } else if (lower.includes('itc') || lower.includes('eligible') || lower.includes('16(4)')) {
        type = 'ITC Audit Review';
        provision = 'Sec 16(4)';
        status = 'Advisory Signed';
        statusColor = '#67E8F9';
      } else if (lower.includes('73') || lower.includes('notice') || lower.includes('scn')) {
        type = 'Sec 73 SCN Response';
        provision = 'Section 73';
        status = 'Vetting Needed';
        statusColor = '#F59E0B';
      } else if (lower.includes('86a') || lower.includes('block') || lower.includes('ledger')) {
        type = 'Ledger Blocking Contest';
        provision = 'Rule 86A';
        status = 'Active Workspace';
        statusColor = '#EC4899';
      } else if (lower.includes('penalty') || lower.includes('47')) {
        type = 'Section 47 Penalty';
        provision = 'Section 47';
        status = 'Case Closed';
        statusColor = '#6B7280';
      }
    } else if (domainId === 'fema') {
      type = 'FEMA Advisory';
      provision = 'FEMA Sec 6';
      if (lower.includes('fdi')) {
        type = 'FDI Policy Clearance';
        provision = 'FDI Schedule';
        status = 'Verification Ok';
        statusColor = '#22C55E';
      } else if (lower.includes('export')) {
        type = 'Export Repatriation';
        provision = 'Section 8';
        status = 'Under Audit';
        statusColor = '#F59E0B';
      }
    } else if (domainId === 'company-law') {
      type = 'ROC Corporate Compliance';
      provision = 'CA 2013';
      if (lower.includes('condonation') || lower.includes('delay')) {
        type = 'Delay Condonation filing';
        provision = 'Sec 137';
        status = 'In Consultation';
        statusColor = '#EC4899';
      } else if (lower.includes('director') || lower.includes('164')) {
        type = 'Board Director Briefing';
        provision = 'Sec 164';
        status = 'Brief Completed';
        statusColor = '#67E8F9';
      }
    } else if (domainId === 'income-tax') {
      type = 'Scrutiny Defense';
      provision = 'ITA 1961';
      if (lower.includes('143')) {
        type = '143(2) Response Prep';
        provision = 'Sec 143(2)';
        status = 'Active Scrutiny';
        statusColor = '#EC4899';
      } else if (lower.includes('appeal')) {
        type = 'Assessment Appeal grounds';
        provision = 'Sec 246A';
        status = 'Draft Signed';
        statusColor = '#22C55E';
      }
    }

    if (type === 'Statutory Consultation' && cleanTitle) {
      type = cleanTitle.length > 25 ? cleanTitle.substring(0, 22) + '...' : cleanTitle;
    }

    return { type, provision, status, statusColor };
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-[#000000] select-none text-sm font-body overflow-hidden">
      
      {/* ── TOP HEADER NAVBAR (Fixed, flex-shrink: 0) ─────────────────────────────────────────── */}
      <header className="h-[72px] flex-shrink-0 flex items-center justify-between px-6 bg-[#000000] border-b border-[#4FB7C5]/10 relative z-20">
        <div className="flex items-center gap-4">
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

        {/* Global actions */}
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-2 px-3 py-1 border border-white/[0.06] bg-white/[0.02] rounded-full text-[11px]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22C55E] animate-pulse" />
            Active Advisory Workspace
          </span>
        </div>
      </header>

      {/* ── WORKSPACE BODY PANELS (Occupies exact height, prevents outer scrolling) ────────────────── */}
      <div className="flex-grow flex flex-row overflow-hidden relative">

        {/* 1. LEFT SIDEBAR: Independently Scrollable Consultations & Folders */}
        <aside 
          className="h-full flex flex-col border-r border-[#4FB7C5]/10 bg-[#000000] flex-shrink-0 transition-all duration-300 overflow-hidden relative z-10"
          style={{ width: isSidebarOpen ? '320px' : '0px' }}
        >
          {/* New Consultation trigger */}
          <div className="p-4 flex-shrink-0 border-b border-[#4FB7C5]/10">
            <button
              onClick={handleNewSession}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl font-sans font-semibold uppercase tracking-wider text-[10px] transition-all duration-200 text-black bg-[#4FB7C5] hover:bg-[#3EA6B4]"
            >
              <Plus className="w-4 h-4" />
              New Consultation
            </button>
          </div>

          {/* Session scrollable items list (Independently Scrollable) */}
          <div className="flex-grow overflow-y-auto px-3 py-4 space-y-4 scrollbar-thin">
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

            {/* Structured Saved matter repositories */}
            <div className="pt-4 border-t border-[#4FB7C5]/10 space-y-1">
              <span className="text-[10px] font-mono uppercase tracking-[0.2em] px-2 text-[#6B7280] block mb-2.5">
                Advisory Repository
              </span>
              {[
                { label: 'Saved Matter Drafts', icon: Folder, count: '3 Files' },
                { label: 'Starred Advisory Briefs', icon: Star, count: '5 Starred' },
                { label: 'Department Notice Files', icon: Landmark, count: '2 Notices' },
                { label: 'Custom Reference Bookmarks', icon: Bookmark, count: '12 Refs' }
              ].map((item, idx) => (
                <div 
                  key={idx}
                  className="flex items-center justify-between px-3 py-2.5 rounded-xl cursor-not-allowed text-[#475569] hover:bg-white/[0.01] hover:text-[#A1AAB8] transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <item.icon size={14} />
                    <span className="text-xs">{item.label}</span>
                  </div>
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.02] text-[#475569]">
                    {item.count}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Left panel collapse monitor */}
          <div className="p-4 border-t border-[#4FB7C5]/10 flex items-center justify-between text-[11px] text-[#475569]">
            <div className="flex items-center gap-2">
              <ShieldCheck size={14} className="text-[#4FB7C5]" />
              <span className="font-sans font-semibold">Vault Storage Encrypted</span>
            </div>
          </div>
        </aside>

        {/* 2. CENTER WORKSPACE: Main Drafting Board (Locked layout, flex-column) */}
        <section
          className="flex-grow flex flex-col h-full bg-[#000000] overflow-hidden relative"
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
          {/* ── Drag-and-drop overlay ────────────────────────────────────── */}
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
                  borderRadius: '0px',
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

          {/* CHAT MESSAGE AREA (Independently Scrollable with bottom margins) */}
          <div className="flex-1 overflow-y-auto overflow-x-hidden relative scroll-smooth scrollbar-thin">
            <div className="max-w-[920px] mx-auto w-full px-6 md:px-12 pt-10 pb-40 flex flex-col gap-8">
              
              {messages.length === 0 ? (
                /* GUIDED UPPER-MID VIEWPORT EMPTY STATE (Stacked vertically, no global centering) */
                <div className="w-full max-w-[800px] mx-auto pt-6 flex flex-col">
                  
                  {/* UPPER-MID SUMMARY HEADER */}
                  <div className="text-left mb-8 animate-in fade-in slide-in-from-top-4 duration-300">
                    <div className="inline-flex p-2.5 rounded-xl bg-[#4FB7C5]/10 border border-[#4FB7C5]/15 mb-4 text-[#4FB7C5]">
                      <Scale size={18} />
                    </div>
                    <h2 className="font-display font-bold uppercase text-lg md:text-xl text-white mb-2 tracking-tight">
                      How can LETA assist you today?
                    </h2>
                    <p className="text-xs font-body text-[#A7B3C2] max-w-2xl leading-relaxed">
                      Describe your notice, compliance issue, drafting requirement, or statutory query. LETA cross-references Indian judicial precedents and the active acts database to synthesize structured advisory briefs.
                    </p>
                  </div>

                  {/* HIGH-IMPACT SUGGESTIONS BLOCK */}
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
                /* CHAT TIMELINE STREAM */
                <div className="flex flex-col gap-8 w-full">
                  {messages.map((msg, idx) => {
                    const isUser = msg.role === 'user';
                    return (
                      <div 
                        key={idx} 
                        className={`w-full flex ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}
                      >
                        {isUser ? (
                          /* Right Aligned User Bubble with elegant layout governance */
                          <div className="max-w-[70%] rounded-2xl p-4 bg-[#000000] border border-[#4FB7C5]/15 shadow-md">
                            <span className="text-[9px] font-sans font-semibold text-[#4FB7C5]/80 uppercase tracking-wider block mb-1.5">
                              ADVISORY CONSULTATION QUERY
                            </span>
                            <p className="whitespace-pre-wrap leading-relaxed text-xs text-[#E4E4E7]">
                              {msg.content}
                            </p>
                          </div>
                        ) : (
                          /* Left Aligned Synthesized Answer */
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

          {/* CHAT INPUT AREA (Sticky at bottom, inherits width constraint) */}
          <div className="p-6 md:px-10 py-6 border-t border-[#4FB7C5]/10 bg-[#000000] flex-shrink-0 relative z-20">
            <div className="max-w-[920px] mx-auto relative">
              
              {/* Soft overlay file picker display */}
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
                      onClick={() => setSelectedFile(null)} 
                      className="text-[#6B7280] hover:text-[#EF4444] transition-colors ml-1"
                    >
                      <X size={12} />
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Input Area */}
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

              {/* Utility tray actions */}
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
                  disabled={isLoading}
                  className="p-2.5 rounded-lg text-[#475569] hover:text-white hover:bg-white/[0.02] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                  title="Attach document — PDF, DOCX, TXT or Image (or drag & drop)"
                >
                  <Paperclip size={15} />
                </button>

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
                    className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl font-sans font-semibold text-[10px] uppercase tracking-wider text-black transition-all duration-200"
                    style={{
                      background: (!query.trim() && !selectedFile) || isLoading
                        ? 'rgba(79,183,197,0.1)'
                        : '#4FB7C5',
                      opacity: (!query.trim() && !selectedFile) || isLoading ? 0.4 : 1,
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

        {/* 3. RIGHT PANEL: Live Statutory Context, related drafts or active document PDF (Fixed, flex-shrink: 0) */}
        <aside className="w-[340px] h-full border-l border-[#4FB7C5]/10 bg-[#000000] flex-shrink-0 flex flex-col overflow-hidden relative z-10">
          
          {openDocuments.length > 0 ? (
            // SPLIT VIEW: Dynamic interactive Document PDF viewer replaces right workspace context on open
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
          ) : (
            // STANDARD PANEL VIEW: Session Context Panel (Independently Scrollable)
            <div className="p-5 flex flex-col h-full overflow-y-auto space-y-6 scrollbar-thin">
              
              {/* Metadata block */}
              <div>
                <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#6B7280] block mb-3">
                  Workspace Context
                </span>
                <div className="p-4 rounded-xl border border-[#4FB7C5]/12 bg-white/[0.01] space-y-3">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-[#6B7280]">Active Domain:</span>
                    <span className="font-mono text-white text-[11px] font-bold">
                      {domainId.toUpperCase()} INTEL
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-[#6B7280]">Citations Found:</span>
                    <span className="font-mono text-white text-[11px]">
                      {messages[messages.length-1]?.consulted_sources?.length || 0} Sources
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-[#6B7280]">Analysis Engine:</span>
                    <span className="font-sans font-semibold text-[#4FB7C5] text-[10px] bg-[#4FB7C5]/10 px-1.5 py-0.5 rounded">
                      TITAN_V4
                    </span>
                  </div>
                </div>
              </div>

              {/* Legal Reference Citations Checklist */}
              <div>
                <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#6B7280] block mb-3">
                  Cited Provisions Checklist
                </span>
                <div className="space-y-2">
                  {messages.length > 0 && messages[messages.length-1]?.consulted_sources ? (
                    messages[messages.length-1].consulted_sources?.slice(0, 4).map((src: any, idx: number) => (
                      <div 
                        key={idx}
                        onClick={() => handleDocumentClick({ url: src.url, page: src.page_num, title: src.title })}
                        className="p-3 rounded-lg border border-[#4FB7C5]/12 bg-white/[0.01] hover:border-[#4FB7C5]/35 transition-all cursor-pointer flex items-start gap-2.5"
                      >
                        <Scale size={13} className="text-[#4FB7C5] mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="text-xs font-semibold text-white truncate max-w-[240px]">
                            {src.title || 'Statutory Code Reference'}
                          </p>
                          <span className="text-[9px] font-mono text-[#475569] block mt-0.5">
                            Page {src.page_num || 1} • Click to open
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 rounded-xl border border-dashed border-white/[0.03] text-center text-xs text-[#475569] font-mono">
                      No active citations loaded
                    </div>
                  )}
                </div>
              </div>

              {/* Related Practical drafts templates */}
              {domainConfig.drafts.length > 0 && (
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#6B7280] block mb-3">
                    Recommended Draft Formats
                  </span>
                  <div className="space-y-2">
                    {domainConfig.drafts.map((draft, idx) => (
                      <div 
                        key={idx}
                        className="p-3 rounded-lg border border-[#4FB7C5]/10 bg-[#000000]/50 hover:border-[#4FB7C5]/25 flex items-center justify-between"
                      >
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-[#A7B3C2] truncate max-w-[200px]">
                            {draft.name}
                          </p>
                          <span className="text-[9px] font-sans text-[#6C7A99]">
                            Category: {draft.section}
                          </span>
                        </div>
                        
                        <button 
                          className="p-1.5 rounded bg-white/[0.03] border border-white/[0.05] text-[#4FB7C5] hover:bg-[#4FB7C5]/10 hover:text-white transition-colors flex-shrink-0 cursor-not-allowed"
                          title="Integration in customization route"
                        >
                          <Download size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>
          )}
        </aside>

      </div>
    </div>
  );
};

export default LetaWorkspace;
