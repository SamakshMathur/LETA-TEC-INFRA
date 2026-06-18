import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Scale, BadgeCheck, BookOpen, Briefcase, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

const CREDENTIALS = [
  { icon: BadgeCheck, label: 'Chartered Accountant',  sub: 'ICAI Certified' },
  { icon: Scale,      label: 'GST & Indirect Tax',    sub: '42,000+ Provisions Indexed' },
  { icon: BookOpen,   label: 'Judicial Precedents',   sub: '1,400+ HC / SC Judgments' },
  { icon: Briefcase,  label: 'Litigation Advisory',   sub: 'SCN · DRC · Appeal Drafting' },
];

// Demo conversation — realistic CA-style exchange
const CONVERSATION = [
  {
    role: 'user',
    text: 'As per my understanding, the intermediary services provided by our Indian company to a foreign principal should qualify as export of service under Section 2(6) of the IGST Act. Please advise.',
    delay: 0,
  },
  {
    role: 'bot',
    isTyping: true,
    delay: 1200,
    text: null,
  },
  {
    role: 'bot',
    delay: 3200,
    label: 'POSITION',
    text: "Your understanding requires correction. Intermediary services do **not** qualify as export of service — the place of supply is India under Section 13(8)(b) of the IGST Act, irrespective of where the foreign principal is located.",
    chips: ['Section 13(8)(b) IGST Act', 'Circular 159/15/2021', 'Section 2(6) IGST Act'],
    confidence: '⚠️ High Litigation Exposure',
    confColor: '#F59E0B',
  },
  {
    role: 'user',
    text: 'Can you give me the detailed advisory and also draft a reply to the SCN we received on this issue?',
    delay: 5800,
  },
  {
    role: 'bot',
    isTyping: true,
    delay: 7000,
    text: null,
  },
  {
    role: 'bot',
    delay: 8800,
    label: 'DETAILED ADVISORY',
    text: "Under Section 13(8)(b), for intermediary services the place of supply is the location of the supplier — i.e., India. CBIC Circular 159/15/2021 expressly clarified that intermediaries cannot claim the 'place of supply = location of recipient' benefit. The Hon'ble Bombay High Court in **Dharmendra M. Jani v. UOI** upheld this position. Your GST liability stands; ITC claimed as if zero-rated may be recoverable.",
    chips: ['DRC-01 Reply', 'Block A→H Draft', 'Circular 159/15/2021'],
    confidence: '✅ Settled — High Court Confirmed',
    confColor: '#22C55E',
  },
];

const TypingDots = () => (
  <div className="flex items-center gap-1 px-4 py-3">
    {[0, 1, 2].map(i => (
      <motion.div
        key={i}
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: '#4FB7C5' }}
        animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.1, 0.8] }}
        transition={{ duration: 0.9, delay: i * 0.18, repeat: Infinity }}
      />
    ))}
  </div>
);

const Chip = ({ label }) => (
  <span
    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-mono font-semibold uppercase tracking-wider cursor-default"
    style={{ background: 'rgba(79,183,197,0.1)', border: '1px solid rgba(79,183,197,0.25)', color: '#67E8F9' }}
  >
    {label}
  </span>
);

const Message = ({ msg }) => {
  const isUser = msg.role === 'user';

  if (msg.isTyping) {
    return (
      <div className="flex items-end gap-2">
        <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: 'rgba(79,183,197,0.12)', border: '1px solid rgba(79,183,197,0.2)' }}>
          <Scale size={13} style={{ color: '#4FB7C5' }} />
        </div>
        <div className="rounded-2xl rounded-bl-sm" style={{ background: '#0F1722', border: '1px solid rgba(255,255,255,0.06)' }}>
          <TypingDots />
        </div>
      </div>
    );
  }

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[75%] px-4 py-3 rounded-2xl rounded-br-sm text-sm leading-relaxed"
          style={{ background: 'rgba(79,183,197,0.1)', border: '1px solid rgba(79,183,197,0.18)', color: '#E2E8F0', fontFamily: "'Times New Roman', serif" }}
        >
          {msg.text}
        </div>
      </div>
    );
  }

  // Bot message
  return (
    <div className="flex items-end gap-2">
      <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 flex-shrink-0"
        style={{ background: 'rgba(79,183,197,0.12)', border: '1px solid rgba(79,183,197,0.2)' }}>
        <Scale size={13} style={{ color: '#4FB7C5' }} />
      </div>
      <div
        className="max-w-[80%] rounded-2xl rounded-bl-sm px-4 py-3 space-y-2"
        style={{ background: '#0F1722', border: '1px solid rgba(255,255,255,0.06)' }}
      >
        {msg.label && (
          <span className="text-[9px] font-mono font-bold uppercase tracking-[0.18em]" style={{ color: '#4FB7C5' }}>
            {msg.label}
          </span>
        )}
        <p className="text-sm leading-relaxed" style={{ color: '#CBD5E1', fontFamily: "'Times New Roman', serif" }}
          dangerouslySetInnerHTML={{ __html: msg.text.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#F1F5F9">$1</strong>') }}
        />
        {msg.chips && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {msg.chips.map((c, i) => <Chip key={i} label={c} />)}
          </div>
        )}
        {msg.confidence && (
          <p className="text-[10px] font-mono font-semibold pt-0.5" style={{ color: msg.confColor }}>
            {msg.confidence}
          </p>
        )}
      </div>
    </div>
  );
};

