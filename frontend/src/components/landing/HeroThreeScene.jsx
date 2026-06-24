import { useEffect, useRef } from 'react';
import * as THREE from 'three';

const GRID      = 6;
const CUBE_SIZE = 1;
const GAP       = 0.28;
const STEP      = CUBE_SIZE + GAP;
const SPREAD    = 12;

const STIFFNESS = 0.28;
const DAMPING   = 0.62;
const MAX_RISE  = 1.6; // cubes pop toward camera

const GRID_DATA = [
  { label: 'GSTR-1',  sub: 'OUTWARD',    status: 'ok'      },
  { label: 'GSTR-3B', sub: 'MONTHLY',    status: 'pending' },
  { label: 'GSTR-9',  sub: 'ANNUAL',     status: 'ok'      },
  { label: 'ITC-04',  sub: 'JOB WORK',   status: 'ok'      },
  { label: 'GSTR-7',  sub: 'TDS',        status: 'urgent'  },
  { label: 'GSTR-8',  sub: 'TCS',        status: 'ok'      },
  { label: '18%',     sub: 'RATE',       status: 'ok'      },
  { label: '12%',     sub: 'RATE',       status: 'ok'      },
  { label: '5%',      sub: 'RATE',       status: 'ok'      },
  { label: '28%',     sub: 'CESS',       status: 'pending' },
  { label: '0%',      sub: 'EXEMPT',     status: 'ok'      },
  { label: 'NULL',    sub: 'SUPPLY',     status: 'ok'      },
  { label: '₹1.2Cr',  sub: 'ITC CLAIM',  status: 'ok'      },
  { label: '₹45.3L',  sub: 'TURNOVER',   status: 'ok'      },
  { label: '₹8.7L',   sub: 'REFUND',     status: 'urgent'  },
  { label: '₹2.1Cr',  sub: 'LIABILITY',  status: 'pending' },
  { label: '₹15.4L',  sub: 'IGST',       status: 'ok'      },
  { label: '₹3.2Cr',  sub: 'CGST',       status: 'ok'      },
  { label: 'ARN',     sub: 'REFERENCE',  status: 'ok'      },
  { label: 'SCN',     sub: 'NOTICE',     status: 'urgent'  },
  { label: 'DRC-07',  sub: 'ORDER',      status: 'ok'      },
  { label: 'ASMT-10', sub: 'SCRUTINY',   status: 'pending' },
  { label: 'LUT',     sub: 'EXPORT',     status: 'ok'      },
  { label: 'RCM',     sub: 'REVERSE',    status: 'ok'      },
  { label: 'CGST',    sub: 'CENTRAL',    status: 'ok'      },
  { label: 'SGST',    sub: 'STATE',      status: 'ok'      },
  { label: 'IGST',    sub: 'INTER',      status: 'ok'      },
  { label: 'CESS',    sub: 'ADDITIONAL', status: 'ok'      },
  { label: 'ITC',     sub: 'INPUT TAX',  status: 'ok'      },
  { label: 'HSN',     sub: 'CODE',       status: 'ok'      },
  { label: 'Q1-FY25', sub: 'FILED',      status: 'ok'      },
  { label: 'Q2-FY25', sub: 'FILED',      status: 'ok'      },
  { label: 'Q3-FY25', sub: 'FILED',      status: 'ok'      },
  { label: 'Q4-FY25', sub: 'PENDING',    status: 'pending' },
  { label: 'ANN-FY25',sub: 'ANNUAL',     status: 'ok'      },
  { label: 'QRMP',    sub: 'SCHEME',     status: 'ok'      },
];

const SYMBOLS = [
  '₹', 'GST', 'GSTR-1', 'GSTR-3B', 'ITC', 'SCN', 'DRC', 'CGST', 'SGST', 'IGST',
  '18%', '28%', '5%', 'ITR', 'HSN', 'GSTIN', 'Sec.16', 'Sec.17', 'ARN', 'LUT',
  'RCM', 'QRMP', 'CESS', 'TDS', 'TCS', 'ASMT', 'AAR', 'GSTR-9', 'ITC-04', '12%',
];

