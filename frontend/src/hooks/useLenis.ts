import { useContext } from 'react';
import { LenisContext } from '../components/effects/LenisProvider';

export const useLenis = () => useContext(LenisContext);
