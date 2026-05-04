import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

import { Navbar, SystemFooter, ScrollToTop } from './components/layout';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { PublicRoute }    from './components/auth/PublicRoute';
import { authRoutes, protectedRoutes } from './routes';

const NotFound: React.FC = () => (
  <div className="flex flex-col items-center justify-center min-h-screen gap-6"
    style={{ backgroundColor: 'var(--surface)' }}>
    <span className="font-display font-bold text-8xl" style={{ color: '#2a2a2a' }}>404</span>
    <p className="text-sm font-mono" style={{ color: '#9a9a9a' }}>
      This route does not exist in the system.
    </p>
    <a href="/" className="btn-titan px-8 py-3">Return Home</a>
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
        <div style={{ backgroundColor: '#141313', color: '#ff6b6b', minHeight: '100vh',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexDirection: 'column', gap: '1rem', fontFamily: 'monospace' }}>
          <h2>Something went wrong</h2>
          <pre style={{ color: '#999', fontSize: '0.8rem', maxWidth: '80vw', overflow: 'auto' }}>
            {this.state.error.message}
          </pre>
          <button onClick={() => window.location.href = '/'}
            style={{ color: '#4edea3', border: '1px solid #4edea3',
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
  <div className="min-h-screen flex flex-col relative"
    style={{ backgroundColor: 'var(--surface)', color: 'var(--on-surface)' }}>
    <div className="fixed inset-0 bg-noise z-10 pointer-events-none" />
    <Navbar />
    <main className="flex-grow relative transition-all duration-500">{children}</main>
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
            {/* Auth routes — redirect to dashboard if already logged in */}
            {authRoutes.map(({ path, element }) => (
              <Route key={path} path={path} element={<PublicRoute>{element}</PublicRoute>} />
            ))}

            {/* Protected routes — redirect to login if not authenticated */}
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
