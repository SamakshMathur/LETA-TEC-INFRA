export const BASE_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.PROD
    ? '/api_proxy'
    : 'http://localhost:8000');
