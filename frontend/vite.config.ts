import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
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
    sourcemap: false,
    minify: 'terser',
    chunkSizeWarningLimit: 900,
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
        passes: 2, // 3 passes triples build time for <1% size gain
      },
      format: { comments: false },
      mangle: { toplevel: true },
    },
    rollupOptions: {
      output: {
        manualChunks(id) {
          // ── Heavy 3D / WebGL — only used on landing page / 3D sections ──────
          if (
            id.includes('node_modules/three') ||
            id.includes('node_modules/@react-three') ||
            id.includes('node_modules/@splinetool') ||
            id.includes('node_modules/ogl/')
          ) return 'vendor-3d';

          // ── PDF viewer — only opened when user clicks a document ─────────────
          if (
            id.includes('node_modules/pdfjs-dist') ||
            id.includes('node_modules/@react-pdf-viewer')
          ) return 'vendor-pdf';

          // ── Charts — only dashboard pages ────────────────────────────────────
          if (
            id.includes('node_modules/recharts') ||
            id.includes('node_modules/d3-') ||
            id.includes('node_modules/victory-')
          ) return 'vendor-charts';

          // ── DOCX parser — only file-upload path ──────────────────────────────
          if (id.includes('node_modules/mammoth')) return 'vendor-mammoth';

          // ── Animation — shared across many pages ─────────────────────────────
          if (id.includes('node_modules/framer-motion')) return 'vendor-framer';

          // ── Markdown + unified AST pipeline ──────────────────────────────────
          if (
            id.includes('node_modules/react-markdown') ||
            id.includes('node_modules/remark') ||
            id.includes('node_modules/micromark') ||
            id.includes('node_modules/mdast') ||
            id.includes('node_modules/unist') ||
            id.includes('node_modules/vfile') ||
            id.includes('node_modules/hast')
          ) return 'vendor-markdown';

          // ── React core — highly stable, maximises CDN cache lifetime ─────────
          if (
            id.includes('node_modules/react/') ||
            id.includes('node_modules/react-dom/') ||
            id.includes('node_modules/scheduler/')
          ) return 'vendor-react';

          // ── Router ───────────────────────────────────────────────────────────
          if (
            id.includes('node_modules/react-router-dom') ||
            id.includes('node_modules/react-router/')
          ) return 'vendor-router';

          // ── Query / data fetching ─────────────────────────────────────────────
          if (id.includes('node_modules/@tanstack')) return 'vendor-query';

          // ── Icons — large but stable ──────────────────────────────────────────
          if (id.includes('node_modules/lucide-react')) return 'vendor-icons';

          // ── Axios ─────────────────────────────────────────────────────────────
          if (id.includes('node_modules/axios')) return 'vendor-axios';
        },
      },
    },
  },
});
