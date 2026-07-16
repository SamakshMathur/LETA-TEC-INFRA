export const BASE_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.PROD
    ? 'https://api.letatec.com'
    : 'http://localhost:8000');
