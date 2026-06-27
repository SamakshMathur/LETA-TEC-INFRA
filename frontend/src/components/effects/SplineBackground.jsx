import { Suspense, lazy } from 'react';

const Spline = lazy(() => import('@splinetool/react-spline'));

/**
 * Drop your Spline scene URL below.
 * How to get it:
 *   1. Open your scene in spline.design
 *   2. Click Export → Web (Public URL)  or  Publish → Get Link
 *   3. Copy the URL ending in .splinecode
 *   4. Paste it as the value of SPLINE_URL below
 */
const SPLINE_URL = 'YOUR_SPLINE_SCENE_URL_HERE';

const isConfigured = SPLINE_URL !== 'YOUR_SPLINE_SCENE_URL_HERE';

export default function SplineBackground({ onLoad }) {
  if (!isConfigured) {
    /* ── Placeholder shown until a real URL is pasted in ── */
    return (
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          zIndex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          pointerEvents: 'none',
          gap: '12px',
        }}
      >
        {/* Pulsing placeholder orb */}
        <div style={{
          width: '320px',
          height: '320px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(79,183,197,0.12) 0%, transparent 70%)',
          animation: 'splinePulse 3s ease-in-out infinite',
        }} />
        <p style={{
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: '10px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.18em',
          color: 'rgba(79,183,197,0.5)',
          marginTop: '-160px',
        }}>
          Paste your Spline URL in SplineBackground.jsx
        </p>
        <style>{`
          @keyframes splinePulse {
            0%, 100% { opacity: 0.5; transform: scale(1); }
            50%       { opacity: 1;   transform: scale(1.08); }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 1,
        pointerEvents: 'none',
        overflow: 'hidden',
      }}
    >
      <Suspense fallback={<SplineFallback />}>
        <Spline
          scene={SPLINE_URL}
          onLoad={onLoad}
          style={{
            width: '100%',
            height: '100%',
            position: 'absolute',
            inset: 0,
          }}
        />
      </Suspense>
    </div>
  );
}

function SplineFallback() {
  return (
    <div style={{
      position: 'absolute',
      inset: 0,
      background: 'radial-gradient(ellipse 60% 50% at 50% 40%, rgba(79,183,197,0.08) 0%, transparent 70%)',
      animation: 'splinePulse 2s ease-in-out infinite',
    }} />
  );
}
