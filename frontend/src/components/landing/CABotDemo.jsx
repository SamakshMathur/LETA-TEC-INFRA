import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Scale } from 'lucide-react';
import { Link } from 'react-router-dom';
import legalImg from '../../pages/IMAGES/magnific_futuristic-ai-data-pipeli_9Rx1osxNYZ.jpeg';

const CONVERSATION = [
  {
    role: 'user',
    text: 'My client provides support services to a US company. They got an SCN saying this isn\'t export — is that correct?',
    delay: 0,
  },
  { role: 'bot', isTyping: true, delay: 900, text: null },
  {
    role: 'bot',
    delay: 2500,
    label: 'POSITION',
    text: 'The SCN is correct. If your client is an **intermediary** (arranging services between the US co. and a third party), place of supply is India under §13(8)(b) — it\'s taxable GST, not export.',
    chips: ['§13(8)(b) IGST', 'Circular 159/15/2021'],
    confidence: '⚠ High Litigation Exposure',
    confType: 'warn',
  },
  {
    role: 'user',
    text: 'Can you draft the DRC-01 reply for us? Hearing is next week.',
    delay: 4600,
  },
  { role: 'bot', isTyping: true, delay: 5600, text: null },
  {
    role: 'bot',
    delay: 7200,
    label: 'ADVISORY',
    text: "Done. DRC-01 reply drafted across Blocks A–H — citing Circular 159/15/2021 and **Bombay HC in Dharmendra M. Jani v. UOI**. Ground: taxpayer classified as intermediary, §13(8)(b) applies.",
    chips: ['DRC-01 Draft Ready', 'Circular 159/2021'],
    confidence: '✓ Settled — HC Confirmed',
    confType: 'ok',
  },
];

const TypingDots = () => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '8px 12px' }}>
    {[0, 1, 2].map(i => (
      <motion.div key={i}
        style={{ width: 4, height: 4, borderRadius: '50%', background: '#4FB7C5' }}
        animate={{ opacity: [0.2, 1, 0.2] }}
        transition={{ duration: 0.9, delay: i * 0.2, repeat: Infinity }}
      />
    ))}
  </div>
);

const Chip = ({ label }) => (
  <span style={{
    padding: '2px 7px', fontSize: 7.5,
    fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700,
    textTransform: 'uppercase', letterSpacing: '0.1em',
    border: '1px solid rgba(79,183,197,0.2)', color: 'rgba(79,183,197,0.7)',
  }}>{label}</span>
);

const Message = ({ msg }) => {
  const isUser = msg.role === 'user';

  if (msg.isTyping) return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
      <div style={{ width: 22, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, border: '1px solid rgba(79,183,197,0.18)' }}>
        <Scale size={10} style={{ color: '#4FB7C5' }} />
      </div>
      <div style={{ background: 'rgba(4,8,14,0.7)', border: '1px solid rgba(255,255,255,0.05)' }}>
        <TypingDots />
      </div>
    </div>
  );

  if (isUser) return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <p style={{
        maxWidth: '72%', margin: 0, padding: '9px 13px',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.07)',
        fontSize: 14, lineHeight: 1.65, color: 'rgba(203,213,225,0.8)',
        fontFamily: "'Inter', sans-serif",
      }}>{msg.text}</p>
    </div>
  );

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
      <div style={{ width: 22, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, border: '1px solid rgba(79,183,197,0.18)', marginTop: 2 }}>
        <Scale size={10} style={{ color: '#4FB7C5' }} />
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 7 }}>
        {msg.label && (
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 7, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.22em', color: '#4FB7C5', opacity: 0.7 }}>
            {msg.label}
          </span>
        )}
        <p style={{ fontSize: 14, lineHeight: 1.75, color: 'rgba(148,163,184,0.9)', fontFamily: "'Inter', sans-serif", margin: 0 }}
          dangerouslySetInnerHTML={{ __html: msg.text.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#e2e8f0;font-weight:600">$1</strong>') }}
        />
        {msg.chips && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {msg.chips.map((c, i) => <Chip key={i} label={c} />)}
          </div>
        )}
        {msg.confidence && (
          <p style={{
            fontFamily: "'IBM Plex Mono', monospace", fontSize: 8, fontWeight: 600, margin: 0, letterSpacing: '0.08em',
            color: msg.confType === 'ok' ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.32)',
          }}>{msg.confidence}</p>
        )}
      </div>
    </div>
  );
};

