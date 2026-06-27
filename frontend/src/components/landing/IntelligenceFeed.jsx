import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Clock, Cpu, Wifi, WifiOff } from 'lucide-react';

// ── Synthetic fallback pool (shown when backend has no data yet) ─────────────
const SYNTHETIC_POOL = [
  { text: 'GST Circular 177/2022 Indexed & Context-Hashed', type: 'INDEX' },
  { text: 'Refund Limitation Analysis Generated for Section 54(3)', type: 'ANALYSIS' },
  { text: 'Section 17(5) Blocked Credit Interpretation Updated', type: 'UPDATE' },
  { text: 'Input Tax Credit Risk Signature Detected on Construction Invoices', type: 'ALERT' },
  { text: 'FEMA Regulatory Compliance Node Activated (FEMA 20R/2017)', type: 'NODE' },
  { text: 'NCLT Tribunal Restructuring Citation Indexing Finished', type: 'INDEX' },
  { text: 'Filing Timeline Circular 183 Statutory Exception Synced', type: 'UPDATE' },
  { text: 'Customs Notification 44/2023 Import Classification Hashed', type: 'INDEX' },
  { text: 'Supreme Court Rule of Law Judgment Citation Integrated', type: 'ANALYSIS' },
  { text: 'CGST Rule 37A Reversal Condition Audit Trace Updated', type: 'ALERT' },
  { text: 'SEZ Zero-Rated Supply Interpretation Audit Sync Completed', type: 'UPDATE' },
  { text: 'Direct Tax Section 43B(h) Ingestion Matrix Mapped', type: 'NODE' },
];

function now() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
}

function syntheticItem() {
  const pick = SYNTHETIC_POOL[Math.floor(Math.random() * SYNTHETIC_POOL.length)];
  return { id: `syn_${Date.now()}`, text: pick.text, type: pick.type, time: now(), source: 'synthetic' };
}

// ── Badge colours ─────────────────────────────────────────────────────────────
const BADGE = {
  INDEX:    'bg-blue-500/10 text-blue-400 border border-blue-500/20',
  ALERT:    'bg-red-500/10 text-red-400 border border-red-500/20',
  NODE:     'bg-purple-500/10 text-[#67E8F9] border border-purple-500/20',
  ANALYSIS: 'bg-green-500/10 text-emerald-400 border border-green-500/20',
  UPDATE:   'bg-green-500/10 text-emerald-400 border border-green-500/20',
};

