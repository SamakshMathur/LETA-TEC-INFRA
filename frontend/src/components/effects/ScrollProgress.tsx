import { useScroll, useSpring, motion } from 'framer-motion';

export default function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001,
  });

  return (
    <motion.div
      aria-hidden="true"
      style={{
        scaleX,
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        height: '2px',
        background: 'linear-gradient(90deg, #4FB7C5 0%, #67E8F9 50%, #4FB7C5 100%)',
        transformOrigin: '0%',
        zIndex: 9998,
        boxShadow: '0 0 8px rgba(103,232,249,0.6), 0 0 20px rgba(79,183,197,0.3)',
      }}
    />
  );
}
