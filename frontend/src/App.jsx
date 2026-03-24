import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

// Layout
import { Navbar, SystemFooter, ScrollToTop } from './components/layout';

// Dashboard
import { LawDashboard } from './components/dashboard';

// Pages
import {
  Home, About, Documentation, Login,
  GstTemplates, TemplateCustomization,
  AdminTemplateDashboard, AdminUploadPortal,
} from './pages';

// Context
import { AuthProvider, useAuth } from './context/AuthContext';

const ProtectedRoute = ({ children, adminOnly = false }) => {
  const { user, isAdmin, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center min-h-screen"
        style={{ backgroundColor: 'var(--surface)' }}
      >
        <span
          className="text-sm font-mono animate-pulse"
          style={{ color: '#4edea3' }}
        >
          Verifying credentials...
        </span>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />;
  return children;
};

const NotFound = () => (
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

const Layout = ({ children }) => {
  const { isAdmin } = useAuth();

  return (
    <div
      className="min-h-screen flex flex-col relative"
      style={{ backgroundColor: 'var(--surface)', color: 'var(--on-surface)' }}
    >
      {/* Noise texture overlay — z-10, pointer-events-none */}
      <div className="fixed inset-0 bg-noise z-10 pointer-events-none" />

      <Navbar />

      <main className="flex-grow relative z-20 transition-all duration-500">
        {children}
      </main>

      <SystemFooter />

      {isAdmin && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-6 py-2 rounded-full text-xs font-bold tracking-[0.2em] uppercase"
          style={{
            backgroundColor: 'rgba(78,222,163,0.08)',
            color: '#4edea3',
            boxShadow: 'inset 0 0 0 1px rgba(78,222,163,0.25), 0 0 20px rgba(78,222,163,0.15)',
            backdropFilter: 'blur(16px)',
          }}
        >
          TITAN PORTAL ACTIVE
        </div>
      )}
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <ScrollToTop />
        <Layout>
          <Routes>
            {/* ── Public ─────────────────────────────────────────────── */}
            <Route path="/"      element={<Home />} />
            <Route path="/about" element={<About />} />
            <Route path="/docs"  element={<Documentation />} />
            <Route path="/login" element={<Login />} />

            {/* ── GST ────────────────────────────────────────────────── */}
            <Route path="/gst" element={
              <ProtectedRoute>
                <LawDashboard
                  title="GST Intelligence Hub"
                  domainId="gst"
                  contextDesc="tax scenario"
                  definition="A comprehensive indirect tax charged on the supply of goods and services. It replaced multiple cascading taxes levied by the central and state governments."
                  implDate="July 1, 2017"
                />
              </ProtectedRoute>
            } />
            <Route path="/gst/templates" element={
              <ProtectedRoute><GstTemplates /></ProtectedRoute>
            } />
            <Route path="/gst/templates/:id/customize" element={
              <ProtectedRoute><TemplateCustomization /></ProtectedRoute>
            } />

            {/* ── Income Tax ─────────────────────────────────────────── */}
            <Route path="/income-tax" element={
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

            {/* ── FEMA ───────────────────────────────────────────────── */}
            <Route path="/fema" element={
              <ProtectedRoute>
                <LawDashboard
                  title="FEMA Expert System"
                  domainId="fema"
                  contextDesc="foreign exchange scenario"
                  definition="An Act to consolidate and amend the law relating to foreign exchange with the objective of facilitating external trade and payments."
                  implDate="June 1, 2000"
                />
              </ProtectedRoute>
            } />

            {/* ── Company Law ────────────────────────────────────────── */}
            <Route path="/company-law" element={
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
            <Route path="/admin/templates" element={
              <ProtectedRoute adminOnly={true}><AdminTemplateDashboard /></ProtectedRoute>
            } />
            <Route path="/admin/upload" element={
              <ProtectedRoute adminOnly={true}><AdminUploadPortal /></ProtectedRoute>
            } />

            {/* ── 404 catch-all ──────────────────────────────────────── */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Layout>
      </Router>
    </AuthProvider>
  );
}

export default App;
