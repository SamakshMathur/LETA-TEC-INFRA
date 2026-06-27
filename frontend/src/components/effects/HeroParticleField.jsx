import { useRef, useMemo } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

function ParticleCloud({ count = 2800 }) {
  const pointsRef = useRef(null);
  const { mouse } = useThree();

  const [positions, opacities] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const op = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 4 + Math.random() * 8;
      pos[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.5;
      pos[i * 3 + 2] = r * Math.cos(phi);
      op[i] = 0.15 + Math.random() * 0.55;
    }
    return [pos, op];
  }, [count]);

  useFrame((state) => {
    if (!pointsRef.current) return;
    const t = state.clock.elapsedTime;
    pointsRef.current.rotation.y = t * 0.015 + mouse.x * 0.08;
    pointsRef.current.rotation.x = Math.sin(t * 0.008) * 0.12 + mouse.y * 0.04;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.022}
        color="#4FB7C5"
        transparent
        opacity={0.55}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

function NearParticles({ count = 400 }) {
  const ref = useRef(null);
  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3]     = (Math.random() - 0.5) * 6;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 4;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 3;
    }
    return pos;
  }, [count]);

  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.y = state.clock.elapsedTime * -0.008;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.04}
        color="#67E8F9"
        transparent
        opacity={0.3}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  );
}

export default function HeroParticleField() {
  return (
    <div
      aria-hidden="true"
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 1,
      }}
    >
      <Canvas
        camera={{ position: [0, 0, 6], fov: 70 }}
        gl={{ alpha: true, antialias: false, powerPreference: 'high-performance' }}
        dpr={[1, 1.5]}
        style={{ background: 'transparent', width: '100%', height: '100%' }}
      >
        <fog attach="fog" args={['#000000', 8, 22]} />
        <ParticleCloud />
        <NearParticles />
      </Canvas>
    </div>
  );
}
