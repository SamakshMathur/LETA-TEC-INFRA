import React, { useRef, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

const NODE_COUNT   = 75;
const CONNECT_DIST = 3.6;
const MAX_LINES    = 400;
const ACCENT       = '#4FB7C5';

// ─── Inner scene — imperative for zero GC pressure ───────────────────────────
function KnowledgeGraph() {
  const { scene, camera } = useThree();
  const mouse = useRef({ x: 0, y: 0 });

  type State = {
    pos:        Float32Array;
    vel:        Float32Array;
    lineBuf:    Float32Array;
    opacityBuf: Float32Array;
    points:     THREE.Points;
    lines:      THREE.LineSegments;
  };
  const s = useRef<State | null>(null);

  useEffect(() => {
    const pos = new Float32Array(NODE_COUNT * 3);
    const vel = new Float32Array(NODE_COUNT * 3);

    for (let i = 0; i < NODE_COUNT; i++) {
      pos[i*3]   = (Math.random() - 0.5) * 30;
      pos[i*3+1] = (Math.random() - 0.5) * 18;
      pos[i*3+2] = (Math.random() - 0.5) * 10;
      vel[i*3]   = (Math.random() - 0.5) * 0.0055;
      vel[i*3+1] = (Math.random() - 0.5) * 0.0045;
      vel[i*3+2] = (Math.random() - 0.5) * 0.0025;
    }

    const lineBuf    = new Float32Array(MAX_LINES * 6);
    const opacityBuf = new Float32Array(MAX_LINES * 2);

    // ── Points ──────────────────────────────────────────────────────────────
    const ptGeo = new THREE.BufferGeometry();
    ptGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const ptMat = new THREE.PointsMaterial({
      color: new THREE.Color(ACCENT),
      size: 0.07,
      transparent: true,
      opacity: 0.6,
      sizeAttenuation: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const points = new THREE.Points(ptGeo, ptMat);

    // ── Lines — custom shader for per-segment distance fade ──────────────────
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute('position', new THREE.BufferAttribute(lineBuf, 3));
    lineGeo.setAttribute('aOpacity', new THREE.BufferAttribute(opacityBuf, 1));
    lineGeo.setDrawRange(0, 0);

    const lineMat = new THREE.ShaderMaterial({
      uniforms: { uColor: { value: new THREE.Color(ACCENT) } },
      vertexShader: `
        attribute float aOpacity;
        varying  float vOpacity;
        void main() {
          vOpacity = aOpacity;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec3  uColor;
        varying float vOpacity;
        void main() {
          gl_FragColor = vec4(uColor, vOpacity);
        }
      `,
      transparent: true,
      depthWrite:  false,
      blending:    THREE.AdditiveBlending,
    });
    const lines = new THREE.LineSegments(lineGeo, lineMat);

    scene.add(points, lines);
    s.current = { pos, vel, lineBuf, opacityBuf, points, lines };

    const onMouse = (e: MouseEvent) => {
      mouse.current.x =  (e.clientX / window.innerWidth  - 0.5) * 2;
      mouse.current.y = -(e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener('mousemove', onMouse);

    return () => {
      scene.remove(points, lines);
      ptGeo.dispose();   ptMat.dispose();
      lineGeo.dispose(); lineMat.dispose();
      window.removeEventListener('mousemove', onMouse);
    };
  }, [scene]);

  useFrame(({ clock }) => {
    if (!s.current) return;
    const { pos, vel, lineBuf, opacityBuf, points, lines } = s.current;
    const t = clock.getElapsedTime();

    // ── Drift particles ────────────────────────────────────────────────────
    for (let i = 0; i < NODE_COUNT; i++) {
      pos[i*3]   += vel[i*3];
      pos[i*3+1] += vel[i*3+1];
      pos[i*3+2] += vel[i*3+2];
      if (Math.abs(pos[i*3])   > 15) vel[i*3]   *= -1;
      if (Math.abs(pos[i*3+1]) > 9)  vel[i*3+1] *= -1;
      if (Math.abs(pos[i*3+2]) > 5)  vel[i*3+2] *= -1;
    }
    points.geometry.attributes.position.needsUpdate = true;

    // ── Rebuild connection lines ───────────────────────────────────────────
    let n = 0;
    const cd  = CONNECT_DIST;
    const cd2 = cd * cd;

    for (let i = 0; i < NODE_COUNT && n < MAX_LINES; i++) {
      for (let j = i + 1; j < NODE_COUNT && n < MAX_LINES; j++) {
        const dx = pos[i*3]   - pos[j*3];
        const dy = pos[i*3+1] - pos[j*3+1];
        const dz = pos[i*3+2] - pos[j*3+2];
        const d2 = dx*dx + dy*dy + dz*dz;
        if (d2 < cd2) {
          const b  = n * 6;
          lineBuf[b]   = pos[i*3];   lineBuf[b+1] = pos[i*3+1]; lineBuf[b+2] = pos[i*3+2];
          lineBuf[b+3] = pos[j*3];   lineBuf[b+4] = pos[j*3+1]; lineBuf[b+5] = pos[j*3+2];
          // Fade: full near, zero at threshold
          const op = (1 - Math.sqrt(d2) / cd) * 0.22;
          opacityBuf[n*2]     = op;
          opacityBuf[n*2 + 1] = op;
          n++;
        }
      }
    }
    lines.geometry.setDrawRange(0, n * 2);
    lines.geometry.attributes.position.needsUpdate = true;
    lines.geometry.attributes.aOpacity.needsUpdate  = true;

    // ── Camera: slow drift orbit + mouse parallax ─────────────────────────
    const angle = t * 0.018;
    const tx = Math.sin(angle) * 2.0 + mouse.current.x * 1.6;
    const ty = Math.cos(angle * 0.6) * 1.1 + mouse.current.y * 1.0;
    camera.position.x += (tx - camera.position.x) * 0.022;
    camera.position.y += (ty - camera.position.y) * 0.022;
    camera.lookAt(0, 0, 0);
  });

  return null;
}

// ─── Export ───────────────────────────────────────────────────────────────────
const DashboardParticles: React.FC = () => (
  <div className="fixed inset-0 pointer-events-none" style={{ zIndex: 0 }}>
    <Canvas
      dpr={typeof window !== 'undefined' ? Math.min(window.devicePixelRatio, 1.5) : 1}
      camera={{ position: [0, 0, 12], fov: 55 }}
      gl={{ alpha: true, antialias: false, powerPreference: 'high-performance' }}
      style={{ background: 'transparent' }}
    >
      <KnowledgeGraph />
    </Canvas>
  </div>
);

export default DashboardParticles;
