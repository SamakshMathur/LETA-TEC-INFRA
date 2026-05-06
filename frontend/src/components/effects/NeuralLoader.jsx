import React, { useEffect, useRef, useState } from 'react';

class Node3D {
  constructor() {
    // Generate points on a sphere/ellipsoid surface
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos((Math.random() * 2) - 1);
    
    // Brain shape (two hemispheres slightly separated)
    const radius = 120;
    let x = radius * Math.sin(phi) * Math.cos(theta);
    let y = radius * Math.sin(phi) * Math.sin(theta);
    let z = radius * Math.cos(phi);
    
    // Flatten Y slightly
    y *= 0.8; 
    
    // Separate hemispheres
    if (x > 0) x += 15;
    else x -= 15;

    this.x = x;
    this.y = y;
    this.z = z;
    
    this.baseX = x;
    this.baseY = y;
    this.baseZ = z;

    // Pulse
    this.pulse = Math.random() * Math.PI;
    this.pulseSpeed = 0.05 + Math.random() * 0.05;
  }

  rotate(angle) {
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    
    // Rotate around Y axis
    const x = this.baseX * cos - this.baseZ * sin;
    const z = this.baseX * sin + this.baseZ * cos;
    
    this.x = x;
    this.z = z;
  }

  draw(ctx, centerX, centerY) {
    // Simple perspective projection
    const scale = 300 / (300 + this.z);
    const alpha = Math.max(0.1, (this.z + 120) / 240); // Fade back nodes
    
    const px = centerX + this.x * scale;
    const py = centerY + this.y * scale;

    this.screenX = px;
    this.screenY = py;
    this.scale = scale;

    // Pulse effect
    this.pulse += this.pulseSpeed;
    const r = 1.5 * scale + Math.sin(this.pulse) * 0.5;

    ctx.fillStyle = `rgba(0, 255, 148, ${alpha})`;
    ctx.beginPath();
    ctx.arc(px, py, r, 0, Math.PI * 2);
    ctx.fill();
  }
}

const NeuralBrainLoader = () => {
  const canvasRef = useRef(null);
  const [nodeCountText, setNodeCountText] = useState(1243);

  useEffect(() => {
    setNodeCountText(Math.floor(Math.random() * 500) + 1000);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    let width, height;
    let nodes = [];
    let animationFrameId;

    // Brain Shape Configuration
    const nodeCount = 180;
    const connectionDistance = 70;
    const rotationSpeed = 0.002;

    const resize = () => {
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };



    const init = () => {
      resize();
      nodes = [];
      for (let i = 0; i < nodeCount; i++) {
        nodes.push(new Node3D());
      }
    };

    let angle = 0;

    const animate = () => {
      ctx.clearRect(0, 0, width, height);
      
      const centerX = width / 2;
      const centerY = height / 2;
      
      angle += rotationSpeed;

      // Update and Draw Nodes
      nodes.forEach(node => {
        node.rotate(angle);
        node.draw(ctx, centerX, centerY);
      });

      // Draw Connections
      ctx.lineWidth = 0.5;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        
        // Check only a subset for performance
        for (let j = i + 1; j < nodes.length; j++) {
            const b = nodes[j];
            
            // 3D Distance check (approximate using base coordinates for stability or screen coords)
            // Using screen coords looks cooler (screenspace connections)
            const dx = a.screenX - b.screenX;
            const dy = a.screenY - b.screenY;
            const dist = Math.hypot(dx, dy);

            // Only connect if close AND explicitly on same Z-layer roughly (optional)
            if (dist < connectionDistance * a.scale) {
                const alpha = (1 - dist / (connectionDistance * a.scale)) * 0.3;
                ctx.strokeStyle = `rgba(0, 255, 148, ${alpha})`;
                ctx.beginPath();
                ctx.moveTo(a.screenX, a.screenY);
                ctx.lineTo(b.screenX, b.screenY);
                ctx.stroke();
            }
        }
      }
      
      // Draw centralized "thought beam" occasionally
      if (Math.random() > 0.95) {
          const activeNode = nodes[Math.floor(Math.random() * nodes.length)];
          if (activeNode.scale > 0.8) {
             ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
             ctx.beginPath();
             ctx.arc(activeNode.screenX, activeNode.screenY, 4, 0, Math.PI * 2);
             ctx.fill();
          }
      }

      animationFrameId = requestAnimationFrame(animate);
    };

    window.addEventListener('resize', resize);
    init();
    animate();

    return () => {
        window.removeEventListener('resize', resize);
        cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="flex flex-col items-center justify-center w-full h-full min-h-[400px] relative bg-[#FFFFFF] border border-leta-gray-200 overflow-hidden">
      <canvas 
        ref={canvasRef} 
        className="absolute inset-0 w-full h-full z-0"
      />
      
      {/* Overlay UI */}
      <div className="relative z-10 flex flex-col items-center justify-center p-8 bg-leta-black/30 backdrop-blur-sm rounded-full border border-sentinel-green/20 shadow-[0_0_50px_rgba(0,255,148,0.1)]">
        <h2 className="text-xl font-bold text-leta-gray-900 font-mono tracking-widest uppercase mb-1 animate-pulse">
           LETA Neural Core
        </h2>
        <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-sentinel-green rounded-full animate-ping"></span>
            <p className="text-sentinel-green font-mono text-[10px] uppercase tracking-[0.2em]">
            Synthesizing Legal Context
            </p>
        </div>
      </div>
    </div>
  );
};

export default NeuralBrainLoader;
