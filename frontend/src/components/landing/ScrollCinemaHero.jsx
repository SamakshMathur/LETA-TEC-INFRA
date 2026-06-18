import React, { useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import HeroThreeScene from './HeroThreeScene';

const SCROLL_HEIGHT_VH = 100;

const ScrollCinemaHero = () => {
  const containerRef = useRef(null);
  const textRef      = useRef(null);
  const scrollCueRef = useRef(null);
  const rafRef       = useRef(null);

  // Fade text + scroll cue out as user scrolls into the pinned section
  useEffect(() => {
    const tick = () => {
      const container = containerRef.current;
      if (!container) return;
      const rect    = container.getBoundingClientRect();
      const totalH  = container.offsetHeight - window.innerHeight;
      const p       = totalH > 0 ? Math.min(1, Math.max(0, -rect.top) / totalH) : 0;

      const text = textRef.current;
      if (text) {
        const raw = p < 0.55 ? 1 : p > 0.82 ? 0 : 1 - (p - 0.55) / 0.27;
        text.style.opacity   = Math.max(0, raw).toFixed(3);
        text.style.transform = `translateY(${Math.max(0, (p - 0.55) / 0.27) * -32}px)`;
      }

      const cue = scrollCueRef.current;
      if (cue) {
        const c = p < 0.12 ? 1 : p > 0.35 ? 0 : 1 - (p - 0.12) / 0.23;
        cue.style.opacity = Math.max(0, c).toFixed(3);
      }
    };

    const onScroll = () => { cancelAnimationFrame(rafRef.current); rafRef.current = requestAnimationFrame(tick); };
    window.addEventListener('scroll', onScroll, { passive: true });
    tick();
    return () => { window.removeEventListener('scroll', onScroll); cancelAnimationFrame(rafRef.current); };
  }, []);

  return (
    <div ref={containerRef} style={{ height: `${SCROLL_HEIGHT_VH}vh`, position: 'relative' }}>
      <div style={{ position: 'sticky', top: 0, height: '100vh', overflow: 'hidden', background: '#000' }}>

        {/* 3D scene — right half only, so text never overlaps */}
        <div style={{ position: 'absolute', left: '40%', right: 0, top: 0, bottom: 0, zIndex: 1 }}>
          <HeroThreeScene />
        </div>

        {/* Top-edge vignette so the scene blends cleanly into nav */}
        <div aria-hidden style={{
          position: 'absolute', inset: 0, zIndex: 2, pointerEvents: 'none',
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, transparent 22%, transparent 72%, rgba(0,0,0,0.72) 100%)',
        }} />

        {/* Text overlay */}
        <div
          ref={textRef}
          style={{
            position: 'absolute', inset: 0, zIndex: 10,
            display: 'flex', flexDirection: 'column', justifyContent: 'center',
            padding: 'clamp(40px, 6vw, 96px)',
            maxWidth: '50%',
            opacity: 1, willChange: 'opacity, transform',
          }}
        >
          <h1 className="cinema-h1">
            <span className="cinema-line-wrap">
              <span className="cinema-line" style={{ animationDelay: '0.10s' }}>Intelligence</span>
            </span>
            <span className="cinema-line-wrap">
              <span className="cinema-line" style={{ animationDelay: '0.26s' }}>for High-Stakes</span>
            </span>
            <span className="cinema-line-wrap">
              <span className="cinema-line cinema-line--accent" style={{ animationDelay: '0.44s' }}>Tax.</span>
            </span>
          </h1>

          <p className="cinema-body">
            Autonomous GST reconciliation and compliance engine built for
            precision-engineered financial command.
          </p>

          <Link to="/gst" className="cinema-cta">
            <span>Enter Command Center</span>
            <ArrowRight size={15} />
          </Link>
        </div>

        {/* Scroll cue */}
        <div ref={scrollCueRef} className="cinema-scroll-cue">
          <p className="cinema-scroll-label">Scroll</p>
          <div className="cinema-scroll-track">
            <span className="cinema-scroll-dot" />
          </div>
        </div>

      </div>

      <style>{`
        @keyframes cinema-revealUp {
          from { transform: translateY(110%); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
        @keyframes cinema-fadeUp {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0);    }
        }
        @keyframes cinema-pulseDot {
          0%,100% { opacity:1; transform:scale(1);   }
          50%     { opacity:.4; transform:scale(0.8); }
        }
        @keyframes cinema-scrollDrop {
          0%   { top:-8px; opacity:0; }
          20%  { opacity:1; }
          100% { top:100%; opacity:0; }
        }

        .cinema-eyebrow {
          font-family: 'IBM Plex Mono', monospace;
          font-size: 10px; font-weight: 600;
          text-transform: uppercase; letter-spacing: 0.22em;
          color: #4FB7C5;
          display: flex; align-items: center; gap: 10px;
          margin: 0 0 28px 0; padding: 0;
          animation: cinema-fadeUp 0.6s ease 0.05s both;
        }
        .cinema-pulse-dot {
          width:6px; height:6px; border-radius:50%; flex-shrink:0;
          background:#4FB7C5; display:inline-block;
          box-shadow: 0 0 10px rgba(79,183,197,0.8);
          animation: cinema-pulseDot 2s ease-in-out infinite;
        }

        .cinema-h1 { margin: 0 0 24px 0; padding: 0; font-size: 0; display: block; }

        .cinema-line-wrap {
          display: block; overflow: hidden; line-height: 1.10;
        }
        .cinema-line {
          display: block;
          font-family: 'Inter', sans-serif;
          font-weight: 700;
          font-size: clamp(32px, 4.8vw, 72px);
          letter-spacing: -0.025em;
          line-height: 1.10;
          color: #ffffff;
          padding-bottom: 0.04em;
          animation: cinema-revealUp 0.80s cubic-bezier(0.16,1,0.3,1) both;
        }
        .cinema-line--accent {
          background: linear-gradient(135deg, #ffffff 0%, #4FB7C5 40%, #67E8F9 70%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .cinema-body {
          font-family: 'Inter', sans-serif;
          font-size: clamp(13px, 1.1vw, 16px);
          font-weight: 300; line-height: 1.70;
          color: rgba(167,179,194,0.85);
          max-width: 420px;
          margin: 0 0 36px 0; padding: 0;
          animation: cinema-fadeUp 0.8s ease 0.70s both;
        }

        .cinema-cta {
          display: inline-flex; align-items: center; gap: 12px;
          align-self: flex-start; width: fit-content;
          padding: 14px 26px;
          background: linear-gradient(135deg, #4FB7C5 0%, #67E8F9 100%);
          color: #000; font-family: 'Inter Tight', sans-serif;
          font-weight: 700; font-size: 11px;
          letter-spacing: 0.14em; text-transform: uppercase;
          text-decoration: none;
          animation: cinema-fadeUp 0.7s ease 0.88s both;
          transition: box-shadow 0.3s ease, transform 0.2s ease;
        }
        .cinema-cta:hover {
          box-shadow: 0 0 40px rgba(79,183,197,0.5);
          transform: translateY(-2px);
        }

        .cinema-scroll-cue {
          position: absolute; bottom: 28px; left: 50%;
          transform: translateX(-50%);
          display: flex; flex-direction: column; align-items: center; gap: 6px;
          z-index: 10; opacity: 1; will-change: opacity;
        }
        .cinema-scroll-label {
          font-family: 'IBM Plex Mono'; font-size: 8px;
          letter-spacing: 0.22em; text-transform: uppercase;
          color: rgba(79,183,197,0.45); margin: 0;
        }
        .cinema-scroll-track {
          width:1px; height:44px;
          background: rgba(255,255,255,0.07);
          position:relative; overflow:hidden; border-radius:999px;
        }
        .cinema-scroll-dot {
          position:absolute; top:-8px; left:0;
          width:1px; height:8px;
          background: linear-gradient(to bottom, transparent, rgba(79,183,197,0.8));
          border-radius:999px;
          animation: cinema-scrollDrop 1.8s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
};

export default ScrollCinemaHero;
