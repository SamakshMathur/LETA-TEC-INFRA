import { LawDashboard } from '../components/dashboard';
import {
  Home, About, Documentation,
  GST, GstTemplates, TemplateCustomization,
  AdminTemplateDashboard, AdminUploadPortal,
  SignupPage, LetaWorkspace, ModuleDashboard,
} from '../pages';
import LoginPage from '../pages/auth/login';
import { ROUTES } from '../constants/routes';

export interface RouteConfig {
  path: string;
  element: React.ReactNode;
}

/** Redirect to /dashboard if already logged in */
export const authRoutes: RouteConfig[] = [
  { path: ROUTES.LOGIN,  element: <LoginPage /> },
  { path: ROUTES.SIGNUP, element: <SignupPage /> },
];

/** Require login — redirect to /login if not authenticated */
export const protectedRoutes: RouteConfig[] = [
  { path: ROUTES.HOME,  element: <Home /> },
  { path: ROUTES.ABOUT, element: <About /> },
  { path: ROUTES.DOCS,  element: <Documentation /> },

  { path: ROUTES.DASHBOARD, element: <ModuleDashboard /> },
  { path: '/:domainId/leta', element: <LetaWorkspace /> },

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
  { path: ROUTES.GST.TEMPLATES, element: <GstTemplates /> },
  { path: ROUTES.RESPONSES,     element: <GstTemplates /> },
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
];
