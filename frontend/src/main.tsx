import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { setupInterceptors } from './utils/interceptors';
import LenisProvider from './components/effects/LenisProvider';

// Initialize interceptors before rendering
setupInterceptors();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <ThemeProvider>
        <LenisProvider>
          <App />
        </LenisProvider>
      </ThemeProvider>
    </AuthProvider>
  </StrictMode>,
);
