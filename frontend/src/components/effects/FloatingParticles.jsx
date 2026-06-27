import React, { useRef, useEffect } from 'react';

const FloatingParticles = ({ className = '' }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;

    const resize = () => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // Create particles
    const COUNT = 72;
    const particles = Array.from({ length: COUNT }, () => ({
      x:       Math.random() * canvas.width,
      y:       Math.random() * canvas.height,
      r:       0.6 + Math.random() * 1.4,
      opacity: 0.08 + Math.random() * 0.22,
      vx:      (Math.random() - 0.5) * 0.18,
      vy:      -0.06 - Math.random() * 0.12,   // drift upward slowly
      pulse:   Math.random() * Math.PI * 2,
      pulseSpeed: 0.008 + Math.random() * 0.012,
    }));

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (const p of particles) {
        p.pulse += p.pulseSpeed;
        const alpha = p.opacity * (0.7 + 0.3 * Math.sin(p.pulse));

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(79, 183, 197, ${alpha})`;
        ctx.fill();

        p.x += p.vx;
        p.y += p.vy;

        // Wrap
        if (p.y < -4)              p.y = canvas.height + 4;
        if (p.x < -4)              p.x = canvas.width  + 4;
        if (p.x > canvas.width + 4) p.x = -4;
      }

      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
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

export default FloatingParticles;
