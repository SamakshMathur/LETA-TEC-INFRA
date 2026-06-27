import { useEffect, useRef } from 'react';
import * as THREE from 'three';

const N       = 5;
const SPACING = 2.8;
const SYMBOLS = ['₹', 'GST', 'ITC', 'SCN', 'DRC'];

function makeLabel(text) {
  const cv = document.createElement('canvas');
  cv.width = 128; cv.height = 64;
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, 128, 64);
  ctx.font = `700 ${text.length > 3 ? 15 : 20}px 'IBM Plex Mono', monospace`;
  ctx.fillStyle = 'rgba(79,183,197,0.65)';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(text, 64, 32);
  return new THREE.CanvasTexture(cv);
}

function makeGlowTex() {
  const cv = document.createElement('canvas');
  cv.width = cv.height = 256;
  const ctx = cv.getContext('2d');
  const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
  g.addColorStop(0,   'rgba(79,183,197,1)');
  g.addColorStop(0.25,'rgba(79,183,197,0.6)');
  g.addColorStop(0.55,'rgba(79,183,197,0.15)');
  g.addColorStop(1,   'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(cv);
}

const PipelineThreeScene = ({ activeStep, onStepClick, overlay = false }) => {
  const mountRef  = useRef(null);
  const activeRef = useRef(activeStep);
  const hoverRef  = useRef(-1);

  useEffect(() => { activeRef.current = activeStep; }, [activeStep]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const W = mount.clientWidth  || 900;
    const H = mount.clientHeight || (overlay ? 300 : 200);

    // ── Renderer ──────────────────────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    if (overlay) renderer.domElement.style.mixBlendMode = 'screen';
    mount.appendChild(renderer.domElement);

    // ── Scene / Camera ────────────────────────────────────────────────────────
    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(overlay ? 72 : 58, W / H, 0.1, 200);
    if (overlay) {
      camera.position.set(0, 2.5, 10);
      camera.lookAt(0, 0.4, 0);
    } else {
      camera.position.set(0, 1.2, 7.5);
      camera.lookAt(0, 0, 0);
    }

    // ── Lights ────────────────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0x0a1a22, 4));
    const topLight = new THREE.PointLight(0x4FB7C5, 4, 30);
    topLight.position.set(0, 10, 3);
    scene.add(topLight);

    // ── Shared geometries ─────────────────────────────────────────────────────
    const radius  = overlay ? 0.38 : 0.58;
    const icoGeo  = new THREE.IcosahedronGeometry(radius, 1);
    const edgeGeo = new THREE.EdgesGeometry(icoGeo);
    const offset  = ((N - 1) * SPACING) / 2;
    const nodeY   = overlay ? 0.4 : 0;
    const glowTex = overlay ? makeGlowTex() : null;

    // ── Build nodes ───────────────────────────────────────────────────────────
    const nodes = [];
    for (let i = 0; i < N; i++) {
      const x     = i * SPACING - offset;
      const group = new THREE.Group();
      group.position.set(x, nodeY, 0);

      // Dark body
      const body = new THREE.Mesh(icoGeo, new THREE.MeshStandardMaterial({
        color: 0x020810, roughness: 0.35, metalness: 0.9,
        emissive: new THREE.Color(0x4FB7C5),
        emissiveIntensity: overlay ? 0.15 : 0.05,
        transparent: overlay,
        opacity: overlay ? 0.55 : 1,
      }));
      group.add(body);

      // Primary wireframe
      const wire = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({
        color: 0x4FB7C5, transparent: true, opacity: overlay ? 0.35 : 0.20,
      }));
      wire.scale.setScalar(1.02);
      group.add(wire);

      // Outer halo wireframe
      const halo = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({
        color: 0x67E8F9, transparent: true, opacity: overlay ? 0.08 : 0.05,
      }));
      halo.scale.setScalar(1.22);
      group.add(halo);

      // Glow sprite — only in overlay mode
      let glowSprite = null;
      if (overlay && glowTex) {
        glowSprite = new THREE.Sprite(new THREE.SpriteMaterial({
          map: glowTex, transparent: true, opacity: 0,
          blending: THREE.AdditiveBlending, depthWrite: false,
        }));
        glowSprite.scale.set(1.8, 1.8, 1);
        group.add(glowSprite);
      }

      // Attached point light
      const nLight = new THREE.PointLight(0x4FB7C5, 0, overlay ? 8 : 6);
      group.add(nLight);

      scene.add(group);
      nodes.push({ group, body, wire, halo, nLight, glowSprite });
    }

    // ── Floating symbols (standalone mode only) ───────────────────────────────
    if (!overlay) {
      for (let i = 0; i < 30; i++) {
        const tex = makeLabel(SYMBOLS[i % SYMBOLS.length]);
        const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: Math.random() * 0.2 + 0.04, depthWrite: false });
        const sp  = new THREE.Sprite(mat);
        const s   = 0.6;
        sp.scale.set(s, s * 0.5, 1);
        sp.position.set(
          (Math.random() - 0.5) * 18,
          (Math.random() - 0.5) * 4 + 1,
          (Math.random() - 0.5) * 4 - 1
        );
        scene.add(sp);
      }
    }

    // ── Connections + flowing particles ───────────────────────────────────────
    const conns = [];
    for (let i = 0; i < N - 1; i++) {
      const s = nodes[i].group.position.clone();
      const e = nodes[i + 1].group.position.clone();
      const m = new THREE.Vector3((s.x + e.x) / 2, nodeY + 0.55, 0);
      const curve = new THREE.QuadraticBezierCurve3(s, m, e);

      const tube = new THREE.Mesh(
        new THREE.TubeGeometry(curve, 40, 0.016, 6, false),
        new THREE.MeshBasicMaterial({ color: 0x4FB7C5, transparent: true, opacity: overlay ? 0.28 : 0.14 })
      );
      scene.add(tube);

      const particles = Array.from({ length: 6 }, (_, p) => {
        const pm = new THREE.Mesh(
          new THREE.SphereGeometry(0.055, 6, 6),
          new THREE.MeshBasicMaterial({ color: 0x67E8F9, transparent: true, opacity: 0 })
        );
        scene.add(pm);
        return { mesh: pm, t: p / 6 };
      });

      conns.push({ curve, tube, particles });
    }

    // ── Raycaster ─────────────────────────────────────────────────────────────
    const raycaster = new THREE.Raycaster();
    const mouse     = new THREE.Vector2();

    const hitTest = (e) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.set(
        ((e.clientX - rect.left) / rect.width)  *  2 - 1,
        ((e.clientY - rect.top)  / rect.height) * -2 + 1
      );
      raycaster.setFromCamera(mouse, camera);
      for (let i = 0; i < nodes.length; i++) {
        if (raycaster.intersectObjects(nodes[i].group.children, true).length > 0) return i;
      }
      return -1;
    };

    const onMove  = (e) => {
      hoverRef.current = hitTest(e);
      renderer.domElement.style.cursor = hoverRef.current >= 0 ? 'pointer' : 'default';
    };
    const onClick = (e) => { const idx = hitTest(e); if (idx >= 0) onStepClick(idx); };
    renderer.domElement.addEventListener('mousemove', onMove);
    renderer.domElement.addEventListener('click', onClick);

    // ── Resize ────────────────────────────────────────────────────────────────
    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth, h = mount.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h; camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    ro.observe(mount);

    // ── Animation loop ────────────────────────────────────────────────────────
    const clock = new THREE.Clock();
    const lerp  = (a, b, t) => a + (b - a) * t;

    const tick = () => {
      const t      = clock.getElapsedTime();
      const active = activeRef.current;
      const hover  = hoverRef.current;

      nodes.forEach((node, i) => {
        const isActive = i === active;
        const isPassed = i < active;
        const isHover  = i === hover && i !== active;

        // Scale
        const ts = isActive ? 1.30 : isHover ? 1.10 : 1.0;
        node.group.scale.lerp(new THREE.Vector3(ts, ts, ts), 0.06);

        // Rotation
        node.group.rotation.y = t * 0.28 + i * 0.6;
        node.group.rotation.x = Math.sin(t * 0.17 + i) * 0.10;

        // Emissive
        const tE = isActive ? (overlay ? 2.0 : 1.1) : isPassed ? 0.28 : 0.04;
        node.body.material.emissiveIntensity = lerp(node.body.material.emissiveIntensity, tE, 0.07);

        // Wire opacity
        const tW = isActive ? 0.95 : isPassed ? 0.50 : isHover ? 0.50 : (overlay ? 0.30 : 0.18);
        node.wire.material.opacity = lerp(node.wire.material.opacity, tW, 0.07);

        // Halo opacity
        const tH = isActive ? 0.38 : 0.06;
        node.halo.material.opacity = lerp(node.halo.material.opacity, tH, 0.06);

        // Glow sprite
        if (node.glowSprite) {
          const pulse = isActive ? 1 + Math.sin(t * 3.2) * 0.10 : 1;
          const tG    = isActive ? 0.60 * pulse : isHover ? 0.18 : 0.02;
          node.glowSprite.material.opacity = lerp(node.glowSprite.material.opacity, tG, 0.06);
          const gs = (isActive ? 2.6 : 1.6) * pulse;
          node.glowSprite.scale.setScalar(gs);
        }

        // Node light
        const tL = isActive ? (overlay ? 4.5 : 2.8) : 0;
        node.nLight.intensity = lerp(node.nLight.intensity, tL, 0.07);
      });

      // Particles
      conns.forEach(({ particles, curve }) => {
        particles.forEach(p => {
          p.t = (p.t + 0.0028) % 1;
          curve.getPoint(p.t, p.mesh.position);
          const fade = p.t < 0.12 ? p.t / 0.12 : p.t > 0.88 ? (1 - p.t) / 0.12 : 1;
          p.mesh.material.opacity = fade * (overlay ? 0.92 : 0.80);
        });
      });

      // Camera drift
      if (overlay) {
        camera.position.x = Math.sin(t * 0.055) * 0.3;
        camera.position.y = 2.5 + Math.cos(t * 0.038) * 0.15;
        camera.lookAt(0, 0.4, 0);
      } else {
        camera.position.x = Math.sin(t * 0.055) * 0.4;
        camera.position.y = 2.2 + Math.cos(t * 0.038) * 0.18;
        camera.lookAt(0, 0, 0);
      }

      renderer.render(scene, camera);
    };
    renderer.setAnimationLoop(tick);

    const onVisibility = () => {
      if (document.hidden) renderer.setAnimationLoop(null);
      else renderer.setAnimationLoop(tick);
    };
    document.addEventListener('visibilitychange', onVisibility);

    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) renderer.setAnimationLoop(tick);
      else renderer.setAnimationLoop(null);
    }, { threshold: 0 });
    io.observe(mount);

    return () => {
      renderer.setAnimationLoop(null);
      document.removeEventListener('visibilitychange', onVisibility);
      ro.disconnect();
      io.disconnect();
      renderer.domElement.removeEventListener('mousemove', onMove);
      renderer.domElement.removeEventListener('click', onClick);
      renderer.dispose();
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={mountRef} style={{ width: '100%', height: overlay ? '100%' : 200 }} />
  );
};

export default PipelineThreeScene;
