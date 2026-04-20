import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { workflow } from 'workflow/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), workflow()],
  server: {
    proxy: {
      '/api_proxy': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api_proxy/, ''),
      },
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    sourcemap: false, // Prevent source code exposure
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,   // Remove console.log
        drop_debugger: true,  // Remove debugger statements
        passes: 3,            // Compress multiple times
      },
      format: {
        comments: false,      // Remove all comments
      },
      mangle: {
        toplevel: true,       // Mangle top-level variable and function names
      },
    },
  },
})
