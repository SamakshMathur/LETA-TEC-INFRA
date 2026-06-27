import { useEffect, useRef, useState } from 'react';

// All coordinates in a 320 × 720 viewBox
const VW = 320;
const VH = 720;
const C  = '#4FB7C5';

// 5 nodes — gentle S-wave, top → bottom
const NODES = [
  { x: 160, y:  60 },
  { x:  92, y: 192 },
  { x: 160, y: 360 },
  { x: 228, y: 528 },
  { x: 160, y: 660 },
];

// 4 segments connecting consecutive nodes (cubic bezier)
const SEGS = [
  'M 160 60  C 160 120  92 120   92 192',
  'M  92 192 C  92 264 160 296  160 360',
  'M 160 360 C 160 424 228 460  228 528',
  'M 228 528 C 228 592 160 628  160 660',
];

// full joined spine (for animateMotion reference)
const SPINE = 'M 160 60 C 160 120 92 120 92 192 C 92 264 160 296 160 360 C 160 424 228 460 228 528 C 228 592 160 628 160 660';

// floating orbs behind the pipeline
const ORBS = [
  { cx: '20%', cy: '12%', r: 120, op: 0.055, dur: 8  },
  { cx: '80%', cy: '45%', r: 100, op: 0.04,  dur: 11 },
  { cx: '15%', cy: '78%', r: 130, op: 0.06,  dur: 9  },
  { cx: '75%', cy: '80%', r:  90, op: 0.035, dur: 7  },
];

const FLIES = [
  { x: '10%', y: '8%',  d: 9,  dl: 0    },
  { x: '85%', y: '22%', d: 11, dl: 1.4  },
  { x: '25%', y: '55%', d: 8,  dl: 0.7  },
  { x: '78%', y: '68%', d: 12, dl: 2.2  },
  { x: '5%',  y: '70%', d: 10, dl: 1.9  },
  { x: '92%', y: '85%', d: 9,  dl: 0.5  },
  { x: '50%', y: '15%', d: 13, dl: 1.1  },
  { x: '40%', y: '90%', d: 8,  dl: 3.0  },
  { x: '65%', y: '40%', d: 10, dl: 0.3  },
];

const CSS = `
  @keyframes orb-breathe {
    0%   { transform: scale(1);    opacity:1; }
    50%  { transform: scale(1.2);  opacity:.65; }
    100% { transform: scale(1);    opacity:1; }
  }
  @keyframes fly-drift {
    0%   { transform:translate(0,0);    opacity:.07; }
    25%  { transform:translate(8px,-12px); opacity:.55; }
    60%  { transform:translate(15px,5px);  opacity:.22; }
    80%  { transform:translate(4px,14px);  opacity:.50; }
    100% { transform:translate(0,0);    opacity:.07; }
  }
`;

function Packet({ dur, begin }) {
  return (
    <g>
      {/* leading glow */}
      <circle r={6} fill={C} opacity={0}>
        <animateMotion dur={`${dur}s`} begin={`${begin}s`} repeatCount="indefinite">
          <mpath href="#sp" />
        </animateMotion>
        <animate attributeName="opacity"
          values="0;0.18;0.18;0" keyTimes="0;0.06;0.94;1"
          dur={`${dur}s`} begin={`${begin}s`} repeatCount="indefinite" />
      </circle>
      {/* bright core dot */}
      <circle r={2.5} fill="#e8f8fb" opacity={0}>
        <animateMotion dur={`${dur}s`} begin={`${begin}s`} repeatCount="indefinite">
          <mpath href="#sp" />
        </animateMotion>
        <animate attributeName="opacity"
          values="0;1;1;0" keyTimes="0;0.06;0.94;1"
          dur={`${dur}s`} begin={`${begin}s`} repeatCount="indefinite" />
      </circle>
    </g>
  );
}