const CABotDemo = () => {
  const [visible, setVisible] = useState([]);
  const [started, setStarted]  = useState(false);
  const bottomRef  = useRef(null);
  const scrollRef  = useRef(null);

  // Scroll only inside the chat box — never the page
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [visible]);

  // Start replaying on mount / loop
  useEffect(() => {
    let timers = [];
    const play = () => {
      setVisible([]);
      setStarted(true);
      CONVERSATION.forEach((msg, i) => {
        const t = setTimeout(() => {
          setVisible(prev => {
            // Replace typing bubble with real message when next bot msg arrives
            if (!msg.isTyping && i > 0 && CONVERSATION[i - 1]?.isTyping) {
              return [...prev.slice(0, -1), msg];
            }
            return [...prev, msg];
          });
        }, msg.delay);
        timers.push(t);
      });
      // Loop after last message
      const loopDelay = CONVERSATION[CONVERSATION.length - 1].delay + 6000;
      const loop = setTimeout(play, loopDelay);
      timers.push(loop);
    };
    play();
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <section style={{ padding: '80px 0', background: '#000000', position: 'relative', overflow: 'hidden', borderTop: '1px solid rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>

      {/* Subtle background orb */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(79,183,197,0.04) 0%, transparent 65%)', filter: 'blur(60px)' }} />

      <div className="section-container" style={{ position: 'relative', zIndex: 10 }}>

        {/* Section header */}
        <div className="mb-16 max-w-2xl">
          <p className="section-eyebrow">// AI-Powered CA Advisory</p>
          <h2 className="section-headline">
            Your Senior CA,<br />
            <span style={{ color: '#4FB7C5' }}>Available 24 × 7</span>
          </h2>
          <p className="section-subhead">
            LETA reasons like a senior CA partner — analysing statutes, citing circulars, flagging litigation risk, and drafting replies on demand.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">

          {/* Left — CA credentials card */}
          <div className="lg:col-span-4 space-y-4">

            {/* Avatar card */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.7 }}
              className="rounded-2xl p-6 premium-card"
              style={{ border: '1px solid rgba(79,183,197,0.22)' }}
            >
              <div className="flex items-center gap-4 mb-6">
                <div className="relative">
                  <div className="w-14 h-14 rounded-xl flex items-center justify-center"
                    style={{ background: 'rgba(79,183,197,0.1)', border: '1px solid rgba(79,183,197,0.25)' }}>
                    <Scale size={26} style={{ color: '#4FB7C5' }} />
                  </div>
                  {/* Online indicator */}
                  <span className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-[#0A0F1A]"
                    style={{ background: '#22C55E' }} />
                </div>
                <div>
                  <h3 className="font-display font-bold text-white text-lg leading-none">LETA</h3>
                  <p className="text-[11px] font-mono tracking-wider mt-1" style={{ color: '#4FB7C5' }}>TEC AI — Senior CA</p>
                  <p className="text-[10px] font-mono mt-0.5" style={{ color: '#475569' }}>Online · Instant Response</p>
                </div>
              </div>

              <div className="space-y-3">
                {CREDENTIALS.map(({ icon: Icon, label, sub }, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.1 + i * 0.08 }}
                    className="flex items-center gap-3 p-3 rounded-xl"
                    style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}
                  >
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ background: 'rgba(79,183,197,0.08)' }}>
                      <Icon size={13} style={{ color: '#4FB7C5' }} />
                    </div>
                    <div>
                      <p className="text-[12px] font-semibold text-white leading-none">{label}</p>
                      <p className="text-[10px] font-mono mt-0.5" style={{ color: '#475569' }}>{sub}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>

            {/* CTA */}
            <Link to="/gst">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-semibold text-sm text-black transition-all"
                style={{ background: '#4FB7C5' }}
              >
                Start Consultation <ChevronRight size={15} />
              </motion.button>
            </Link>
          </div>

          {/* Right — Live chat demo */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="lg:col-span-8 rounded-2xl overflow-hidden flex flex-col premium-card"
            style={{ minHeight: '520px' }}
          >
            {/* Chat header */}
            <div className="flex items-center justify-between px-5 py-3.5 flex-shrink-0"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: 'rgba(15,23,34,0.8)' }}>
              <div className="flex items-center gap-2.5">
                <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: '#22C55E' }} />
                <span className="text-[11px] font-mono uppercase tracking-[0.18em]" style={{ color: '#4FB7C5' }}>
                  LETA · GST Advisory Session
                </span>
              </div>
              <span className="text-[10px] font-mono" style={{ color: '#2a3050' }}>LIVE DEMO</span>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-5 space-y-4" style={{ maxHeight: '460px' }}>
              <AnimatePresence>
                {visible.map((msg, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <Message msg={msg} />
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>

            {/* Fake input bar */}
            <div className="px-5 py-3 flex-shrink-0"
              style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
              <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl"
                style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                <span className="text-xs flex-1" style={{ color: '#2a3050', fontFamily: "'Times New Roman', serif" }}>
                  Ask LETA a GST or tax question...
                </span>
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#4FB7C5' }} />
                  <span className="text-[9px] font-mono" style={{ color: '#4FB7C5' }}>AI READY</span>
                </div>
              </div>
            </div>
          </motion.div>

        </div>
      </div>
    </section>
  );
};

export default CABotDemo;
