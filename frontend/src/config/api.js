/**
 * Centralized API configuration.
 * Import this instead of hardcoding URLs in components.
 */
export const BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD
  ? '/api_proxy'
  : 'http://localhost:8000');
