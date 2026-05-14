import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Clock, Cpu } from 'lucide-react';

const INITIAL_FEED_ITEMS = [
  { id: 1, text: 'GST Circular 177/2022 Indexed & Context-Hashed', type: 'INDEX', time: '12:44:03' },
  { id: 2, text: 'Refund Limitation Analysis Generated for Section 54(3)', type: 'ANALYSIS', time: '12:43:55' },
  { id: 3, text: 'Section 17(5) Blocked Credit Interpretation Updated', type: 'UPDATE', time: '12:43:12' },
  { id: 4, text: 'Input Tax Credit Risk Signature Detected on Construction Invoices', type: 'ALERT', time: '12:42:01' },
  { id: 5, text: 'FEMA Regulatory Compliance Node Activated (FEMA 20R/2017)', type: 'NODE', time: '12:41:45' },
  { id: 6, text: 'NCLT Tribunal Restructuring Citation Indexing Finished', type: 'INDEX', time: '12:40:12' },
  { id: 7, text: 'Filing Timeline Circular 183 Statutory Exception Synced', type: 'UPDATE', time: '12:39:50' },
];

const NEW_FEED_GENERATOR = [
  { text: 'Customs Notification 44/2023 Import Classification Hashed', type: 'INDEX' },
  { text: 'Supreme Court Rule of Law Judgment Citation Integrated', type: 'ANALYSIS' },
  { text: 'CGST Rule 37A Reversal Condition Audit Trace Updated', type: 'ALERT' },
  { text: 'SEZ Zero-Rated Supply Interpretation Audit Sync Completed', type: 'UPDATE' },
  { text: 'Direct Tax Section 43B(h) Ingestion Matrix Mapped', type: 'NODE' },
];

const IntelligenceFeed = () => {
  const [feed, setFeed] = useState(INITIAL_FEED_ITEMS);

  useEffect(() => {
    // Subtly inject new live events to give a terminal feed atmosphere
    const interval = setInterval(() => {
      const randomNew = NEW_FEED_GENERATOR[Math.floor(Math.random() * NEW_FEED_GENERATOR.length)];
      const now = new Date();
      const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
      
      const newItem = {
        id: Date.now(),
        text: randomNew.text,
        type: randomNew.type,
        time: timeStr,
      };

      setFeed(prev => [newItem, ...prev.slice(0, 6)]);
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  return (
    <section className="py-[80px] bg-[#070B11] relative overflow-hidden border-t border-b border-white/[0.03]">
      <div className="max-w-[1600px] mx-auto px-10 lg:px-20 relative z-10">
        
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-16 items-center">
          
          {/* Left Column: Descriptive Context */}
          <div className="lg:col-span-5 flex flex-col justify-center space-y-6">
            <div className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-[#67E8F9] font-bold">
              <Activity size={14} className="animate-pulse" />
              <span>Real-Time Operation Feed</span>
            </div>
            <h2 className="font-display font-bold text-3xl md:text-5xl text-white uppercase tracking-tight leading-tight">
              Sovereign Legal Intelligence Feed
            </h2>
            <p className="font-body text-[#A1AAB8] text-base leading-relaxed font-light">
              LETA constantly reads, hashes, and indexes India's statutory frameworks, updates, circulars, and dispute outcomes. Watch the continuous operations matrix in action.
            </p>

            <div className="flex items-center gap-6 pt-4 border-t border-white/[0.04]">
              <div className="flex items-center gap-2 font-mono text-xs text-[#6B7280]">
                <Clock size={12} />
                <span>Auto-indexing Every 5s</span>
              </div>
              <div className="flex items-center gap-2 font-mono text-xs text-[#6B7280]">
                <Cpu size={12} />
                <span>Encrypted Connection Status</span>
              </div>
            </div>
          </div>

          {/* Right Column: Dynamic Terminal Feed */}
          <div className="lg:col-span-7">
            <div className="rounded-leta border border-white/[0.06] bg-[#10141B]/80 backdrop-blur-md overflow-hidden">
              
              {/* Header */}
              <div className="px-6 py-4 flex items-center justify-between bg-white/[0.02] border-b border-white/[0.04]">
                <div className="flex items-center gap-2.5">
                  <span className="w-2 h-2 rounded-full bg-[#67E8F9] animate-pulse" />
                  <span className="font-mono text-xs uppercase tracking-widest text-[#F5F7FA] font-bold">
                    TITAN_INDEX_LOGGER_ACTIVE
                  </span>
                </div>
                <span className="font-mono text-[9px] text-[#6B7280]">SYSTEM STATUS: NOMINAL</span>
              </div>

              {/* Logger feed wrapper */}
              <div className="p-6 space-y-3 min-h-[380px]">
                <AnimatePresence initial={false}>
                  {feed.map((item) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, x: -10, y: -5 }}
                      animate={{ opacity: 1, x: 0, y: 0 }}
                      exit={{ opacity: 0, scale: 0.98 }}
                      transition={{ duration: 0.35, ease: 'easeOut' }}
                      className="p-4 rounded-xl bg-white/[0.01] hover:bg-white/[0.02] border border-white/[0.03] flex items-center justify-between gap-6 transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        {/* Feed Item Type indicator */}
                        <span className={`px-2.5 py-0.5 rounded font-mono text-[8px] font-bold tracking-widest ${
                          item.type === 'INDEX'
                            ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                            : item.type === 'ALERT'
                            ? 'bg-red-500/10 text-red-400 border border-red-500/20'
                            : item.type === 'NODE'
                            ? 'bg-purple-500/10 text-[#67E8F9] border border-purple-500/20'
                            : 'bg-green-500/10 text-emerald-400 border border-green-500/20'
                        }`}>
                          {item.type}
                        </span>

                        <p className="font-mono text-xs text-[#A1AAB8] leading-normal font-light">
                          {item.text}
                        </p>
                      </div>

                      {/* Timestamp */}
                      <span className="font-mono text-[10px] text-[#52525B] whitespace-nowrap">
                        {item.time}
                      </span>
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
