import { motion, AnimatePresence } from 'framer-motion';
import { useLocation } from 'react-router-dom';
import { ReactNode } from 'react';

interface Props { children: ReactNode }

const curtainVariants = {
  initial: { scaleY: 0 },
  animate: { scaleY: [0, 1, 1, 0] },
  exit: {},
};

export default function PageTransition({ children }: Props) {
  const location = useLocation();

  return (
    <>
      {/* Page content fade */}
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
        >
          {children}
        </motion.div>
      </AnimatePresence>

      {/* Curtain wipe overlay */}
      <AnimatePresence>
        <motion.div
          key={`curtain-${location.pathname}`}
          initial={{ scaleY: 0, transformOrigin: 'top' }}
          animate={{
            scaleY: [0, 1, 1, 0],
            transformOrigin: ['top', 'top', 'bottom', 'bottom'],
          }}
          transition={{
            duration: 0.65,
            times: [0, 0.4, 0.6, 1],
            ease: 'easeInOut',
          }}
          aria-hidden="true"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9996,
            pointerEvents: 'none',
            background: 'linear-gradient(135deg, #4FB7C5 0%, #0e7490 100%)',
          }}
        />
      </AnimatePresence>
    </>
  );
}
