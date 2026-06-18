import { useEffect, useRef } from 'react';
import * as THREE from 'three';

const LEGAL_NODES = [
  'GSTR-1','ITC','SCN','§16','CGST','IGST','DRC','18%','ARN','GSTR-9',
  'LUT','ASMT','GSTR-3B','RCM','E-WAY','IGST §13','CBIC','AAR','Sec 16(4)',
  'GSTR-9C','ISD','RCMC','CENVAT','HSN','SAC',
];

function makeNodeTex(text) {
  const cv = document.createElement('canvas');
  cv.width = 192; cv.height = 72;
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, 192, 72);
  ctx.font = `700 ${text.length > 6 ? 13 : text.length > 3 ? 16 : 20}px 'IBM Plex Mono', monospace`;
  ctx.fillStyle = 'rgba(79,183,197,0.65)';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(text, 96, 36);
  return new THREE.CanvasTexture(cv);
}

function makeGlow() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = 128;
  const ctx = cv.getContext('2d');
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0,    'rgba(79,183,197,1)');
  g.addColorStop(0.28, 'rgba(79,183,197,0.55)');
  g.addColorStop(0.6,  'rgba(79,183,197,0.12)');
  g.addColorStop(1,    'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(cv);
}

const CABotThreeScene = ({ overlay = true }) => {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const W = mount.clientWidth  || 1000;
    const H = mount.clientHeight || 560;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    if (overlay) renderer.domElement.style.mixBlendMode = 'screen';
    mount.appendChild(renderer.domElement);

    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 200);
    camera.position.set(0, 0, 14);
    camera.lookAt(0, 0, 0);

    const glowTex = makeGlow();

    // Build nodes scattered in a wide plane
    const nodeData = [];
    const spread = { x: 11, y: 5.5 };
    for (let i = 0; i < LEGAL_NODES.length; i++) {
      const x = (Math.random() - 0.5) * spread.x * 2;
      const y = (Math.random() - 0.5) * spread.y * 2;
      const z = (Math.random() - 0.5) * 2.5;

      const group = new THREE.Group();
      group.position.set(x, y, z);

      // Dot
      const dotGeo = new THREE.IcosahedronGeometry(0.08 + Math.random() * 0.06, 0);
      const dot = new THREE.Mesh(dotGeo,
        new THREE.MeshBasicMaterial({ color: 0x4FB7C5, transparent: true, opacity: 0.7 + Math.random() * 0.3 })
      );
      group.add(dot);

      // Glow halo
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({
        map: glowTex, transparent: true,
        opacity: 0.12 + Math.random() * 0.18,
        blending: THREE.AdditiveBlending, depthWrite: false,
      }));
      const hs = 0.6 + Math.random() * 0.8;
      halo.scale.set(hs, hs, 1);
      group.add(halo);

      // Label sprite
      const label = new THREE.Sprite(new THREE.SpriteMaterial({
        map: makeNodeTex(LEGAL_NODES[i]),
        transparent: true, opacity: 0.28 + Math.random() * 0.22,
        depthWrite: false,
      }));
      label.scale.set(0.9, 0.34, 1);
      label.position.y = 0.22;
      group.add(label);

      scene.add(group);
      nodeData.push({ group, dot, halo, label, x, y, z, pulse: Math.random() * Math.PI * 2 });
    }

    // Build edges between nearby nodes
    const edgeMat = new THREE.LineBasicMaterial({ color: 0x4FB7C5, transparent: true, opacity: 0.12 });
    const MAX_DIST = 5.5;
    const edgeList = [];
    for (let i = 0; i < nodeData.length; i++) {
      for (let j = i + 1; j < nodeData.length; j++) {
        const dx = nodeData[i].x - nodeData[j].x;
        const dy = nodeData[i].y - nodeData[j].y;
        const dz = nodeData[i].z - nodeData[j].z;
        const d = Math.sqrt(dx*dx + dy*dy + dz*dz);
        if (d < MAX_DIST && Math.random() > 0.55) {
          const pts = [
            new THREE.Vector3(nodeData[i].x, nodeData[i].y, nodeData[i].z),
            new THREE.Vector3(nodeData[j].x, nodeData[j].y, nodeData[j].z),
          ];
          const line = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(pts),
            edgeMat.clone()
          );
          scene.add(line);
          edgeList.push({ line, i, j, d, particles: [] });
        }
      }
    }

    // Flowing particles along edges
    const particleGeo = new THREE.SphereGeometry(0.04, 4, 4);
    const particleMat = new THREE.MeshBasicMaterial({ color: 0x67E8F9, transparent: true, opacity: 0 });
    edgeList.forEach(edge => {
      const count = Math.random() > 0.6 ? 2 : 1;
      for (let p = 0; p < count; p++) {
        const mesh = new THREE.Mesh(particleGeo, particleMat.clone());
        scene.add(mesh);
        edge.particles.push({ mesh, t: Math.random() });
      }
    });

    const onResize = () => {
      const w = mount.clientWidth, h = mount.clientHeight;
      camera.aspect = w / h; camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);

    let raf;
    const clock = new THREE.Clock();

    const tick = () => {
      raf = requestAnimationFrame(tick);
      const t = clock.getElapsedTime();

      // Animate nodes
      nodeData.forEach((n, i) => {
        const wave = Math.sin(t * 0.7 + n.pulse) * 0.5 + 0.5;
        n.halo.material.opacity = (0.06 + wave * 0.22);
        n.dot.material.opacity  = 0.5 + wave * 0.5;
        n.label.material.opacity = 0.15 + wave * 0.28;
        n.group.rotation.y = t * 0.3 + i * 0.4;
      });

      // Animate edges
      edgeList.forEach(edge => {
        const waveA = Math.sin(t * 0.5 + edge.i * 0.3) * 0.5 + 0.5;
        edge.line.material.opacity = 0.04 + waveA * 0.14;

        edge.particles.forEach(p => {
          p.t = (p.t + 0.0022) % 1;
          const a = nodeData[edge.i];
          const b = nodeData[edge.j];
          p.mesh.position.set(
            a.x + (b.x - a.x) * p.t,
            a.y + (b.y - a.y) * p.t,
            a.z + (b.z - a.z) * p.t,
          );
          const fade = p.t < 0.1 ? p.t / 0.1 : p.t > 0.9 ? (1 - p.t) / 0.1 : 1;
          p.mesh.material.opacity = fade * 0.85;
        });
      });

      // Slow camera drift
      camera.position.x = Math.sin(t * 0.045) * 1.8;
      camera.position.y = Math.cos(t * 0.035) * 0.9;
      camera.lookAt(0, 0, 0);

      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      renderer.dispose();
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mountRef} style={{ width: '100%', height: '100%' }} />;
};

export default CABotThreeScene;
