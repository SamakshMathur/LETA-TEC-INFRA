import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Separate from vite.config.ts on purpose: this only configures the
// test runner (jsdom env, RTL) and must never affect the production
// build config/plugins/rollupOptions used by `npm run build`.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
  },
});
