import { useEffect, useRef } from 'react';

export default function HeroMeshBackground() {
  const spotRef = useRef(null);

  useEffect(() => {
    let rafId;
    let targetX = 50, targetY = 40;
    let currentX = 50, currentY = 40;

    const onMove = (e) => {
      targetX = (e.clientX / window.innerWidth) * 100;
      targetY = (e.clientY / window.innerHeight) * 100;
    };

    const tick = () => {
      currentX += (targetX - currentX) * 0.06;
      currentY += (targetY - currentY) * 0.06;
      if (spotRef.current) {
        spotRef.current.style.background =
          `radial-gradient(ellipse 700px 500px at ${currentX}% ${currentY}%, rgba(79,183,197,0.07) 0%, rgba(14,116,144,0.03) 40%, transparent 70%)`;
      }
      rafId = requestAnimationFrame(tick);
    };

    window.addEventListener('mousemove', onMove, { passive: true });
    rafId = requestAnimationFrame(tick);
    return () => {
      window.removeEventListener('mousemove', onMove);
      cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'absolute',
        inset: 0,
        overflow: 'hidden',
        zIndex: 1,
        pointerEvents: 'none',
      }}
    >
      {/* Orb 1 — top-left teal */}
      <div style={{
        position: 'absolute',
        width: '900px', height: '900px',
        top: '-200px', left: '-200px',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,180,200,0.14) 0%, rgba(0,100,130,0.06) 45%, transparent 70%)',
        filter: 'blur(80px)',
        animation: 'meshDrift1 28s ease-in-out infinite alternate',
        willChange: 'transform',
      }} />

      {/* Orb 2 — top-right cyan */}
      <div style={{
        position: 'absolute',
        width: '700px', height: '700px',
        top: '-150px', right: '-120px',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(0,160,190,0.12) 0%, rgba(0,80,110,0.05) 45%, transparent 70%)',
        filter: 'blur(100px)',
        animation: 'meshDrift2 36s ease-in-out infinite alternate',
        willChange: 'transform',
      }} />

      {/* Orb 3 — centre depth (very subtle warm teal) */}
      <div style={{
        position: 'absolute',
        width: '1000px', height: '600px',
        top: '20%', left: '50%',
        transform: 'translateX(-50%)',
        borderRadius: '50%',
        background: 'radial-gradient(ellipse, rgba(79,183,197,0.06) 0%, transparent 65%)',
        filter: 'blur(120px)',
        animation: 'meshPulse 12s ease-in-out infinite',
      }} />

      {/* Orb 4 — bottom-left subtle blue */}
      <div style={{
        position: 'absolute',
        width: '600px', height: '600px',
        bottom: '-100px', left: '10%',
        borderRadius: '50%',
        background: 'radial-gradient(circle, rgba(30,100,150,0.1) 0%, transparent 65%)',
        filter: 'blur(90px)',
        animation: 'meshDrift3 22s ease-in-out infinite alternate',
      }} />

      {/* Mouse spotlight */}
      <div
        ref={spotRef}
        style={{
          position: 'absolute',
          inset: 0,
          transition: 'background 0.05s linear',
          mixBlendMode: 'screen',
        }}
      />

      {/* Subtle scanline texture */}
      <div style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(255,255,255,0.008) 3px, rgba(255,255,255,0.008) 4px)',
        pointerEvents: 'none',
      }} />

      <style>{`
        @keyframes meshDrift1 {
          from { transform: translate(0px, 0px) scale(1); }
          to   { transform: translate(70px, 50px) scale(1.08); }
        }
        @keyframes meshDrift2 {
          from { transform: translate(0px, 0px) scale(1); }
          to   { transform: translate(-60px, 40px) scale(1.12); }
        }
        @keyframes meshDrift3 {
          from { transform: translate(0px, 0px) scale(1); }
          to   { transform: translate(40px, -30px) scale(1.06); }
        }
        @keyframes meshPulse {
          0%, 100% { opacity: 0.6; transform: translateX(-50%) scale(1); }
          50%       { opacity: 1;   transform: translateX(-50%) scale(1.05); }
        }
      `}</style>
    </div>
  );
}
