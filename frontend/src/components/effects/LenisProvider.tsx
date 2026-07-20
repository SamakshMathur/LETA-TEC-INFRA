import { useEffect, useRef, createContext } from 'react';
import Lenis from 'lenis';

export const LenisContext = createContext<Lenis | null>(null);

interface Props { children: React.ReactNode }

export default function LenisProvider({ children }: Props) {
  const lenisRef = useRef<Lenis | null>(null);

  useEffect(() => {
    const lenis = new Lenis({
      duration: 0.6,
      easing: (t: number) => 1 - Math.pow(1 - t, 3),
      smoothWheel: true,
      wheelMultiplier: 1.2,
      touchMultiplier: 1.8,
      // Don't intercept scroll events inside containers that opt out
      prevent: (node: Element) =>
        node.hasAttribute('data-lenis-prevent') ||
        node.closest('[data-lenis-prevent]') !== null,
    });

    lenisRef.current = lenis;

    let rafId: number;
    function raf(time: number) {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    }
    rafId = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(rafId);
      lenis.destroy();
    };
  }, []);

  return (
    <LenisContext.Provider value={lenisRef.current}>
      {children}
    </LenisContext.Provider>
  );
}
