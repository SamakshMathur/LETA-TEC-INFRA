export const BASE_URL =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.PROD
    ? 'https://swmgzifq69.execute-api.ap-south-1.amazonaws.com'
    : 'http://localhost:8000');
