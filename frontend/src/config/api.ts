export const BASE_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.PROD
    ? 'https://api.letatec.com'   // production canonical — never use /api_proxy (no proxy exists on Amplify)
    : 'http://localhost:8000');
