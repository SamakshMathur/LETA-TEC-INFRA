// Single source of truth for the support contact address — was duplicated
// as a local const in LegalPolicies.tsx with no shared source, which is
// exactly how two copies quietly go out of sync if this address ever
// changes. Payment.tsx needs the same address for its own support links.
export const CONTACT_EMAIL = 'contact@letatec.com';