const PillarThreeScene = ({ activeStep }) => {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      <style>{CSS}</style>

      {/* ── Aurora orbs ──────────────────────────────────────── */}
      {ORBS.map((o, i) => (
        <div key={i} style={{
          position: 'absolute', top: o.cy, left: o.cx,
          width: o.r * 2, height: o.r * 2,
          transform: 'translate(-50%,-50%)',
          borderRadius: '50%',
          background: `radial-gradient(circle, rgba(79,183,197,${o.op}) 0%, transparent 70%)`,
          filter: `blur(${o.r * 0.6}px)`,
          animation: `orb-breathe ${o.dur}s ease-in-out ${i * 1.5}s infinite alternate`,
          pointerEvents: 'none',
        }} />
      ))}

      {/* ── Fireflies ─────────────────────────────────────────── */}
      {FLIES.map((f, i) => (
        <div key={i} style={{
          position: 'absolute', top: f.y, left: f.x,
          width: 3, height: 3, borderRadius: '50%',
          background: C,
          boxShadow: `0 0 7px 2px rgba(79,183,197,0.65)`,
          animation: `fly-drift ${f.d}s ease-in-out ${f.dl}s infinite`,
          pointerEvents: 'none',
        }} />
      ))}

      {/* ── SVG pipeline — fills full container ──────────────── */}
      <svg
        viewBox={`0 0 ${VW} ${VH}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* hidden spine for animateMotion target */}
        <path id="sp" d={SPINE} fill="none" stroke="none" />

        {/* ── Segment lines ─────────────────────────────────── */}
        {SEGS.map((d, i) => {
          const passed = i < activeStep;
          const active = i === activeStep - 1 || (i === 0 && activeStep === 0);
          const future = i >= activeStep;
          return (
            <g key={i}>
              {/* bloom */}
              <path d={d} fill="none"
                stroke={C} strokeWidth={16}
                opacity={passed ? 0.07 : 0.02}
                strokeLinecap="round"
                style={{ filter: 'blur(8px)', transition: 'opacity 0.8s ease' }}
              />
              {/* crisp */}
              <path d={d} fill="none"
                stroke={C} strokeWidth={1.5}
                opacity={passed ? 0.65 : future ? 0.10 : 0.25}
                strokeLinecap="round"
                style={{ transition: 'opacity 0.8s ease' }}
              />
            </g>
          );
        })}

        {/* ── Flowing data packets ──────────────────────────── */}
        <Packet dur={3.6} begin={0}    />
        <Packet dur={4.2} begin={-1.0} />
        <Packet dur={3.9} begin={-2.2} />
        <Packet dur={4.6} begin={-3.4} />

        {/* ── Pipeline nodes — ALL always visible ──────────── */}
        {NODES.map((n, i) => {
          const passed = i < activeStep;
          const active = i === activeStep;
          const future = i > activeStep;

          return (
            <g key={i}>
              {/* outer bloom — only past/active */}
              {!future && (
                <circle cx={n.x} cy={n.y}
                  r={active ? 42 : 24}
                  fill={C}
                  opacity={active ? 0.05 : 0.025}
                  style={{ transition: 'all 0.8s ease', filter: 'blur(12px)' }}
                >
                  {active && (
                    <animate attributeName="r" values="42;54;42" dur="3.5s" repeatCount="indefinite" />
                  )}
                </circle>
              )}

              {/* mid glow */}
              <circle cx={n.x} cy={n.y}
                r={active ? 20 : passed ? 12 : 8}
                fill={C}
                opacity={active ? 0.12 : passed ? 0.06 : 0.02}
                style={{ transition: 'all 0.8s ease' }}
              />

              {/* inner disc */}
              <circle cx={n.x} cy={n.y}
                r={active ? 10 : passed ? 6 : 5}
                fill={C}
                opacity={active ? 0.28 : passed ? 0.12 : 0.04}
                style={{ transition: 'all 0.8s ease' }}
              />

              {/* ring stroke */}
              <circle cx={n.x} cy={n.y}
                r={active ? 8 : passed ? 5.5 : 4.5}
                fill="none"
                stroke={C}
                strokeWidth={active ? 1.5 : 1}
                opacity={active ? 0.90 : passed ? 0.50 : 0.15}
                style={{ transition: 'all 0.8s ease' }}
              />

              {/* core dot */}
              <circle cx={n.x} cy={n.y}
                r={active ? 3.5 : passed ? 2.2 : 1.8}
                fill={active ? '#dff6fa' : C}
                opacity={active ? 1 : passed ? 0.7 : 0.2}
                style={{ transition: 'all 0.8s ease' }}
              />

              {/* sonar rings — active only */}
              {active && (
                <>
                  <circle cx={n.x} cy={n.y} r={10} fill="none" stroke={C} strokeWidth={1} opacity={0}>
                    <animate attributeName="r"       values="10;46" dur="2.6s"        repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.65;0" dur="2.6s"        repeatCount="indefinite" />
                  </circle>
                  <circle cx={n.x} cy={n.y} r={10} fill="none" stroke={C} strokeWidth={0.5} opacity={0}>
                    <animate attributeName="r"       values="10;46" dur="2.6s" begin="1.3s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.35;0" dur="2.6s" begin="1.3s" repeatCount="indefinite" />
                  </circle>
                </>
              )}

              {/* step number badge */}
              <text
                x={n.x + (i % 2 === 0 ? 18 : -18)}
                y={n.y + 4}
                textAnchor={i % 2 === 0 ? 'start' : 'end'}
                fontFamily="'IBM Plex Mono', monospace"
                fontSize={9}
                fontWeight={600}
                fill={C}
                opacity={active ? 0.75 : passed ? 0.35 : 0.12}
                style={{ transition: 'opacity 0.8s ease' }}
              >
                0{i + 1}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export default PillarThreeScene;