const CABotDemo = () => {
  const [visible, setVisible] = useState([]);
  const scrollRef  = useRef(null);
  const sectionRef = useRef(null);
  const bgRef      = useRef(null);

  // Counter-scroll the background so it appears fixed while the section scrolls
  useEffect(() => {
    const onScroll = () => {
      if (!sectionRef.current || !bgRef.current) return;
      const top = sectionRef.current.getBoundingClientRect().top;
      bgRef.current.style.transform = `translateY(${-top}px)`;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [visible]);

  useEffect(() => {
    let timers = [];
    const play = () => {
      setVisible([]);
      CONVERSATION.forEach((msg, i) => {
        const t = setTimeout(() => {
          setVisible(prev => {
            if (!msg.isTyping && i > 0 && CONVERSATION[i - 1]?.isTyping) {
              return [...prev.slice(0, -1), msg];
            }
            return [...prev, msg];
          });
        }, msg.delay);
        timers.push(t);
      });
      timers.push(setTimeout(play, CONVERSATION[CONVERSATION.length - 1].delay + 7000));
    };
    play();
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <section ref={sectionRef} style={{
      position: 'relative', overflow: 'hidden',
      borderTop: '1px solid rgba(255,255,255,0.04)',
    }}>

      {/* Background image — counter-scrolled to appear viewport-fixed */}
      <div ref={bgRef} style={{
        position: 'absolute', inset: 0, zIndex: 0,
        backgroundImage: `url(${legalImg})`,
        backgroundSize: 'cover',
        backgroundPosition: '60% 30%',
        willChange: 'transform',
      }} />

      {/* Deep overlay — lighter on the right so the image bleeds behind the chat panel */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 1, pointerEvents: 'none',
        background: 'linear-gradient(to right, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.75) 45%, rgba(0,0,0,0.55) 100%)' }} />
      {/* Top/bottom fade */}
      <div style={{ position: 'absolute', inset: 0, zIndex: 1, pointerEvents: 'none',
        background: 'linear-gradient(180deg, rgba(0,0,0,0.55) 0%, transparent 25%, transparent 75%, rgba(0,0,0,0.7) 100%)' }} />

      {/* Bottom bleed into next section */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 100, zIndex: 2, pointerEvents: 'none',
        background: 'linear-gradient(to bottom, transparent, #000)' }} />

      {/* Content */}
      <div className="section-container" style={{ position: 'relative', zIndex: 10, paddingTop: 90, paddingBottom: 100 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.6fr', gap: 72, alignItems: 'center' }}>

          {/* ── Left ─────────────────────────────────────── */}
          <div>
            {/* Eyebrow */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#4FB7C5', flexShrink: 0, boxShadow: '0 0 8px rgba(79,183,197,0.9)', display: 'inline-block' }} />
              <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 8.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.22em', color: '#4FB7C5' }}>
                CA-Grade Legal &amp; Tax Advisory
              </span>
            </div>

            {/* Headline */}
            <h2 style={{
              fontFamily: "'Playfair Display', Georgia, serif", fontWeight: 400,
              fontSize: 'clamp(28px,3vw,50px)', letterSpacing: '0.01em',
              color: '#E8DDD0', lineHeight: 1.1, margin: '0 0 16px',
            }}>
              Your Client Called.<br />
              <span style={{ color: '#4FB7C5' }}>LETA TEC Has the Answer.</span>
            </h2>

            {/* Body */}
            <p style={{
              fontFamily: "'Inter', sans-serif", fontSize: 15, fontWeight: 300,
              lineHeight: 1.72, color: 'rgba(167,179,194,0.65)',
              margin: '0 0 36px', maxWidth: 340,
            }}>
              SCN on your desk, blocked ITC, tax scrutiny notice, appeal deadline tomorrow — get the reply your senior partner would give, instantly.
            </p>

            {/* CTA */}
            <Link to="/dashboard" style={{ textDecoration: 'none' }}>
              <motion.button
                whileHover={{ background: 'rgba(79,183,197,0.09)', borderColor: 'rgba(79,183,197,0.5)' }}
                whileTap={{ scale: 0.97 }}
                style={{
                  padding: '12px 24px', background: 'transparent',
                  border: '1px solid rgba(79,183,197,0.28)', color: '#4FB7C5',
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: 9, fontWeight: 700,
                  textTransform: 'uppercase', letterSpacing: '0.18em',
                  cursor: 'pointer', transition: 'all 0.25s',
                  display: 'inline-flex', alignItems: 'center', gap: 10,
                }}
              >
                Start Consultation →
              </motion.button>
            </Link>
          </div>

          {/* ── Right: Chat ──────────────────────────────── */}
          <div
            style={{
              background: 'rgba(2,4,8,0.8)', backdropFilter: 'blur(22px)',
              border: '1px solid rgba(255,255,255,0.07)',
              display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative',
            }}
          >
            {/* Cyan top line */}
            <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1,
              background: 'linear-gradient(90deg, #4FB7C5, transparent 65%)', zIndex: 2 }} />

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '11px 16px', borderBottom: '1px solid rgba(255,255,255,0.045)', flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#4FB7C5', boxShadow: '0 0 5px rgba(79,183,197,0.7)' }} />
                <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 8, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'rgba(79,183,197,0.8)' }}>
                  LETA TEC · Legal &amp; Tax Advisory
                </span>
              </div>
              <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 7, color: 'rgba(255,255,255,0.1)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Live</span>
            </div>

            {/* Messages */}
            <div ref={scrollRef} style={{ overflowY: 'auto', padding: '18px 16px', display: 'flex', flexDirection: 'column', gap: 16, minHeight: 300, maxHeight: 380 }}>
              <AnimatePresence>
                {visible.map((msg, i) => (
                  <motion.div key={i}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25 }}
                  >
                    <Message msg={msg} />
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>

            {/* Input */}
            <div style={{ padding: '9px 14px 12px', borderTop: '1px solid rgba(255,255,255,0.04)', flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', border: '1px solid rgba(255,255,255,0.05)', background: 'rgba(255,255,255,0.01)' }}>
                <span style={{ flex: 1, fontSize: 11.5, fontFamily: "'Inter', sans-serif", color: 'rgba(255,255,255,0.11)' }}>
                  Ask LETA TEC a legal or tax question…
                </span>
                <motion.div animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.6, repeat: Infinity }}
                  style={{ width: 4, height: 4, borderRadius: '50%', background: '#4FB7C5' }} />
                <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 7, color: 'rgba(79,183,197,0.5)', letterSpacing: '0.12em' }}>AI READY</span>
              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
};

export default CABotDemo;
