import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Shield, ChevronRight, Scale } from 'lucide-react';

import cx from 'classnames/bind';
import styles from './SovereignHero.module.css';

const cn = cx.bind(styles);

const InteractiveDotGrid = () => {
  const canvasRef = React.useRef(null);
  const mouseRef = React.useRef({ x: -1000, y: -1000, targetX: -1000, targetY: -1000 });

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    const handleMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current.targetX = e.clientX - rect.left;
      mouseRef.current.targetY = e.clientY - rect.top;
    };

    const handleMouseLeave = () => {
      mouseRef.current.targetX = -1000;
      mouseRef.current.targetY = -1000;
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseleave', handleMouseLeave);

    const spacing = 22; // 18px-24px spacing
    const interactionRadius = 140;

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Smooth mouse interpolation (LERP) for ultra-premium feel
      mouseRef.current.x += (mouseRef.current.targetX - mouseRef.current.x) * 0.1;
      mouseRef.current.y += (mouseRef.current.targetY - mouseRef.current.y) * 0.1;

      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;

      for (let x = spacing / 2; x < width; x += spacing) {
        for (let y = spacing / 2; y < height; y += spacing) {
          const dx = mx - x;
          const dy = my - y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          let dotRadius = 1.0;
          let alpha = 0.18;

          if (dist < interactionRadius) {
            const force = (interactionRadius - dist) / interactionRadius;
            // Subtle bulge/distortion
            dotRadius = 1.0 + force * 1.5;
            alpha = 0.18 + force * 0.42;
          }

          ctx.beginPath();
          ctx.arc(x, y, dotRadius, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(94, 206, 220, ${alpha})`;
          ctx.fill();
        }
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return <canvas ref={canvasRef} className={cn('interactiveDotGridCanvas')} />;
};

const SovereignHero = () => {
  return (
    <section className={cn('heroSection')}>

      {/* Cinematic Layered Background System */}
      <div className={cn('bgNoiseOverlay')} />
      <InteractiveDotGrid />
      <div className={cn('bgRadialFalloff')} />
      <div className={cn('bgEdgeDarkening')} />
      <div className={cn('bgLightShaft1')} />
      <div className={cn('bgLightShaft2')} />
      <div className={cn('bgDepthBlurOrb1')} />
      <div className={cn('bgDepthBlurOrb2')} />

      {/* Ambient Floating Dust Particles */}
      <div className={cn('dustParticlesContainer')}>
        <div className={cn('dustParticle', 'p1')} />
        <div className={cn('dustParticle', 'p2')} />
        <div className={cn('dustParticle', 'p3')} />
        <div className={cn('dustParticle', 'p4')} />
        <div className={cn('dustParticle', 'p5')} />
        <div className={cn('dustParticle', 'p6')} />
      </div>

      <div className={cn('gridContainer')}>
        <div className={cn('grid')}>
          
          {/* Left Column: Premium Typography & Content */}
          <div className={cn('leftColumn')}>
            
            {/* System Status Indicator */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className={cn('statusIndicator')}
            >
              <span className={cn('pingDotContainer')}>
                <span className={cn('pingDot')}></span>
                <span className={cn('staticDot')}></span>
              </span>
              <span className={cn('statusText')}>
                Enterprise Statutory Intelligence
              </span>
            </motion.div>
 
            {/* Cinematic Hero Header */}
            <motion.h1
              initial={{ opacity: 0, y: 25 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className={cn('heroHeading')}
            >
              Legal and TAX <br />
              <span className={cn('headingGradient')}>
                Assistant
              </span>
            </motion.h1>
 
            {/* Low-noise high-impact Supporting Copy */}
            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.25 }}
              className={cn('supportingCopy')}
            >
              Professional GST and legal advisory intelligence for compliance and litigation workflows. Built with high-fidelity citations, circulars, and Indian judicial precedents.
            </motion.p>
 
            {/* CTA Elements */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.35 }}
              className={cn('ctaContainer')}
            >
              <Link to="/gst">
                <button className={cn('ctaButtonPrimary')}>
                  Start Consultation
                  <ChevronRight size={14} className={cn('chevronIcon')} />
                </button>
              </Link>
              <Link to="/about">
                <button className={cn('ctaButtonSecondary')}>
                  Learn More
                </button>
              </Link>
            </motion.div>
 
            {/* Trust Badges */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.5 }}
              className={cn('trustBadges')}
            >
              <div className={cn('badge')}>
                <Shield size={14} className={cn('badgeIcon')} />
                <span className={cn('badgeText')}>
                  SECURE ENCRYPTED ARCHIVE
                </span>
              </div>
              <div className={cn('badge')}>
                <Scale size={14} className={cn('badgeIcon')} />
                <span className={cn('badgeText')}>
                  STATUTORY PRECISION SYSTEM
                </span>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default SovereignHero;
