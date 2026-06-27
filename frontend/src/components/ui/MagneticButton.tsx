import { useRef, ReactNode } from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';

interface Props {
  children: ReactNode;
  strength?: number;
  className?: string;
}

export default function MagneticButton({ children, strength = 0.28, className = '' }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const x = useSpring(rawX, { stiffness: 280, damping: 22, mass: 0.5 });
  const y = useSpring(rawY, { stiffness: 280, damping: 22, mass: 0.5 });

  const onMove = (e: React.MouseEvent) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    rawX.set((e.clientX - rect.left - rect.width / 2) * strength);
    rawY.set((e.clientY - rect.top - rect.height / 2) * strength);
  };

  const onLeave = () => {
    rawX.set(0);
    rawY.set(0);
  };

  return (
    <motion.div
      ref={ref}
      style={{ x, y, display: 'inline-block' }}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className={className}
    >
      {children}
    </motion.div>
  );
}
