import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

// Layout
import { Navbar, SystemFooter, ScrollToTop } from './components/layout';

// Dashboard
import { LawDashboard } from './components/dashboard';

// Pages
import {
  Home, About, Documentation,
  GstTemplates, TemplateCustomization,
  AdminTemplateDashboard, AdminUploadPortal,
} from './pages';

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

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
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

const Layout = ({ children }) => {
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
            <Route path="/"      element={<Home />} />
            <Route path="/about" element={<About />} />
            <Route path="/docs"  element={<Documentation />} />

            {/* ── GST ────────────────────────────────────────────────── */}
            <Route path="/gst" element={
                <LawDashboard
                  title="GST Intelligence Hub"
                  domainId="gst"
                  contextDesc="tax scenario"
                  definition="A comprehensive indirect tax charged on the supply of goods and services. It replaced multiple cascading taxes levied by the central and state governments."
                  implDate="July 1, 2017"
                />
            } />
            <Route path="/gst/templates" element={<GstTemplates />} />
            <Route path="/gst/templates/:id/customize" element={<TemplateCustomization />} />

            {/* ── Income Tax ─────────────────────────────────────────── */}
            <Route path="/income-tax" element={
                <LawDashboard
                  title="Income Tax Advisory"
                  domainId="income-tax"
                  contextDesc="income tax query"
                  definition="A direct tax levied on the income or profits of individuals and entities. Governed by the Income Tax Act, 1961."
                  implDate="April 1, 1962"
                />
            } />

            {/* ── FEMA ───────────────────────────────────────────────── */}
            <Route path="/fema" element={
                <LawDashboard
                  title="FEMA Expert System"
                  domainId="fema"
                  contextDesc="foreign exchange scenario"
                  definition="An Act to consolidate and amend the law relating to foreign exchange with the objective of facilitating external trade and payments."
                  implDate="June 1, 2000"
                />
            } />

            {/* ── Company Law ────────────────────────────────────────── */}
            <Route path="/company-law" element={
                <LawDashboard
                  title="Company Law Compliance"
                  domainId="company-law"
                  contextDesc="regulatory query"
                  definition="The legislation that governs the incorporation, responsibilities, and dissolution of companies in India."
                  implDate="April 1, 2014"
                />
            } />

            {/* ── Admin ──────────────────────────────────────────────── */}
            <Route path="/admin/templates" element={<AdminTemplateDashboard />} />
            <Route path="/admin/upload" element={<AdminUploadPortal />} />

            {/* ── 404 catch-all ──────────────────────────────────────── */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Layout>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
