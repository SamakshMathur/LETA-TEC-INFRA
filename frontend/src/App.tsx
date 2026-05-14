import React from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';

import { Navbar, SystemFooter, ScrollToTop } from './components/layout';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { PublicRoute }    from './components/auth/PublicRoute';
import { authRoutes, protectedRoutes } from './routes';

const NotFound: React.FC = () => (
  <div className="flex flex-col items-center justify-center min-h-screen gap-6"
    style={{ background: '#07090D' }}>
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
        <div style={{ background: '#07090D', color: '#EF4444', minHeight: '100vh',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexDirection: 'column', gap: '1rem', fontFamily: 'monospace' }}>
          <h2>Something went wrong</h2>
          <pre style={{ color: '#A1AAB8', fontSize: '0.8rem', maxWidth: '80vw', overflow: 'auto' }}>
            {this.state.error.message}
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
      <main className="h-screen w-screen overflow-hidden bg-[#07090D] flex flex-col">
        {children}
      </main>
    );
  }

  return (
    <div className="min-h-screen flex flex-col"
      style={{ background: '#07090D', backgroundAttachment: 'fixed', color: '#A1AAB8' }}>
      <Navbar />
      <main className="flex-grow">{children}</main>
      <SystemFooter />
    </div>
  );
};

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
