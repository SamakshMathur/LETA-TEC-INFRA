import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, MessageSquare, Trash2, Clock, Terminal } from 'lucide-react';
import axios from 'axios';
import { BASE_URL } from '../../config/api';

const ChatSidebar = ({ currentSessionId, onSelectSession, onNewSession, isOpen, toggleSidebar }) => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSessions();
    // Poll for updates every 60s
    const interval = setInterval(fetchSessions, 60000);
    return () => clearInterval(interval);
  }, [currentSessionId]); // Refetch when session changes (e.g. title update)

  const fetchSessions = async () => {
    try {
      const baseUrl = BASE_URL;
      const res = await axios.get(`${baseUrl}/api/sessions/list`);
      setSessions(res.data);
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
    }
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    try {
      const baseUrl = BASE_URL;
      await axios.delete(`${baseUrl}/api/sessions/${id}`);
      fetchSessions();
      if (currentSessionId === id) {
        onNewSession();
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  return (
    <motion.div 
      initial={{ width: isOpen ? 280 : 0, opacity: isOpen ? 1 : 0 }}
      animate={{ width: isOpen ? 280 : 0, opacity: isOpen ? 1 : 0 }}
      className={`h-full bg-[#050A10] border-r border-white/10 flex flex-col overflow-hidden transition-all duration-300 ${!isOpen ? 'w-0 p-0' : 'w-72'}`}
    >
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <button 
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 bg-sentinel-green/10 hover:bg-sentinel-green text-sentinel-green hover:text-white border border-sentinel-green py-2 rounded-sm transition-all font-mono font-bold uppercase tracking-widest text-xs shadow-[0_0_15px_rgba(16,185,129,0.15)] hover:shadow-[0_0_20px_rgba(16,185,129,0.4)]"
        >
          <Plus className="w-4 h-4" />
          New Analysis
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1 custom-scrollbar">
        {sessions.length === 0 ? (
          <div className="text-center text-gray-500 mt-10 text-xs">
            <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
            No history found
          </div>
        ) : (
          <AnimatePresence>
            {sessions.map((session) => (
              <motion.div
                key={session.session_id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                onClick={() => onSelectSession(session.session_id)}
                className={`group flex items-center gap-3 p-3 rounded-sm cursor-pointer transition-all relative font-mono
                  ${currentSessionId === session.session_id 
                    ? 'bg-[#020202] text-sentinel-green border-l-2 border-l-sentinel-green shadow-inner' 
                    : 'text-gray-500 hover:bg-white/5 hover:text-gray-300 border-l-2 border-l-transparent'
                  }`}
              >
                <Terminal className="w-4 h-4 flex-shrink-0" />
                
                <div className="flex-1 overflow-hidden">
                  <h3 className="text-sm font-medium truncate pr-6" title={session.title || "New Chat"}>
                    {session.title || "New Chat"}
                  </h3>
                  <span className="text-[10px] text-gray-500 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {new Date(session.updated_at).toLocaleDateString()}
                  </span>
                </div>

                <button 
                  onClick={(e) => handleDelete(e, session.session_id)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 hover:text-red-500 rounded transition-all"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
      
      {/* Footer / User Info */}
      <div className="p-4 border-t border-white/10 text-[10px] text-gray-500 text-center font-mono uppercase tracking-widest flex items-center justify-center gap-2">
        <span className="w-2 h-2 rounded-full bg-sentinel-green animate-pulse" />
        MEM_CORE_ACTIVE
      </div>
    </motion.div>
  );
};

export default ChatSidebar;
