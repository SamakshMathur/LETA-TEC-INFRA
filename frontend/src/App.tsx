import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

import { Navbar, SystemFooter, ScrollToTop } from './components/layout';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { PublicRoute }    from './components/auth/PublicRoute';
import { authRoutes, protectedRoutes } from './routes';

const NotFound: React.FC = () => (
  <div className="flex flex-col items-center justify-center min-h-screen gap-6"
    style={{ background: 'linear-gradient(180deg, #060816 0%, #0B1020 100%)' }}>
    <span className="font-display font-bold text-8xl text-white">404</span>
    <p className="text-sm font-mono" style={{ color: '#94A3B8' }}>
      This route does not exist in the system.
    </p>
    <a href="/" className="px-8 py-3 rounded-xl font-bold text-white text-sm"
      style={{ background: 'linear-gradient(135deg, #7C3AED, #5B21B6)', boxShadow: '0 0 20px rgba(124,58,237,0.4)' }}>
      Return Home
    </a>
  </div>
);

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ background: '#060816', color: '#ff6b6b', minHeight: '100vh',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexDirection: 'column', gap: '1rem', fontFamily: 'monospace' }}>
          <h2>Something went wrong</h2>
          <pre style={{ color: '#94A3B8', fontSize: '0.8rem', maxWidth: '80vw', overflow: 'auto' }}>
            {this.state.error.message}
          </pre>
          <button onClick={() => window.location.href = '/'}
            style={{ color: '#A78BFA', border: '1px solid rgba(124,58,237,0.4)',
              padding: '8px 24px', borderRadius: '8px', background: 'none', cursor: 'pointer' }}>
            Go Home
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="min-h-screen flex flex-col"
    style={{ background: 'linear-gradient(180deg, #060816 0%, #0B1020 100%)', backgroundAttachment: 'fixed', color: '#CBD5E1' }}>
    <Navbar />
    <main className="flex-grow">{children}</main>
    <SystemFooter />
  </div>
);

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <ScrollToTop />
        <Layout>
          <Routes>
            {authRoutes.map(({ path, element }) => (
              <Route key={path} path={path} element={<PublicRoute>{element}</PublicRoute>} />
            ))}
            {protectedRoutes.map(({ path, element }) => (
              <Route key={path} path={path} element={<ProtectedRoute>{element}</ProtectedRoute>} />
            ))}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Layout>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