const STATUS_COLOR = { ok: 0x4FB7C5, pending: 0x9FE5F0, urgent: 0xFFFFFF };
const STATUS_GLOW  = { ok: 0x67E8F9, pending: 0xB2F5FF, urgent: 0xFFFFFF };

function makeTopLabel(label, sub, status) {
  const cv = document.createElement('canvas');
  cv.width = 256; cv.height = 256;
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, 256, 256);
  const mainColor = status === 'urgent'  ? 'rgba(255,255,255,1.0)'
                  : status === 'pending' ? 'rgba(159,229,240,0.95)'
                  :                        'rgba(79,183,197,0.92)';
  const fs = label.length > 5 ? 30 : label.length > 3 ? 38 : 52;
  ctx.font = `700 ${fs}px 'IBM Plex Mono', monospace`;
  ctx.fillStyle = mainColor;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(label, 128, 108);
  ctx.font = `500 20px 'IBM Plex Mono', monospace`;
  ctx.fillStyle = 'rgba(167,179,194,0.65)';
  ctx.fillText(sub, 128, 162);
  if (status === 'urgent') {
    ctx.beginPath();
    ctx.arc(210, 52, 10, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.95)';
    ctx.fill();
  }
  return new THREE.CanvasTexture(cv);
}

function makeSymbolTexture(text) {
  const cv = document.createElement('canvas');
  cv.width = 128; cv.height = 64;
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, 128, 64);
  ctx.font = `700 ${text.length > 3 ? 16 : 22}px 'IBM Plex Mono', monospace`;
  ctx.fillStyle = 'rgba(79,183,197,0.7)';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(text, 64, 32);
  return new THREE.CanvasTexture(cv);
}

