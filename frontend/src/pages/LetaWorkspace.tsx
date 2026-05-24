import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import {
  Trash2,
  Paperclip,
  Send,
  Square,
  ChevronLeft,
  Menu
} from 'lucide-react';

import axios from 'axios';

import { BASE_URL } from '../config/api';
import { getAccessToken } from '../services/auth';

import { LetaResponse } from '../components/leta';
import { SimpleSearchLoader } from '../components/effects';
import { DocumentViewer } from '../components/documents';

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

  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);

  const [query, setQuery] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const [openDocuments, setOpenDocuments] = useState<OpenDoc[]>([]);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const domainConfig = {
    title: 'LETA GST',
    subtitle: 'Professional GST Intelligence Workspace',
    placeholder:
      'Enter your GST issue, statutory notice, or legal drafting query...'
  };

  const getAuthHeaders = () => {
    const token = getAccessToken();

    return {
      Authorization: `Bearer ${token}`
    };
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({
      behavior: 'smooth'
    });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    fetchSessions();

    const interval = setInterval(() => {
      fetchSessions();
    }, 60000);

    return () => clearInterval(interval);
  }, []);

  const fetchSessions = async () => {
    try {
      const res = await axios.get(
        `${BASE_URL}/api/sessions/list`,
        {
          headers: getAuthHeaders()
        }
      );

      setSessions(res.data || []);
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    try {
      setIsLoading(true);

      setCurrentSessionId(sessionId);

      const res = await axios.get(
        `${BASE_URL}/api/sessions/${sessionId}`,
        {
          headers: getAuthHeaders()
        }
      );

      const loadedMessages =
        res.data?.messages?.map((msg: any) => ({
          role: msg.role,
          content: msg.content,
          confidence: 1,
          citations: [],
          consulted_sources: [],
          isHistory: true
        })) || [];

      setMessages(loadedMessages);

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

    setIsStreaming(false);
  };

  const handleDeleteSession = async (
    e: React.MouseEvent,
    id: string
  ) => {
    e.stopPropagation();

    try {
      await axios.delete(
        `${BASE_URL}/api/sessions/${id}`,
        {
          headers: getAuthHeaders()
        }
      );

      await fetchSessions();

      if (currentSessionId === id) {
        handleNewSession();
      }
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

  const handleAsk = async () => {
    if (!query.trim() && !selectedFile) {
      return;
    }

    const activeQuery = query;

    const userMsg: Message = {
      role: 'user',
      content: activeQuery
    };

    const aiMsg: Message = {
      role: 'assistant',
      content: ''
    };

    setMessages(prev => [...prev, userMsg, aiMsg]);

    setQuery('');

    setIsLoading(true);

    const controller = new AbortController();

    abortControllerRef.current = controller;

    try {
      let activeSessionId = currentSessionId;

      if (!activeSessionId) {
        const sessionRes = await axios.post(
          `${BASE_URL}/api/sessions/new`,
          {
            title:
              activeQuery.length > 40
                ? activeQuery.substring(0, 40)
                : activeQuery
          },
          {
            headers: getAuthHeaders()
          }
        );

        activeSessionId = sessionRes.data.session_id;

        setCurrentSessionId(activeSessionId);
      }

      let res: Response;

      if (selectedFile) {
        const formData = new FormData();

        formData.append('file', selectedFile);

        formData.append('question', activeQuery);

        if (activeSessionId) {
          formData.append(
            'session_id',
            activeSessionId
          );
        }

        res = await fetch(`${BASE_URL}/ask-with-file`, {
          method: 'POST',
          headers: {
            ...getAuthHeaders()
          },
          body: formData,
          signal: controller.signal
        });
      } else {
        res = await fetch(`${BASE_URL}/ask`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders()
          },
          body: JSON.stringify({
            question: activeQuery,
            session_id: activeSessionId,
            intent: 'general'
          }),
          signal: controller.signal
        });
      }

      if (!res.ok) {
        throw new Error(`HTTP ERROR ${res.status}`);
      }

      const reader = res.body?.getReader();

      if (!reader) {
        throw new Error('No stream reader available');
      }

      const decoder = new TextDecoder('utf-8');

      setIsLoading(false);

      setIsStreaming(true);

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value);

        setMessages(prev => {
          const updated = [...prev];

          const last =
            updated[updated.length - 1];

          if (last?.role === 'assistant') {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + chunk
            };
          }

          return updated;
        });
      }

      setIsStreaming(false);

      abortControllerRef.current = null;

      await fetchSessions();
    } catch (error: any) {
      if (error?.name === 'AbortError') {
        setIsStreaming(false);
        return;
      }

      console.error('LETA API Error:', error);

      setMessages(prev => {
        const updated = [...prev];

        const last =
          updated[updated.length - 1];

        if (last?.role === 'assistant') {
          updated[updated.length - 1] = {
            ...last,
            content:
              last.content +
              '\n\n[Workspace Error]: Unable to generate response.'
          };
        }

        return updated;
      });

      setIsLoading(false);

      setIsStreaming(false);
    }
  };

  const handleDocumentClick = ({
    url,
    page,
    search,
    title
  }: {
    url: string;
    page?: number;
    search?: string;
    title?: string;
  }) => {
    const fullUrl = url.startsWith('/api/')
      ? BASE_URL + url
      : url;

    const id = fullUrl;

    const existing = openDocuments.find(
      d => d.id === id
    );

    if (!existing) {
      setOpenDocuments(prev => [
        ...prev,
        {
          id,
          url: fullUrl,
          title: title || 'Reference',
          page,
          search
        }
      ]);
    }

    setActiveDocId(id);
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-black text-white overflow-hidden">

      {/* HEADER */}
      <header className="h-[72px] border-b border-white/10 flex items-center justify-between px-6">

        <div className="flex items-center gap-4">

          <Link
            to={`/${domainId}`}
            className="flex items-center gap-2 text-xs text-gray-400 hover:text-white"
          >
            <ChevronLeft size={14} />
            Back
          </Link>

          <div>
            <h1 className="font-bold text-lg">
              {domainConfig.title}
            </h1>

            <p className="text-xs text-gray-500">
              {domainConfig.subtitle}
            </p>
          </div>

        </div>

        <div className="text-xs text-green-400">
          Active Workspace
        </div>

      </header>

      {/* BODY */}
      <div className="flex flex-1 overflow-hidden">

        {/* SIDEBAR */}
        <aside
          className={`border-r border-white/10 transition-all duration-300 ${isSidebarOpen
            ? 'w-[300px]'
            : 'w-0'
            } overflow-hidden`}
        >

          <div className="p-4 border-b border-white/10">

            <button
              onClick={handleNewSession}
              className="w-full bg-cyan-400 text-black py-3 rounded-xl text-xs font-bold"
            >
              NEW CONSULTATION
            </button>

          </div>

          <div className="overflow-y-auto h-full p-3 space-y-2">

            {sessions.map(session => (
              <div
                key={session.session_id}
                onClick={() =>
                  handleSelectSession(
                    session.session_id
                  )
                }
                className="p-3 border border-white/10 rounded-xl cursor-pointer hover:border-cyan-400"
              >

                <div className="flex items-center justify-between">

                  <div>

                    <p className="text-sm font-semibold">
                      {session.title}
                    </p>

                    <p className="text-[10px] text-gray-500">
                      {new Date(
                        session.updated_at
                      ).toLocaleDateString()}
                    </p>

                  </div>

                  <button
                    onClick={e =>
                      handleDeleteSession(
                        e,
                        session.session_id
                      )
                    }
                    className="text-red-500"
                  >
                    <Trash2 size={14} />
                  </button>

                </div>

              </div>
            ))}

          </div>

        </aside>

        {/* MAIN */}
        <main className="flex-1 flex flex-col overflow-hidden relative">

          <button
            onClick={() =>
              setIsSidebarOpen(
                !isSidebarOpen
              )
            }
            className="absolute top-4 left-4 z-10 p-2 border border-white/10 rounded-lg"
          >
            <Menu size={14} />
          </button>

          {/* CHAT */}
          <div className="flex-1 overflow-y-auto px-8 py-10">

            <div className="max-w-4xl mx-auto space-y-8">

              {messages.length === 0 ? (
                <div className="space-y-4">

                  <h2 className="text-2xl font-bold">
                    How can LETA assist you today?
                  </h2>

                  <p className="text-gray-400 text-sm">
                    Describe your GST issue,
                    statutory notice,
                    drafting requirement,
                    or legal consultation.
                  </p>

                </div>
              ) : (
                messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.role === 'user'
                      ? 'justify-end'
                      : 'justify-start'
                      }`}
                  >

                    {msg.role === 'user' ? (
                      <div className="max-w-[70%] bg-cyan-500 text-black rounded-2xl px-5 py-4 text-sm">
                        {msg.content}
                      </div>
                    ) : (
                      <div className="w-full">

                        <LetaResponse
                          onRegenerate={() => { }}
                          data={{
                            query: '',
                            answer: msg.content,
                            citations:
                              msg.citations || [],
                            consulted_sources:
                              msg.consulted_sources ||
                              [],
                            confidence:
                              msg.confidence ||
                              0.95,
                            status:
                              msg.current_status
                          }}
                          isDark
                          animate={!msg.isHistory}
                          onDocumentClick={
                            handleDocumentClick
                          }
                        />

                      </div>
                    )}

                  </div>
                ))
              )}

              {isLoading && (
                <div className="flex justify-center">
                  <SimpleSearchLoader />
                </div>
              )}

              <div ref={messagesEndRef} />

            </div>

          </div>

          {/* INPUT */}
          <div className="border-t border-white/10 p-6">

            <div className="max-w-4xl mx-auto relative">

              <AnimatePresence>

                {selectedFile && (
                  <div className="absolute -top-12 left-0 bg-zinc-900 border border-white/10 rounded-lg px-3 py-2 text-xs">
                    {selectedFile.name}
                  </div>
                )}

              </AnimatePresence>

              <textarea
                ref={textareaRef}
                value={query}
                onChange={e =>
                  setQuery(e.target.value)
                }
                placeholder={
                  domainConfig.placeholder
                }
                className="w-full bg-black border border-white/10 rounded-2xl p-5 pr-36 min-h-[100px] text-sm resize-none outline-none"
                onKeyDown={e => {
                  if (
                    e.key === 'Enter' &&
                    !e.shiftKey
                  ) {
                    e.preventDefault();
                    handleAsk();
                  }
                }}
              />

              <div className="absolute bottom-4 right-4 flex items-center gap-2">

                <input
                  type="file"
                  ref={fileInputRef}
                  className="hidden"
                  onChange={e => {
                    if (
                      e.target.files?.[0]
                    ) {
                      setSelectedFile(
                        e.target.files[0]
                      );
                    }
                  }}
                />

                <button
                  onClick={() =>
                    fileInputRef.current?.click()
                  }
                  className="p-2 text-gray-400 hover:text-white"
                >
                  <Paperclip size={16} />
                </button>

                {isStreaming ? (
                  <button
                    onClick={handleStop}
                    className="bg-red-500 text-white px-5 py-2 rounded-xl text-xs font-bold flex items-center gap-2"
                  >

                    <Square
                      size={12}
                      fill="currentColor"
                    />

                    STOP

                  </button>
                ) : (
                  <button
                    onClick={handleAsk}
                    disabled={
                      !query.trim() &&
                      !selectedFile
                    }
                    className="bg-cyan-400 text-black px-5 py-2 rounded-xl text-xs font-bold flex items-center gap-2 disabled:opacity-50"
                  >

                    <Send size={12} />

                    ANALYZE

                  </button>
                )}

              </div>

            </div>

          </div>

        </main>

        {/* RIGHT PANEL */}
        <aside className="w-[320px] border-l border-white/10 overflow-hidden">

          {openDocuments.length > 0 ? (
            openDocuments.map(
              doc =>
                doc.id ===
                activeDocId && (
                  <DocumentViewer
                    key={doc.id}
                    url={doc.url}
                    onClose={() =>
                      setOpenDocuments([])
                    }
                    title={doc.title}
                    initialPage={doc.page}
                    keyword={doc.search}
                  />
                )
            )
          ) : (
            <div className="p-6 space-y-6">

              <div>

                <p className="text-xs uppercase text-gray-500 mb-3">
                  Workspace Context
                </p>

                <div className="border border-white/10 rounded-xl p-4 space-y-3">

                  <div className="flex justify-between text-sm">

                    <span className="text-gray-500">
                      Domain
                    </span>

                    <span>GST</span>

                  </div>

                  <div className="flex justify-between text-sm">

                    <span className="text-gray-500">
                      Sources
                    </span>

                    <span>
                      {messages[
                        messages.length - 1
                      ]?.consulted_sources
                        ?.length || 0}
                    </span>

                  </div>

                </div>

              </div>

            </div>
          )}

        </aside>

      </div>

    </div>
  );
};

export default LetaWorkspace;