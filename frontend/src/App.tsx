import React, { Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';

import { openRoutes, authRoutes, protectedRoutes } from './routes';
import {
  Navbar, SystemFooter, ScrollToTop,
  ProtectedRoute, PublicRoute,
  GrainOverlay, ScrollProgress, PageTransition,
} from './components';

// Shown by Suspense while a lazy-loaded route chunk downloads. Same
// background as the app itself (no flash), but with an actual spinner —
// the previous fallback was a bare colored div, which meant any route
// transition hitting an unfetched chunk looked frozen rather than loading.
const RouteLoadingFallback: React.FC = () => (
  <div
    className="flex items-center justify-center min-h-screen"
    style={{ background: '#060816' }}
  >
    <div
      className="w-8 h-8 rounded-full animate-spin"
      style={{
        border: '2.5px solid rgba(79,183,197,0.15)',
        borderTopColor: '#4FB7C5',
      }}
      role="status"
      aria-label="Loading"
    />
  </div>
);

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

// Whether a pathname is the LetaWorkspace chat page — it gets its own
// full-screen layout with no global Navbar/SystemFooter, since it has its
// own internal header. Was `.endsWith('/leta')`, which only matched the
// bare workspace URL (/:domainId/leta). Per-chat URLs
// (/:domainId/leta/:sessionId, added for shareable chat links) broke that
// the moment any chat was open — the check went false, so Layout fell
// through to the normal branch and rendered the global Navbar +
// SystemFooter ON TOP OF the workspace's own internal header/footer: two
// headers stacked, which is what showed up as the logo/"Back to
// Dashboard" overlap. Matching the whole "/leta" segment (with or without
// a chat id after it) instead of just the end of the string fixes it for
// every URL shape this route can take, not just the one without an id.
export function isLetaWorkspacePath(pathname: string): boolean {
  return /^\/[^/]+\/leta(\/|$)/.test(pathname);
}

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const isLetaWorkspace = isLetaWorkspacePath(location.pathname);

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
              The fallback used to be a bare dark div — matched the app
              background so there was no flash, but also gave zero feedback:
              any route transition that hit an unfetched chunk looked like a
              frozen, unresponsive screen for however long the download
              took, with nothing to tell a user it was actually doing
              something. A small centered spinner is still just as
              flash-free (same background) but now actually says so. */}
          <Suspense fallback={<RouteLoadingFallback />}>
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