const HeroThreeScene = () => {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const W = mount.clientWidth, H = mount.clientHeight;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);

    // ── Scene / Camera ── straight in front of the vertical panel ─────────────
    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(72, W / H, 0.1, 200);
    camera.position.set(0, 0, 6.5);
    camera.lookAt(0, 0, 0);

    // ── Lighting ── key light in front so faces are lit ───────────────────────
    scene.add(new THREE.AmbientLight(0xffffff, 0.10));
    const keyLight = new THREE.PointLight(0x4FB7C5, 4.0, 24);
    keyLight.position.set(0, 2, 9);
    scene.add(keyLight);
    const fillLight = new THREE.PointLight(0x0e7490, 1.8, 20);
    fillLight.position.set(-7, 4, 7);
    scene.add(fillLight);

    // ── Grid group — rotated -90° on X so the flat grid becomes a vertical wall
    const gridGroup = new THREE.Group();
    gridGroup.rotation.x = -Math.PI / 2;
    scene.add(gridGroup);

    const boxGeo  = new THREE.BoxGeometry(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE);
    const edgeGeo = new THREE.EdgesGeometry(boxGeo);
    const topGeo  = new THREE.PlaneGeometry(CUBE_SIZE * 0.82, CUBE_SIZE * 0.82);
    const offset  = ((GRID - 1) * STEP) / 2;

    const cubes = [];

    for (let row = 0; row < GRID; row++) {
      for (let col = 0; col < GRID; col++) {
        const idx   = row * GRID + col;
        const data  = GRID_DATA[idx] || { label: 'GST', sub: '', status: 'ok' };
        const group = new THREE.Group();

        const body = new THREE.Mesh(
          boxGeo,
          new THREE.MeshStandardMaterial({ color: 0x020810, roughness: 0.55, metalness: 0.45 })
        );
        group.add(body);

        const edge = new THREE.LineSegments(
          edgeGeo,
          new THREE.LineBasicMaterial({
            color: STATUS_COLOR[data.status],
            transparent: true,
            opacity: data.status === 'urgent' ? 0.95 : 0.82,
          })
        );
        group.add(edge);

        const glow = new THREE.LineSegments(
          edgeGeo,
          new THREE.LineBasicMaterial({
            color: STATUS_GLOW[data.status],
            transparent: true,
            opacity: data.status === 'urgent' ? 0.35 : 0.18,
          })
        );
        glow.scale.setScalar(1.035);
        group.add(glow);

        // Label plane — after gridGroup rotation.x=-PI/2: local -Y → world +Z (toward camera)
        // So position at -Y face, normal must start as (0,-1,0) → use rotation.x=+PI/2
        const topFace = new THREE.Mesh(
          topGeo,
          new THREE.MeshBasicMaterial({
            map: makeTopLabel(data.label, data.sub, data.status),
            transparent: true,
            opacity: 0.95,
            side: THREE.DoubleSide,
            depthTest: false,
          })
        );
        topFace.rotation.x = Math.PI / 2;        // normal becomes (0,-1,0) in local → world +Z
        topFace.position.y = -(CUBE_SIZE / 2 + 0.01); // -Y local → front face in world
        topFace.renderOrder = 2;
        group.add(topFace);

        // Place in group local space (XZ plane)
        group.position.set(col * STEP - offset, 0, row * STEP - offset);
        gridGroup.add(group);

        // World X/Y after rotation (-PI/2 on X): localX→worldX, localZ→world-Y
        const worldX =  col * STEP - offset;
        const worldY = -(row * STEP - offset);

        cubes.push({
          group, edge, glow,
          row, col,
          worldX, worldY,
          status: data.status,
          posY: 0, velY: 0, targetY: 0,
        });
      }
    }

    // ── Floating symbols — spread in XY space (wall plane) ───────────────────
    const sprites = [];
    for (let i = 0; i < 60; i++) {
      const text = SYMBOLS[i % SYMBOLS.length];
      const tex  = makeSymbolTexture(text);
      const mat  = new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: Math.random() * 0.28 + 0.06, depthWrite: false });
      const sp   = new THREE.Sprite(mat);
      const s    = text.length > 2 ? 0.9 : 0.65;
      sp.scale.set(s, s * 0.5, 1);
      sp.position.set(
        (Math.random() - 0.5) * SPREAD * 2,
        (Math.random() - 0.5) * SPREAD * 1.2,
        (Math.random() - 0.5) * 3 - 1       // behind the wall
      );
      scene.add(sp);
      sprites.push({
        sprite: sp,
        baseOpacity: mat.opacity,
        vel: new THREE.Vector3(
          (Math.random() - 0.5) * 0.004,
          (Math.random() - 0.5) * 0.004,
          0
        ),
      });
    }

    // ── Mouse → wall plane (Z = 0) ────────────────────────────────────────────
    const mouseNDC   = new THREE.Vector2(-100, -100);
    const worldMouse = new THREE.Vector3(-999, -999, 0);
    const raycaster  = new THREE.Raycaster();
    const wallPlane  = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
    const canvas     = renderer.domElement;

    const onMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      mouseNDC.x =  ((e.clientX - rect.left) / rect.width)  * 2 - 1;
      mouseNDC.y = -((e.clientY - rect.top)  / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouseNDC, camera);
      raycaster.ray.intersectPlane(wallPlane, worldMouse);
    };

    const onClick = (e) => {
      const rect = canvas.getBoundingClientRect();
      if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) return;
      cubes.forEach(cube => {
        const dx = cube.worldX - worldMouse.x;
        const dy = cube.worldY - worldMouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 5) cube.velY += (1 - dist / 5) * 4.5;
      });
      sprites.forEach(({ sprite, vel }) => {
        const dx = sprite.position.x - worldMouse.x;
        const dy = sprite.position.y - worldMouse.y;
        const d  = Math.sqrt(dx * dx + dy * dy) + 0.001;
        if (d < 7) {
          const f = 0.18 * (1 - d / 7);
          vel.x += (dx / d) * f;
          vel.y += (dy / d) * f;
        }
      });
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('click', onClick);

    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth, h = mount.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    ro.observe(mount);

    // ── Animation loop ────────────────────────────────────────────────────────
    const clock = new THREE.Clock();

    const tick = () => {
      const t = clock.getElapsedTime();

      cubes.forEach((cube) => {
        const { group, edge, glow, worldX, worldY, status, row, col } = cube;

        const dx   = worldMouse.x - worldX;
        const dy   = worldMouse.y - worldY;
        const dist = Math.sqrt(dx * dx + dy * dy);

        const directInfl = Math.max(0, 1 - dist / 2.8);

        let waveInfl = 0;
        cubes.forEach(other => {
          if (other === cube) return;
          const gr = Math.abs(other.row - row) + Math.abs(other.col - col);
          if (gr <= 2) {
            const delay  = gr * 0.06;
            const otherH = Math.max(0, other.posY - delay * 2);
            waveInfl = Math.max(waveInfl, otherH * (1 - gr * 0.3));
          }
        });

        cube.targetY = Math.min(MAX_RISE, directInfl * MAX_RISE + waveInfl * 0.4);

        const accel = (cube.targetY - cube.posY) * STIFFNESS - cube.velY * DAMPING;
        cube.velY += accel;
        cube.posY += cube.velY;
        cube.posY = Math.max(0, cube.posY);

        // posY is local group Y → becomes world Z (toward camera)
        group.position.y = cube.posY;

        const infl  = directInfl + Math.min(0.5, cube.posY / MAX_RISE);
        const pulse = Math.sin(t * 0.7 + (row * GRID + col) * 0.45) * 0.03;

        edge.material.opacity = Math.min(1, (status === 'urgent' ? 0.90 : 0.72) + infl * 0.28 + pulse);
        glow.material.opacity = (status === 'urgent' ? 0.28 : 0.10) + infl * 0.55;

        if (infl > 0.55) {
          edge.material.color.setHex(0xFFFFFF);
        } else if (infl > 0.25) {
          edge.material.color.setHex(0xB2F5FF);
        } else {
          edge.material.color.setHex(STATUS_COLOR[status]);
        }

        if (status === 'urgent' && infl < 0.1) {
          const urgentPulse = 0.75 + Math.sin(t * 1.8 + (row + col) * 0.7) * 0.22;
          edge.material.opacity = urgentPulse;
          glow.material.opacity = (urgentPulse - 0.5) * 0.5;
        }
      });

      // Floating symbols drift in XY
      sprites.forEach(({ sprite, vel, baseOpacity }) => {
        vel.multiplyScalar(0.993);
        sprite.position.x += vel.x;
        sprite.position.y += vel.y;

        if (sprite.position.x >  SPREAD) sprite.position.x = -SPREAD;
        if (sprite.position.x < -SPREAD) sprite.position.x =  SPREAD;
        if (sprite.position.y >  SPREAD) sprite.position.y = -SPREAD;
        if (sprite.position.y < -SPREAD) sprite.position.y =  SPREAD;

        sprite.material.opacity = baseOpacity * (0.5 + Math.sin(t * 0.45 + sprite.position.x) * 0.5);

        const sx = sprite.position.x - worldMouse.x;
        const sy = sprite.position.y - worldMouse.y;
        const sd = Math.sqrt(sx * sx + sy * sy) + 0.001;
        if (sd < 3) {
          const push = 0.02 * (1 - sd / 3);
          vel.x += (sx / sd) * push;
          vel.y += (sy / sd) * push;
        }
      });

      // Subtle camera sway — stays centered facing the wall
      camera.position.x = Math.sin(t * 0.08) * 0.25;
      camera.position.y = Math.cos(t * 0.06) * 0.18;
      camera.lookAt(0, 0, 0);

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
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('click', onClick);
      renderer.dispose();
      if (mount.contains(canvas)) mount.removeChild(canvas);
    };
  }, []);

  return (
    <div
      ref={mountRef}
      style={{ position: 'absolute', inset: 0, top: '81px', zIndex: 1, overflow: 'hidden', background: '#000' }}
    />
  );
};

export default HeroThreeScene;
