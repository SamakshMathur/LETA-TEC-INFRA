import { useRef, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Edges, OrthographicCamera, Text } from '@react-three/drei';
import * as THREE from 'three';

/* ── Individual cube ───────────────────────────────────────────────────── */
function IsoCube({ position, height = 1, floatDelay = 0, edgeColor = '#4FB7C5' }) {
  const groupRef = useRef();
  const baseY = position[1];

  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime * 0.4 + floatDelay;
    groupRef.current.position.y = baseY + Math.sin(t) * 0.06;
  });

  return (
    <group ref={groupRef} position={[position[0], baseY, position[2]]}>
      <mesh>
        <boxGeometry args={[0.9, height, 0.9]} />
        <meshStandardMaterial
          color="#060D18"
          roughness={0.6}
          metalness={0.5}
          transparent
          opacity={0.92}
        />
        <Edges scale={1.001} threshold={1} color={edgeColor} transparent opacity={0.75} />
      </mesh>
      {/* Top face highlight */}
      <mesh position={[0, height / 2 + 0.001, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.88, 0.88]} />
        <meshBasicMaterial color="#4FB7C5" transparent opacity={0.04} depthWrite={false} />
      </mesh>
    </group>
  );
}

/* ── Teal ground glow ──────────────────────────────────────────────────── */
function GroundGlow() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[2, -0.52, 2]}>
      <planeGeometry args={[9, 9]} />
      <meshBasicMaterial
        color="#4FB7C5"
        transparent
        opacity={0.035}
        depthWrite={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/* ── Single floating symbol sprite ────────────────────────────────────── */
function FloatingSymbol({ text, position, baseOpacity, speed, offset }) {
  const ref = useRef();
  const baseY = position[1];

  useFrame((state) => {
    if (!ref.current) return;
    const t = state.clock.elapsedTime;
    ref.current.position.y = baseY + Math.sin(t * speed + offset) * 0.35;
    const pulse = baseOpacity + Math.sin(t * speed * 1.5 + offset) * (baseOpacity * 0.5);
    if (ref.current.material) ref.current.material.opacity = Math.max(0, pulse);
  });

  return (
    <Text
      ref={ref}
      position={position}
      fontSize={0.28}
      color="#4FB7C5"
      anchorX="center"
      anchorY="middle"
      transparent
      opacity={baseOpacity}
      letterSpacing={0.05}
    >
      {text}
    </Text>
  );
}

/* ── All floating symbols ─────────────────────────────────────────────── */
function FloatingSymbols() {
  const symbols = useMemo(() => {
    const pool = ['₹', '§', '%', '¶', 'GST', 'ITC', '18%', 'SC', 'HC', 'IGST', 'CGST', '28%', '5%', 'GSTR'];
    // Seed deterministically so no hydration mismatch
    const list = [];
    for (let i = 0; i < 32; i++) {
      const seed = i * 137.508; // golden angle multiplier
      list.push({
        text: pool[i % pool.length],
        position: [
          Math.cos(seed) * (3 + (i % 5)),
          1.5 + (i % 4) * 1.2,
          Math.sin(seed) * (3 + (i % 4)),
        ],
        speed:      0.18 + (i % 7) * 0.04,
        offset:     (i * 0.91) % (Math.PI * 2),
        baseOpacity: 0.12 + (i % 5) * 0.06,
      });
    }
    return list;
  }, []);

  return (
    <>
      {symbols.map((s, i) => (
        <FloatingSymbol key={i} {...s} />
      ))}
    </>
  );
}

/* ── Cube grid ──────────────────────────────────────────────────────────── */
function CubeGrid() {
  const { mouse } = useThree();
  const groupRef = useRef();

  const cubes = useMemo(() => {
    const GRID = [
      [0, 0, 1.4, '#4FB7C5'], [1, 0, 0.9, '#4FB7C5'], [2, 0, 1.1, '#67E8F9'],
      [3, 0, 0.7, '#4FB7C5'], [4, 0, 1.3, '#4FB7C5'],
      [0, 1, 0.8, '#67E8F9'], [1, 1, 1.5, '#4FB7C5'], [2, 1, 1.0, '#4FB7C5'],
      [3, 1, 1.2, '#67E8F9'], [4, 1, 0.6, '#4FB7C5'],
      [0, 2, 1.1, '#4FB7C5'], [1, 2, 0.7, '#67E8F9'], [2, 2, 1.4, '#4FB7C5'],
      [3, 2, 0.9, '#4FB7C5'], [4, 2, 1.0, '#4FB7C5'],
      [1, 3, 1.2, '#4FB7C5'], [2, 3, 0.8, '#67E8F9'], [3, 3, 1.1, '#4FB7C5'],
      [2, 4, 0.9, '#4FB7C5'], [3, 4, 0.6, '#67E8F9'],
    ];
    return GRID.map(([col, row, height, edgeColor], i) => ({
      position: [col * 1.05, height / 2 - 0.5, row * 1.05],
      height,
      edgeColor,
      floatDelay: i * 0.38,
    }));
  }, []);

  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime;
    groupRef.current.rotation.y = Math.sin(t * 0.08) * 0.06 + mouse.x * 0.04;
    groupRef.current.rotation.x = Math.sin(t * 0.05) * 0.02 + mouse.y * 0.015;
  });

  return (
    <group ref={groupRef} position={[-2, 0, -2]}>
      {cubes.map((cube, i) => (
        <IsoCube key={i} {...cube} />
      ))}
      <GroundGlow />
    </group>
  );
}

/* ── Lighting ───────────────────────────────────────────────────────────── */
function Lighting() {
  return (
    <>
      <ambientLight intensity={0.15} />
      <pointLight position={[-4, 6, -4]} intensity={2.5} color="#4FB7C5" />
      <pointLight position={[6, 4, 6]}  intensity={1.0} color="#0e7490" />
      <pointLight position={[0, -2, 0]} intensity={0.5} color="#4FB7C5" />
    </>
  );
}

/* ── Export ─────────────────────────────────────────────────────────────── */
export default function IsometricCubeField() {
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
      <Canvas
        gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }}
        dpr={[1, 1.5]}
        style={{ background: 'transparent', width: '100%', height: '100%' }}
      >
        <OrthographicCamera makeDefault position={[8, 10, 8]} zoom={55} near={0.1} far={100} />
        <Lighting />
        <CubeGrid />
        <FloatingSymbols />
      </Canvas>
    </div>
  );
}
