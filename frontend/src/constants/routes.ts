export const ROUTES = {
  HOME: '/',
  ABOUT: '/about',
  DOCS: '/docs',
  LOGIN: '/login',
  SIGNUP: '/signup',
  DASHBOARD: '/dashboard',
  GST: {
    ROOT: '/gst',
    TEMPLATES: '/gst/templates',
    CUSTOMIZE: '/gst/templates/:id/customize',
    LETA: '/gst/letatec',
  },
  INCOME_TAX: '/income-tax',
  INCOME_TAX_LETA: '/income-tax/letatec',
  FEMA: '/fema',
  FEMA_LETA: '/fema/letatec',
  COMPANY_LAW: '/company-law',
  COMPANY_LAW_LETA: '/company-law/letatec',
  ADMIN: {
    TEMPLATES: '/admin/templates',
    UPLOAD: '/admin/upload',
  },
  RESPONSES: '/responses',
  LEGAL: '/legal',
  MY_DOCS: '/my-docs',
  PAYMENT: '/payment',
  SETTINGS: '/settings',
  INVOICES: '/invoices',
};

// Which domainIds are actually reachable right now. The dashboard's module
// cards (ModuleDashboard.tsx) already disable their own click for anything
// not in here — this is the routing-level counterpart: LiveDomainGuard
// (routes/index.tsx) redirects a direct URL visit to a non-live module's
// pages back to /dashboard instead of rendering them. Add a domainId here
// (and flip its `status` to 'LIVE' in ModuleDashboard.tsx's MODULES array)
// when that module actually launches.
export const LIVE_MODULE_IDS = ['gst'];
