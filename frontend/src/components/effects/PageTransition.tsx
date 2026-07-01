import { AnimatePresence, motion } from 'framer-motion';
import { useLocation } from 'react-router-dom';
import { ReactNode } from 'react';

interface Props { children: ReactNode }

export default function PageTransition({ children }: Props) {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
