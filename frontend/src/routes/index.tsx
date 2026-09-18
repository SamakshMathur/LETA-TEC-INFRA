import React from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { ROUTES, LIVE_MODULE_IDS } from '../constants/routes';
import { lazyWithRetry } from '../utils/lazyWithRetry';

// Every page is lazy-loaded — its JS chunk downloads only when the route is
// first visited, not on initial app load. Combined with manualChunks in
// vite.config.ts this drops the initial bundle from ~5 MB to ~300 KB.
// lazyWithRetry (not React's lazy() directly) so a stale chunk reference
// after a deploy — "Failed to fetch dynamically imported module" — recovers
// with one automatic reload instead of dead-ending on the error screen.
const Home                  = lazyWithRetry(() => import('../pages/Home'));
const About                 = lazyWithRetry(() => import('../pages/About'));
const Documentation         = lazyWithRetry(() => import('../pages/Documentation'));
const GST                   = lazyWithRetry(() => import('../pages/GST'));
const TemplateCustomization = lazyWithRetry(() => import('../pages/TemplateCustomization'));
const AdminTemplateDashboard= lazyWithRetry(() => import('../pages/AdminTemplateDashboard'));
const AdminUploadPortal     = lazyWithRetry(() => import('../pages/AdminUploadPortal'));
const SignupPage             = lazyWithRetry(() => import('../pages/auth/signup'));
const LetaWorkspace         = lazyWithRetry(() => import('../pages/LetaWorkspace'));
const ModuleDashboard       = lazyWithRetry(() => import('../pages/ModuleDashboard'));
const LegalPolicies         = lazyWithRetry(() => import('../pages/LegalPolicies'));
const MyDocs                = lazyWithRetry(() => import('../pages/MyDocs'));
const Payment               = lazyWithRetry(() => import('../pages/Payment'));
const Settings               = lazyWithRetry(() => import('../pages/Settings'));
const InvoiceHistory        = lazyWithRetry(() => import('../pages/InvoiceHistory'));
const DocumentLibraryPage   = lazyWithRetry(() => import('../pages/DocumentLibraryPage'));
const LoginPage             = lazyWithRetry(() => import('../pages/auth/login'));

// LawDashboard is a presentational component used with inline props —
// lazy-load it so the dashboard chunk doesn't bloat the router chunk.
const LawDashboard = lazyWithRetry(() =>
  import('../components/dashboard').then(m => ({ default: m.LawDashboard }))
);

// Gates a module's pages behind LIVE_MODULE_IDS. The dashboard cards already
// disable their own onClick for non-live modules, but that only blocks the
// card — the routes themselves (the shared /:domainId/leta chat workspace,
// and each module's own dedicated info-page route below) are otherwise
// reachable by anyone who types or links the URL directly. This is the
// route-level counterpart to that: redirects straight back to /dashboard
// instead of ever mounting the page for a module that isn't live yet.
//
// `domainId` is optional: the shared /:domainId/leta route omits it (reads
// the real value from the URL param instead); the fixed per-module info-page
// routes below pass their own domainId explicitly since it isn't a URL param
// there.
const LiveDomainGuard: React.FC<{ domainId?: string; children: React.ReactNode }> = ({ domainId: fixedDomainId, children }) => {
  const params = useParams<{ domainId: string }>();
  const domainId = fixedDomainId ?? params.domainId ?? 'gst';
  if (!LIVE_MODULE_IDS.includes(domainId)) {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }
  return <>{children}</>;
};

export interface RouteConfig {
  path: string;
  element: React.ReactNode;
}

/** No auth check — anyone can visit regardless of login state */
export const openRoutes: RouteConfig[] = [
  { path: ROUTES.HOME,  element: <Home /> },
  { path: ROUTES.ABOUT, element: <About /> },
  { path: ROUTES.DOCS,  element: <Documentation /> },
];

/** Redirect to /dashboard if already logged in */
export const authRoutes: RouteConfig[] = [
  { path: ROUTES.LOGIN,  element: <LoginPage /> },
  { path: ROUTES.SIGNUP, element: <SignupPage /> },
];

/** Require login — redirect to /login if not authenticated */
export const protectedRoutes: RouteConfig[] = [
  { path: ROUTES.DASHBOARD,   element: <ModuleDashboard /> },
  // ONE route with a trailing splat, not two sibling Route entries for
  // "/:domainId/leta" vs "/:domainId/leta/:sessionId" (that was the
  // original shape here and it was wrong — two different Route matches
  // for the same element still count as two different routes to React
  // Router, so it fully unmounted/remounted LetaWorkspace on every
  // navigation between them: header flashing/double-painting mid-transition,
  // and worse, "New Consultation" resetting state and then immediately
  // remounting straight back into the mount effect, which re-reads
  // sessionStorage's last-active-session and silently restores the old
  // chat. A trailing "/*" keeps this ONE continuously-matched route —
  // "/gst/leta" and "/gst/leta/<id>" both match it, the id just arrives
  // as a param that changes without a remount, exactly like any other
  // in-route param transition.
  { path: '/:domainId/leta/*', element: <LiveDomainGuard><LetaWorkspace /></LiveDomainGuard> },

  {
    path: ROUTES.GST.ROOT,
    element: (
      <LawDashboard
        title="GST Intelligence Hub"
        domainId="gst"
        contextDesc="tax scenario"
        definition="A comprehensive indirect tax charged on the supply of goods and services. It replaced multiple cascading taxes."
        implDate="July 1, 2017"
      />
    ),
  },
  { path: ROUTES.GST.CUSTOMIZE, element: <TemplateCustomization /> },

  {
    path: ROUTES.INCOME_TAX,
    element: (
      <LiveDomainGuard domainId="income-tax">
        <LawDashboard
          title="Income Tax Advisory"
          domainId="income-tax"
          contextDesc="income tax query"
          definition="A direct tax levied on the income or profits of individuals and entities. Governed by the Income Tax Act, 1961."
          implDate="April 1, 1962"
        />
      </LiveDomainGuard>
    ),
  },
  {
    path: ROUTES.FEMA,
    element: (
      <LiveDomainGuard domainId="fema">
        <LawDashboard
          title="FEMA Expert System"
          domainId="fema"
          contextDesc="foreign exchange scenario"
          definition="The Foreign Exchange Management Act (FEMA) is an Act of the Parliament of India to consolidate and amend the law relating to foreign exchange."
          implDate="June 1, 2000"
        />
      </LiveDomainGuard>
    ),
  },
  {
    path: ROUTES.COMPANY_LAW,
    element: (
      <LiveDomainGuard domainId="company-law">
        <LawDashboard
          title="Company Law Compliance"
          domainId="company-law"
          contextDesc="regulatory query"
          definition="The legislation that governs the incorporation, responsibilities, and dissolution of companies in India."
          implDate="April 1, 2014"
        />
      </LiveDomainGuard>
    ),
  },

  { path: ROUTES.ADMIN.TEMPLATES, element: <AdminTemplateDashboard /> },
  { path: ROUTES.ADMIN.UPLOAD,    element: <AdminUploadPortal /> },

  { path: ROUTES.LEGAL,   element: <LegalPolicies /> },
  { path: ROUTES.MY_DOCS, element: <MyDocs /> },
  { path: ROUTES.PAYMENT, element: <Payment /> },
  { path: ROUTES.SETTINGS, element: <Settings /> },
  { path: ROUTES.INVOICES, element: <InvoiceHistory /> },
  { path: ROUTES.DOCUMENT_LIBRARY, element: <DocumentLibraryPage /> },
];
