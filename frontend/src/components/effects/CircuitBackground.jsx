import React, { useRef, useEffect } from 'react';

const CELL     = 80;      // grid cell size px
const LINE_CLR = 'rgba(24,180,210,0.13)';
const NODE_CLR = 'rgba(24,180,210,0.55)';
const SIG_CLR  = '#18b4d2';
const SIG_GLOW = 'rgba(24,180,210,0.6)';
const NODE_R   = 2.2;
const SIG_R    = 3.5;
const SIG_SPEED_MIN = 1.2;
const SIG_SPEED_MAX = 2.8;
const MAX_SIGNALS   = 28;

// Build a random circuit graph on the grid
function buildGraph(cols, rows) {
  // Every cell intersection is a potential node
  const nodes = [];
  const edges = [];

  for (let r = 0; r <= rows; r++) {
    for (let c = 0; c <= cols; c++) {
      nodes.push({ x: c * CELL, y: r * CELL });
    }
  }

  const idx = (c, r) => r * (cols + 1) + c;

  // Horizontal edges — skip some for a "broken" circuit look
  for (let r = 0; r <= rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (Math.random() > 0.28) {
        edges.push([idx(c, r), idx(c + 1, r)]);
      }
    }
  }

  // Vertical edges
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c <= cols; c++) {
      if (Math.random() > 0.28) {
        edges.push([idx(c, r), idx(c, r + 1)]);
      }
    }
  }

  // Adjacency map for signal routing
  const adj = Array.from({ length: nodes.length }, () => []);
  for (const [a, b] of edges) {
    adj[a].push(b);
    adj[b].push(a);
  }

  return { nodes, edges, adj };
}

function createSignal(nodes, adj) {
  // Pick a random starting node that has neighbours
  const starts = nodes.map((_, i) => i).filter(i => adj[i].length > 0);
  const from = starts[Math.floor(Math.random() * starts.length)];
  const neighbours = adj[from];
  const to = neighbours[Math.floor(Math.random() * neighbours.length)];
  const speed = SIG_SPEED_MIN + Math.random() * (SIG_SPEED_MAX - SIG_SPEED_MIN);
  return { from, to, progress: 0, speed };
}

const CircuitBackground = ({ className = '' }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let animId;
    let graph = null;
    let signals = [];
    let W = 0, H = 0;

    const resize = () => {
      W = canvas.width  = canvas.offsetWidth;
      H = canvas.height = canvas.offsetHeight;
      const cols = Math.ceil(W / CELL) + 1;
      const rows = Math.ceil(H / CELL) + 1;
      graph = buildGraph(cols, rows);
      signals = [];
      for (let i = 0; i < MAX_SIGNALS; i++) {
        const s = createSignal(graph.nodes, graph.adj);
        s.progress = Math.random(); // stagger start
        signals.push(s);
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, W, H);

      const { nodes, edges, adj } = graph;

      // Draw static circuit traces
      ctx.strokeStyle = LINE_CLR;
      ctx.lineWidth = 0.8;
      for (const [a, b] of edges) {
        ctx.beginPath();
        ctx.moveTo(nodes[a].x, nodes[a].y);
        ctx.lineTo(nodes[b].x, nodes[b].y);
        ctx.stroke();
      }

      // Draw nodes (intersection dots)
      for (let i = 0; i < nodes.length; i++) {
        if (adj[i].length < 2) continue; // only show real junctions
        const { x, y } = nodes[i];
        ctx.beginPath();
        ctx.arc(x, y, NODE_R, 0, Math.PI * 2);
        ctx.fillStyle = NODE_CLR;
        ctx.fill();
      }

      // Draw & advance signals
      for (let i = 0; i < signals.length; i++) {
        const sig = signals[i];
        const a = nodes[sig.from];
        const b = nodes[sig.to];
        const x = a.x + (b.x - a.x) * sig.progress;
        const y = a.y + (b.y - a.y) * sig.progress;

        // Glow
        const grd = ctx.createRadialGradient(x, y, 0, x, y, 14);
        grd.addColorStop(0, SIG_GLOW);
        grd.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.arc(x, y, 14, 0, Math.PI * 2);
        ctx.fillStyle = grd;
        ctx.fill();

        // Core dot
        ctx.beginPath();
        ctx.arc(x, y, SIG_R, 0, Math.PI * 2);
        ctx.fillStyle = SIG_CLR;
        ctx.fill();

        // Advance
        sig.progress += sig.speed / (CELL * 0.9);
        if (sig.progress >= 1) {
          // Arrived — pick next hop or restart
          const nexts = adj[sig.to];
          if (nexts.length > 0) {
            const nextIdx = nexts[Math.floor(Math.random() * nexts.length)];
            sig.from = sig.to;
            sig.to   = nextIdx;
          } else {
            Object.assign(sig, createSignal(nodes, adj));
          }
          sig.progress = 0;
        }
      }

      animId = requestAnimationFrame(draw);
    };

    resize();
    draw();

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className={`pointer-events-none absolute inset-0 w-full h-full ${className}`}
      style={{ display: 'block' }}
    />
  );
};

export default CircuitBackground;
