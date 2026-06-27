import { useEffect, useState } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';

export default function CustomCursor() {
  const cursorX = useMotionValue(-200);
  const cursorY = useMotionValue(-200);
  const [hovering, setHovering] = useState(false);
  const [clicking, setClicking] = useState(false);
  const [visible, setVisible] = useState(false);

  const dotX = useSpring(cursorX, { damping: 40, stiffness: 1000, mass: 0.2 });
  const dotY = useSpring(cursorY, { damping: 40, stiffness: 1000, mass: 0.2 });
  const ringX = useSpring(cursorX, { damping: 26, stiffness: 320, mass: 0.6 });
  const ringY = useSpring(cursorY, { damping: 26, stiffness: 320, mass: 0.6 });

  useEffect(() => {
    const move = (e: MouseEvent) => {
      cursorX.set(e.clientX);
      cursorY.set(e.clientY);
      setVisible(true);
    };
    const down = () => setClicking(true);
    const up = () => setClicking(false);
    const leave = () => setVisible(false);
    const enter = () => setVisible(true);

    window.addEventListener('mousemove', move);
    window.addEventListener('mousedown', down);
    window.addEventListener('mouseup', up);
    document.documentElement.addEventListener('mouseleave', leave);
    document.documentElement.addEventListener('mouseenter', enter);
    return () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mousedown', down);
      window.removeEventListener('mouseup', up);
      document.documentElement.removeEventListener('mouseleave', leave);
      document.documentElement.removeEventListener('mouseenter', enter);
    };
  }, []);

  useEffect(() => {
    const onEnter = () => setHovering(true);
    const onLeave = () => setHovering(false);
    const selectors = 'a, button, [role="button"], input, select, textarea, label, [data-hover]';

    const attach = () => {
      document.querySelectorAll(selectors).forEach(el => {
        el.addEventListener('mouseenter', onEnter);
        el.addEventListener('mouseleave', onLeave);
      });
    };
    attach();

    const obs = new MutationObserver(attach);
    obs.observe(document.body, { childList: true, subtree: true });
    return () => {
      obs.disconnect();
      document.querySelectorAll(selectors).forEach(el => {
        el.removeEventListener('mouseenter', onEnter);
        el.removeEventListener('mouseleave', onLeave);
      });
    };
  }, []);

  const ringSize = clicking ? 20 : hovering ? 52 : 36;
  const dotSize = clicking ? 3 : 5;

  return (
    <>
      {/* Outer ring — lagging behind */}
      <motion.div
        aria-hidden="true"
        style={{
          x: ringX,
          y: ringY,
          translateX: '-50%',
          translateY: '-50%',
          position: 'fixed',
          top: 0,
          left: 0,
          pointerEvents: 'none',
          zIndex: 9999,
          borderRadius: '50%',
        }}
        className="hidden lg:block"
        animate={{
          width: ringSize,
          height: ringSize,
          borderColor: hovering ? 'rgba(79,183,197,0.9)' : 'rgba(255,255,255,0.3)',
          borderWidth: '1px',
          borderStyle: 'solid',
          opacity: visible ? 1 : 0,
          scale: clicking ? 0.88 : 1,
        }}
        transition={{ duration: 0.15, ease: 'easeOut' }}
      />

      {/* Inner dot — snappy */}
      <motion.div
        aria-hidden="true"
        style={{
          x: dotX,
          y: dotY,
          translateX: '-50%',
          translateY: '-50%',
          position: 'fixed',
          top: 0,
          left: 0,
          pointerEvents: 'none',
          zIndex: 10000,
          borderRadius: '50%',
          backgroundColor: hovering ? '#4FB7C5' : '#ffffff',
          mixBlendMode: 'difference',
        }}
        className="hidden lg:block"
        animate={{
          width: dotSize,
          height: dotSize,
          opacity: visible ? 1 : 0,
          scale: clicking ? 0.6 : 1,
        }}
        transition={{ duration: 0.1 }}
      />
    </>
  );
}
