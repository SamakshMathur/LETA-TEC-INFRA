import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

// Layout
import { Navbar, SystemFooter, ScrollToTop } from './components/layout';

// Dashboard
import { LawDashboard } from './components/dashboard';

// Pages
import {
  Home, About, Documentation,
  GST, GstTemplates, TemplateCustomization,
  AdminTemplateDashboard, AdminUploadPortal,
  SignupPage,
} from './pages';

// Auth Components
import LoginPage from './pages/auth/login';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { PublicRoute } from './components/auth/PublicRoute';
import { ROUTES } from './constants/routes';

const NotFound: React.FC = () => (
  <div
    className="flex flex-col items-center justify-center min-h-screen gap-6"
    style={{ backgroundColor: 'var(--surface)' }}
  >
    <span className="font-display font-bold text-8xl" style={{ color: '#2a2a2a' }}>404</span>
    <p className="text-sm font-mono" style={{ color: '#9a9a9a' }}>
      This route does not exist in the system.
    </p>
    <a
      href="/"
      className="btn-titan px-8 py-3"
    >
      Return Home
    </a>
  </div>
);

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) { 
    super(props); 
    this.state = { error: null }; 
  }
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ backgroundColor: '#141313', color: '#ff6b6b', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '1rem', fontFamily: 'monospace' }}>
          <h2>Something went wrong</h2>
          <pre style={{ color: '#999', fontSize: '0.8rem', maxWidth: '80vw', overflow: 'auto' }}>{this.state.error.message}</pre>
          <button onClick={() => window.location.href = '/'} style={{ color: '#4edea3', border: '1px solid #4edea3', padding: '8px 24px', borderRadius: '8px', background: 'none', cursor: 'pointer' }}>Go Home</button>
        </div>
      );
    }
    return this.props.children;
  }
}

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div
      className="min-h-screen flex flex-col relative"
      style={{ backgroundColor: 'var(--surface)', color: 'var(--on-surface)' }}
    >
      <div className="fixed inset-0 bg-noise z-10 pointer-events-none" />
      <Navbar />
      <main className="flex-grow relative transition-all duration-500">
        {children}
      </main>
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
            {/* ── Public ─────────────────────────────────────────────── */}
            <Route path={ROUTES.LOGIN} element={<PublicRoute><LoginPage /></PublicRoute>} />
            <Route path={ROUTES.SIGNUP} element={<PublicRoute><SignupPage /></PublicRoute>} />
            <Route path={ROUTES.HOME}      element={<Home />} />
            <Route path={ROUTES.ABOUT} element={<About />} />
            <Route path={ROUTES.DOCS}  element={<Documentation />} />
            <Route path={ROUTES.DASHBOARD} element={<ProtectedRoute><GST /></ProtectedRoute>} />

            {/* ── Protected Routes ────────────────────────────────────── */}
            <Route path={ROUTES.GST.ROOT} element={
              <ProtectedRoute>
                <LawDashboard
                  title="GST Intelligence Hub"
                  domainId="gst"
                  contextDesc="tax scenario"
                  definition="A comprehensive indirect tax charged on the supply of goods and services. It replaced multiple cascading taxes."
                  implDate="July 1, 2017"
                />
              </ProtectedRoute>
            } />
            <Route path={ROUTES.GST.TEMPLATES} element={<ProtectedRoute><GstTemplates /></ProtectedRoute>} />
            <Route path={ROUTES.RESPONSES} element={<ProtectedRoute><GstTemplates /></ProtectedRoute>} />
            <Route path={ROUTES.GST.CUSTOMIZE} element={<ProtectedRoute><TemplateCustomization /></ProtectedRoute>} />

            <Route path={ROUTES.INCOME_TAX} element={
              <ProtectedRoute>
                <LawDashboard
                  title="Income Tax Advisory"
                  domainId="income-tax"
                  contextDesc="income tax query"
                  definition="A direct tax levied on the income or profits of individuals and entities. Governed by the Income Tax Act, 1961."
                  implDate="April 1, 1962"
                />
              </ProtectedRoute>
            } />

            <Route path={ROUTES.FEMA} element={
              <ProtectedRoute>
                <LawDashboard
                  title="FEMA Expert System"
                  domainId="fema"
                  contextDesc="foreign exchange scenario"
                  definition="The Foreign Exchange Management Act (FEMA) is an Act of the Parliament of India to consolidate and amend the law relating to foreign exchange."
                  implDate="June 1, 2000"
                />
              </ProtectedRoute>
            } />

            <Route path={ROUTES.COMPANY_LAW} element={
              <ProtectedRoute>
                <LawDashboard
                  title="Company Law Compliance"
                  domainId="company-law"
                  contextDesc="regulatory query"
                  definition="The legislation that governs the incorporation, responsibilities, and dissolution of companies in India."
                  implDate="April 1, 2014"
                />
              </ProtectedRoute>
            } />

            {/* ── Admin ──────────────────────────────────────────────── */}
            <Route path={ROUTES.ADMIN.TEMPLATES} element={<ProtectedRoute><AdminTemplateDashboard /></ProtectedRoute>} />
            <Route path={ROUTES.ADMIN.UPLOAD} element={<ProtectedRoute><AdminUploadPortal /></ProtectedRoute>} />

            {/* ── 404 catch-all ──────────────────────────────────────── */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Layout>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
