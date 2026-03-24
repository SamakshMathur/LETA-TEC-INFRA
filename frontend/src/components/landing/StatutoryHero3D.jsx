import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Environment, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';

// Sentinel Color Palette
const COLORS = {
  blue: '#003B59',
  green: '#0B7350',
  white: '#FFFFFF',
};

// Abstract Statutory Layer Component
const StatutoryLayer = ({ position, rotation, scale, color, speed = 0.1 }) => {
  const meshRef = useRef();

  useFrame((state) => {
    if (!meshRef.current) return;
    // Very slow, "idling" rotation - authoritative and calm
    meshRef.current.rotation.y += 0.0005 * speed;
    meshRef.current.rotation.z += 0.0002 * speed;
  });

  return (
    <Float speed={2} rotationIntensity={0.1} floatIntensity={0.2}>
      <mesh 
        ref={meshRef} 
        position={position} 
        rotation={rotation} 
        scale={scale}
      >
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial 
          color={color} 
          roughness={0.7} // Matte finish
          metalness={0.1} // Low reflectivity
          transparent={true}
          opacity={0.9}
        />
      </mesh>
    </Float>
  );
};

// Main Scene Component
const StatutoryScene = () => {
  return (
    <>
      {/* Lighting Setup - Soft, directional, calm */}
      <ambientLight intensity={0.8} color="#ffffff" />
      <directionalLight position={[5, 10, 5]} intensity={1.5} color="#ffffff" castShadow />
      <pointLight position={[-5, -5, 5]} intensity={0.5} color={COLORS.green} />

      <group rotation={[0.2, -0.3, 0]}>
        {/* Central Core (The Reasoning Engine) - Deep Blue */}
        <StatutoryLayer 
          position={[0, 0, 0]} 
          rotation={[0, 0, 0]} 
          scale={[1.5, 4, 1.5]} 
          color={COLORS.blue} 
          speed={0.5} 
        />

        {/* Horizontal Planes (Acts/Rules) - Interlocking - White & Green */}
        <StatutoryLayer 
            position={[-1.2, 0.5, 0.5]} 
            rotation={[0, 0, 0.1]} 
            scale={[3, 0.1, 3]} 
            color={COLORS.white} 
            speed={0.8}
        />
        <StatutoryLayer 
            position={[1.2, -0.8, -0.5]} 
            rotation={[0, 0, -0.1]} 
            scale={[3, 0.1, 2.5]} 
            color={COLORS.green} 
            speed={0.7}
        />
        
        {/* Vertical Stabilizers - Structure */}
        <StatutoryLayer 
            position={[1.5, 1, 0]} 
            rotation={[0, 0, 0]} 
            scale={[0.2, 2.5, 0.2]} 
            color={COLORS.blue} 
            speed={0.3}
        />
         <StatutoryLayer 
            position={[-1.5, -1, 0]} 
            rotation={[0, 0, 0]} 
            scale={[0.2, 2.5, 0.2]} 
            color={COLORS.white} 
            speed={0.3}
        />

        {/* Floating Abstract Data Points - Subtle */}
        <StatutoryLayer position={[2, 2, 1]} rotation={[1, 1, 0]} scale={[0.3, 0.3, 0.3]} color={COLORS.green} speed={1} />
        <StatutoryLayer position={[-2, -2, -1]} rotation={[1, 0, 1]} scale={[0.2, 0.2, 0.2]} color={COLORS.white} speed={1.2} />
      </group>
    </>
  );
};

const StatutoryHero3D = () => {
  return (
    <div className="absolute inset-0 z-0 opacity-40 pointer-events-none">
      <Canvas dpr={[1, 2]}> {/* Handle high DPR devices gracefully */}
        <PerspectiveCamera makeDefault position={[0, 0, 8]} fov={45} />
        <StatutoryScene />
      </Canvas>
      {/* Gradient Overlay to ensure text readability and blend with background */}
      <div className="absolute inset-0 bg-gradient-to-r from-sentinel-blue/90 via-sentinel-blue/50 to-transparent" />
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-sentinel-blue" />
    </div>
  );
};

export default StatutoryHero3D;
