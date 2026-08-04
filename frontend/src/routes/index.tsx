import React, { lazy } from 'react';
import { ROUTES } from '../constants/routes';

// Every page is lazy-loaded — its JS chunk downloads only when the route is
// first visited, not on initial app load. Combined with manualChunks in
// vite.config.ts this drops the initial bundle from ~5 MB to ~300 KB.
const Home                  = lazy(() => import('../pages/Home'));
const About                 = lazy(() => import('../pages/About'));
const Documentation         = lazy(() => import('../pages/Documentation'));
const GST                   = lazy(() => import('../pages/GST'));
const TemplateCustomization = lazy(() => import('../pages/TemplateCustomization'));
const AdminTemplateDashboard= lazy(() => import('../pages/AdminTemplateDashboard'));
const AdminUploadPortal     = lazy(() => import('../pages/AdminUploadPortal'));
const SignupPage             = lazy(() => import('../pages/auth/signup'));
const LetaWorkspace         = lazy(() => import('../pages/LetaWorkspace'));
const ModuleDashboard       = lazy(() => import('../pages/ModuleDashboard'));
const LegalPolicies         = lazy(() => import('../pages/LegalPolicies'));
const MyDocs                = lazy(() => import('../pages/MyDocs'));
const Payment               = lazy(() => import('../pages/Payment'));
const LoginPage             = lazy(() => import('../pages/auth/login'));

// LawDashboard is a presentational component used with inline props —
// lazy-load it so the dashboard chunk doesn't bloat the router chunk.
const LawDashboard = lazy(() =>
  import('../components/dashboard').then(m => ({ default: m.LawDashboard }))
);

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
  { path: '/:domainId/leta',  element: <LetaWorkspace /> },

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
      <LawDashboard
        title="Income Tax Advisory"
        domainId="income-tax"
        contextDesc="income tax query"
        definition="A direct tax levied on the income or profits of individuals and entities. Governed by the Income Tax Act, 1961."
        implDate="April 1, 1962"
      />
    ),
  },
  {
    path: ROUTES.FEMA,
    element: (
      <LawDashboard
        title="FEMA Expert System"
        domainId="fema"
        contextDesc="foreign exchange scenario"
        definition="The Foreign Exchange Management Act (FEMA) is an Act of the Parliament of India to consolidate and amend the law relating to foreign exchange."
        implDate="June 1, 2000"
      />
    ),
  },
  {
    path: ROUTES.COMPANY_LAW,
    element: (
      <LawDashboard
        title="Company Law Compliance"
        domainId="company-law"
        contextDesc="regulatory query"
        definition="The legislation that governs the incorporation, responsibilities, and dissolution of companies in India."
        implDate="April 1, 2014"
      />
    ),
  },

  { path: ROUTES.ADMIN.TEMPLATES, element: <AdminTemplateDashboard /> },
  { path: ROUTES.ADMIN.UPLOAD,    element: <AdminUploadPortal /> },

  { path: ROUTES.LEGAL,   element: <LegalPolicies /> },
  { path: ROUTES.MY_DOCS, element: <MyDocs /> },
  { path: ROUTES.PAYMENT, element: <Payment /> },
];
