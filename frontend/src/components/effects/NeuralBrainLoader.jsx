import React, { useRef, useMemo, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';

// --- MATH HELPERS ---

// Generate random point in sphere
function randomInSphere(radius = 1) {
  const u = Math.random();
  const v = Math.random();
  const theta = 2 * Math.PI * u;
  const phi = Math.acos(2 * v - 1);
  const r = Math.cbrt(Math.random()) * radius;
  const x = r * Math.sin(phi) * Math.cos(theta);
  const y = r * Math.sin(phi) * Math.sin(theta);
  const z = r * Math.cos(phi);
  return new THREE.Vector3(x, y, z);
}

// Generate point on a "Brain" shape
// Simplified as two highly wrinkled ellipsoids
function randomOnBrain(radius = 1) {
  // Hemisphere: -1 for left, 1 for right
  const hemisphere = Math.random() > 0.5 ? 1 : -1;
  
  // Basic Ellipsoid
  const u = Math.random();
  const v = Math.random();
  const theta = 2 * Math.PI * u;
  const phi = Math.acos(2 * v - 1);
  
  // Base Radius
  let r = radius;
  
  // Add "Wrinkles" using sine waves
  const frequency = 8;
  const amplitude = 0.15 * radius;
  const noise = Math.sin(theta * frequency) * Math.sin(phi * frequency) * amplitude;
  r += noise;
  
  // Ellipsoid scaling
  let x = r * Math.sin(phi) * Math.cos(theta);
  let y = r * Math.sin(phi) * Math.sin(theta);
  let z = r * Math.cos(phi);
  
  // Flatten bottom slightly
  y *= 0.8;
  
  // Elongate front-to-back
  z *= 1.2;
  
  // Separate hemispheres
  x *= 0.8; 
  x += hemisphere * (0.2 * radius); 

  return new THREE.Vector3(x, y, z);
}

const ParticleBrain = ({ count = 3000 }) => {
  const mesh = useRef();
  
  // Generate initial (CHAOS) and target (BRAIN) positions
  const { positions, targets, colors } = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const targets = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    
    const colorInside = new THREE.Color("#00ff88"); // Sentinel Green
    const colorOutside = new THREE.Color("#00aaff"); // Electric Blue

    for (let i = 0; i < count; i++) {
      // 1. Chaos Position (Scattered)
      const chaos = randomInSphere(12); 
      positions[i * 3] = chaos.x;
      positions[i * 3 + 1] = chaos.y;
      positions[i * 3 + 2] = chaos.z;
      
      // 2. Brain Position (Target)
      const brain = randomOnBrain(1.5);
      targets[i * 3] = brain.x;
      targets[i * 3 + 1] = brain.y;
      targets[i * 3 + 2] = brain.z;
      
      // 3. Color (Gradient based on brain Y height for depth)
      const mixedColor = colorInside.clone().lerp(colorOutside, (brain.y + 1) / 2);
      colors[i * 3] = mixedColor.r;
      colors[i * 3 + 1] = mixedColor.g;
      colors[i * 3 + 2] = mixedColor.b;
    }
    
    return { positions, targets, colors };
  }, [count]);

  // Animation Loop
  useFrame((state) => {
    if (!mesh.current) return;
    
    const time = state.clock.getElapsedTime();
    const positionsAttribute = mesh.current.geometry.attributes.position;
    
    // Lerp Speed: Lower = Slower formation
    const speed = 0.02; // Slightly faster for debug visibility
    
    mesh.current.rotation.y = time * 0.15;
    mesh.current.rotation.z = Math.sin(time * 0.5) * 0.05;

    for (let i = 0; i < count; i++) {
        const i3 = i * 3;
        
        // Current Pos
        let cx = positionsAttribute.array[i3];
        let cy = positionsAttribute.array[i3 + 1];
        let cz = positionsAttribute.array[i3 + 2];
        
        // Target Pos
        const tx = targets[i3];
        const ty = targets[i3 + 1];
        const tz = targets[i3 + 2];
        
        // Active noise
        const noiseFreq = 2;
        const noiseAmp = 0.05;
        const noiseX = Math.sin(time * noiseFreq + i) * noiseAmp;
        const noiseY = Math.cos(time * noiseFreq + i) * noiseAmp;
        const noiseZ = Math.sin(time * noiseFreq + i * 0.5) * noiseAmp;

        cx += (tx - cx) * speed + noiseX * 0.5;
        cy += (ty - cy) * speed + noiseY * 0.5;
        cz += (tz - cz) * speed + noiseZ * 0.5;

        positionsAttribute.array[i3] = cx;
        positionsAttribute.array[i3 + 1] = cy;
        positionsAttribute.array[i3 + 2] = cz;
    }
    
    positionsAttribute.needsUpdate = true;
  });

  return (
    <points ref={mesh}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={positions.length / 3}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
           attach="attributes-color"
           count={colors.length / 3}
           array={colors}
           itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.06} // Increased size
        vertexColors
        // transparent // Removed transparency for debug
        // opacity={0.8}
        sizeAttenuation={true}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
};

export default function NeuralBrainLoader() {
  // Decorative counter, randomized once per mount. useState's lazy
  // initializer runs exactly once (on the initial render) rather than
  // re-evaluating like useMemo would appear to the purity check.
  const [nodeCount] = useState(() => Math.floor(Math.random() * 500) + 1000);

  return (
    <div className="w-full h-80 relative">
        {/* Overlay Text */}
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-8 z-10 pointer-events-none">
            <h3 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-500 to-blue-400 font-mono uppercase tracking-widest animate-pulse drop-shadow-[0_0_10px_rgba(16,185,129,0.3)]">
                Synthesizing LETA Intelligence
            </h3>
            <p className="text-xs text-leta-gray-500 mt-2 font-mono tracking-wide">
                Optimizing {nodeCount} statutory nodes...
            </p>
        </div>

        <Canvas dpr={[1, 2]} gl={{ alpha: true }}>
            <PerspectiveCamera makeDefault position={[0, 0, 5]} fov={50} />
            {/* <color attach="background" args={['#000000']} /> Removed for transparency */}

            <ambientLight intensity={0.5} />
            <ParticleBrain />
            <OrbitControls enableZoom={false} autoRotate={false} enablePan={false} />
        </Canvas>
    </div>
  );
}