// ── Component ─────────────────────────────────────────────────────────────────
const IntelligenceFeed = () => {
  const [feed, setFeed]           = useState([]);
  const [connected, setConnected] = useState(false);  // SSE status
  const [liveCount, setLiveCount] = useState(0);      // real events received this session
  const esRef     = useRef(null);
  const synTimer  = useRef(null);

  // ── Push a new item to the top, cap at 7 ──────────────────────────────────
  const pushItem = (item) =>
    setFeed(prev => [item, ...prev].slice(0, 7));

  // ── Synthetic ticker (only when connected but no admin activity) ───────────
  const startSyntheticTicker = () => {
    clearInterval(synTimer.current);
    synTimer.current = setInterval(() => {
      // Only inject synthetic events if we haven't received a real one recently
      pushItem(syntheticItem());
    }, 7000);
  };

  // ── REST: load recent real events on mount ─────────────────────────────────
  const loadRecent = async () => {
    try {
      const res = await fetch('/api/feed/recent?n=7');
      if (!res.ok) return;
      const data = await res.json();
      if (data.length > 0) {
        setFeed(data.slice(0, 7));
      } else {
        // No real data yet — seed with synthetics
        setFeed(SYNTHETIC_POOL.slice(0, 7).map((s, i) => ({
          id: `init_${i}`,
          text: s.text,
          type: s.type,
          time: now(),
          source: 'synthetic',
        })));
      }
    } catch {
      // Backend unreachable — seed synthetics
      setFeed(SYNTHETIC_POOL.slice(0, 7).map((s, i) => ({
        id: `init_${i}`,
        text: s.text,
        type: s.type,
        time: now(),
        source: 'synthetic',
      })));
    }
  };

  // ── SSE connection ─────────────────────────────────────────────────────────
  useEffect(() => {
    loadRecent();

    let retryDelay = 3000;
    let dead = false;

    const connect = () => {
      if (dead) return;

      const es = new EventSource('/api/feed/stream');
      esRef.current = es;

      es.onopen = () => {
        setConnected(true);
        retryDelay = 3000;          // reset backoff on success
        startSyntheticTicker();     // keep the feed visually alive
      };

      es.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data);
          if (!ev.id) return;

          // Mark real events from the server
          const item = {
            ...ev,
            id: `live_${ev.id}_${Date.now()}`,
            source: ev.source || 'live',
          };

          // Real upload event from admin — clear synthetic ticker temporarily
          // and show it immediately with a "live" badge boost
          if (item.source === 'live') {
            setLiveCount(c => c + 1);
            clearInterval(synTimer.current);
            // Restart synthetic ticker after 15 s
            setTimeout(startSyntheticTicker, 15000);
          }

          pushItem(item);
        } catch {
          // malformed event — ignore
        }
      };

      es.onerror = () => {
        setConnected(false);
        es.close();
        // Exponential backoff, cap at 30 s
        if (!dead) {
          setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 1.5, 30000);
        }
      };
    };

    connect();

    return () => {
      dead = true;
      clearInterval(synTimer.current);
      esRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <section style={{
      padding: '80px 0',
      background: '#000000',
      position: 'relative', overflow: 'hidden',
      borderTop: '1px solid rgba(255,255,255,0.03)',
      borderBottom: '1px solid rgba(255,255,255,0.03)',
    }}>
      <div className="section-container">

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-16 items-center">

          {/* Left Column */}
          <div className="lg:col-span-5 flex flex-col justify-center space-y-6">
            <p className="section-eyebrow">// Real-Time Operation Feed</p>
            <h2 className="section-headline">
              Legal Intelligence<br />Feed
            </h2>
            <p className="section-subhead">
              LETA constantly reads, hashes, and indexes India's statutory frameworks,
              updates, circulars, and dispute outcomes. Every document uploaded by the
              admin team appears here instantly.
            </p>

            <div className="flex items-center gap-6 pt-4 border-t border-white/[0.04]">
              <div className="flex items-center gap-2 font-mono text-xs text-[#6B7280]">
                <Clock size={12} />
                <span>Auto-indexing Every 5s</span>
              </div>
              <div className={`flex items-center gap-2 font-mono text-xs transition-colors ${connected ? 'text-emerald-400' : 'text-[#6B7280]'}`}>
                {connected
                  ? <Wifi size={12} />
                  : <WifiOff size={12} />}
                <span>{connected ? 'Live Stream Active' : 'Connecting...'}</span>
              </div>
            </div>

            {liveCount > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 w-fit"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-mono text-[10px] text-emerald-400 uppercase tracking-wider">
                  {liveCount} live event{liveCount > 1 ? 's' : ''} received
                </span>
              </motion.div>
            )}
          </div>

          {/* Right Column: Terminal Feed */}
          <div className="lg:col-span-7">
            <div style={{ border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(10,15,24,0.8)', backdropFilter: 'blur(12px)', overflow: 'hidden' }}>

              {/* Header */}
              <div className="px-6 py-4 flex items-center justify-between bg-white/[0.02] border-b border-white/[0.04]">
                <div className="flex items-center gap-2.5">
                  <span className={`w-2 h-2 rounded-full animate-pulse ${connected ? 'bg-[#67E8F9]' : 'bg-yellow-500'}`} />
                  <span className="font-mono text-xs uppercase tracking-widest text-[#F5F7FA] font-bold">
                    TITAN_INDEX_LOGGER_ACTIVE
                  </span>
                </div>
                <span className="font-mono text-[9px] text-[#6B7280]">
                  {connected ? 'SYSTEM STATUS: NOMINAL' : 'SYSTEM STATUS: RECONNECTING'}
                </span>
              </div>

              {/* Feed rows */}
              <div className="p-6 space-y-3 min-h-[380px]">
                <AnimatePresence initial={false}>
                  {feed.map((item) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, x: -10, y: -5 }}
                      animate={{ opacity: 1, x: 0, y: 0 }}
                      exit={{ opacity: 0, scale: 0.98 }}
                      transition={{ duration: 0.35, ease: 'easeOut' }}
                      className={`p-4 rounded-xl border flex items-center justify-between gap-6 transition-colors ${
                        item.source === 'live'
                          ? 'bg-emerald-500/[0.04] border-emerald-500/20 hover:bg-emerald-500/[0.06]'
                          : 'bg-white/[0.01] border-white/[0.03] hover:bg-white/[0.02]'
                      }`}
                    >
                      <div className="flex items-center gap-4 min-w-0">
                        <span className={`shrink-0 px-2.5 py-0.5 rounded font-mono text-[8px] font-bold tracking-widest ${BADGE[item.type] ?? BADGE.UPDATE}`}>
                          {item.type}
                        </span>
                        <p className="font-mono text-xs text-[#A1AAB8] leading-normal font-light truncate">
                          {item.text}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {item.source === 'live' && (
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" title="Live event" />
                        )}
                        <span className="font-mono text-[10px] text-[#52525B] whitespace-nowrap">
                          {item.time}
                        </span>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>

            </div>
          </div>

        </div>

      </div>
    </section>
  );
};

export default IntelligenceFeed;
