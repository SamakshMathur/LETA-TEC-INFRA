import React, { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';

import { Navbar, SystemFooter, ScrollToTop } from './components/layout';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { PublicRoute }    from './components/auth/PublicRoute';
import { openRoutes, authRoutes, protectedRoutes } from './routes';
import GrainOverlay from './components/effects/GrainOverlay';
import ScrollProgress from './components/effects/ScrollProgress';
import PageTransition from './components/effects/PageTransition';

const NotFound: React.FC = () => (
  <div className="flex flex-col items-center justify-center min-h-screen gap-6"
    style={{ background: '#000000' }}>
    <span className="font-display font-bold text-8xl text-white">404</span>
    <p className="text-sm font-mono" style={{ color: '#A1AAB8' }}>
      This route does not exist in the system.
    </p>
    <a href="/" className="px-8 py-3 rounded-xl font-bold text-black text-sm"
      style={{ background: '#67E8F9', boxShadow: '0 0 20px rgba(103,232,249,0.3)' }}>
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
        <div style={{ background: '#000000', color: '#EF4444', minHeight: '100vh',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexDirection: 'column', gap: '1rem', fontFamily: 'monospace', padding: '2rem' }}>
          <h2>Something went wrong</h2>
          <pre style={{ color: '#A1AAB8', fontSize: '0.75rem', maxWidth: '80vw', overflow: 'auto', whiteSpace: 'pre-wrap' }}>
            {this.state.error.message}
          </pre>
          <pre style={{ color: '#6B7280', fontSize: '0.65rem', maxWidth: '80vw', overflow: 'auto', whiteSpace: 'pre-wrap' }}>
            {this.state.error.stack}
          </pre>
          <button onClick={() => window.location.href = '/'}
            style={{ color: '#67E8F9', border: '1px solid rgba(103,232,249,0.4)',
              padding: '8px 24px', borderRadius: '8px', background: 'none', cursor: 'pointer' }}>
            Go Home
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const isLetaWorkspace = location.pathname.endsWith('/leta');

  if (isLetaWorkspace) {
    return (
      <main className="h-screen w-screen overflow-hidden bg-[#000000] flex flex-col">
        {children}
      </main>
    );
  }

  return (
    <div className="min-h-screen flex flex-col"
      style={{ background: '#000000', backgroundAttachment: 'fixed', color: '#A1AAB8' }}>
      <Navbar />
      <main className="flex-grow">
        <PageTransition>{children}</PageTransition>
      </main>
      <SystemFooter />
    </div>
  );
};

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <GrainOverlay />
        <ScrollProgress />
        <ScrollToTop />
        <Layout>
          {/* Suspense catches lazy-loaded page chunks while they download.
              Fallback is a plain dark screen — matches app background, no flash. */}
          <Suspense fallback={<div style={{ background: '#060816', minHeight: '100vh' }} />}>
            <Routes>
              {openRoutes.map(({ path, element }) => (
                <Route key={path} path={path} element={element} />
              ))}
              {authRoutes.map(({ path, element }) => (
                <Route key={path} path={path} element={<PublicRoute>{element}</PublicRoute>} />
              ))}
              {protectedRoutes.map(({ path, element }) => (
                <Route key={path} path={path} element={<ProtectedRoute>{element}</ProtectedRoute>} />
              ))}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </Layout>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
