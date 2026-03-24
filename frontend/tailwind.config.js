/* eslint-env node */
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Sovereign Intelligence — Obsidian Spectrum ─────────────────
        // Surfaces
        'surface':                   '#141313',
        'surface-dim':               '#141313',
        'surface-container-lowest':  '#0e0e0e',
        'surface-container-low':     '#1a1a1a',
        'surface-container':         '#1e1e1e',
        'surface-container-high':    '#2a2a2a',
        'surface-container-highest': '#333333',
        'surface-bright':            '#363636',
        'surface-variant':           '#2a2a2a',

        // Primary — Emerald Glow
        'primary':              '#4edea3',
        'primary-container':    '#10b981',
        'on-primary':           '#0e0e0e',
        'on-primary-container': '#e5e2e1',

        // Secondary — Glacial Cyan
        'secondary':           '#d3fbff',
        'secondary-container': '#00eefc',
        'on-secondary':        '#0e0e0e',

        // Tertiary — Legal Gold
        'tertiary':           '#e9c400',
        'tertiary-container': '#bfa100',
        'on-tertiary':        '#0e0e0e',

        // On-surface
        'on-surface':         '#e5e2e1',
        'on-surface-variant': '#9a9a9a',

        // Outlines (ghost borders only)
        'outline':         'rgba(229,226,225,0.3)',
        'outline-variant': 'rgba(229,226,225,0.15)',

        // ── Legacy aliases (backward compat) ──────────────────────────
        'sentinel-blue':  '#003B59',
        'sentinel-green': '#10b981',
        'sentinel-dark':  '#141313',
        'sentinel-card':  '#1e1e1e',
        'cinema-gold':    '#e9c400',
        'cyber-cyan':     '#00eefc',
      },

      backgroundImage: {
        'brand-gradient':   'linear-gradient(135deg, #4edea3 0%, #10b981 100%)',
        'spotlight-radial': 'radial-gradient(circle at center, rgba(78,222,163,0.12) 0%, rgba(20,19,19,0) 70%)',
        'gold-glow':        'radial-gradient(circle at center, rgba(233,196,0,0.08) 0%, rgba(20,19,19,0) 60%)',
        'glass-border':     'linear-gradient(135deg, rgba(78,222,163,0.15) 0%, rgba(0,238,252,0.15) 100%)',
      },

      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Orbitron"', 'sans-serif'],
        mono:    ['"Space Grotesk"', 'monospace'],
        brand:   ['"Orbitron"', 'sans-serif'],
        pixel:   ['"Silkscreen"', '"Press Start 2P"', 'monospace'],
      },

      fontSize: {
        'display-lg': ['3.5rem',    { lineHeight: '1',    letterSpacing: '-0.02em' }],
        'display-md': ['2.5rem',    { lineHeight: '1.05', letterSpacing: '-0.02em' }],
        'title-lg':   ['1.375rem',  { lineHeight: '1.3',  letterSpacing: '-0.01em' }],
        'title-md':   ['1.125rem',  { lineHeight: '1.4',  fontWeight: '500' }],
        'body-lg':    ['1rem',      { lineHeight: '1.6' }],
        'body-md':    ['0.875rem',  { lineHeight: '1.6' }],
        'body-sm':    ['0.75rem',   { lineHeight: '1.5' }],
        'label-lg':   ['0.875rem',  { lineHeight: '1.4',  fontWeight: '600' }],
        'label-md':   ['0.75rem',   { lineHeight: '1.4',  fontWeight: '600' }],
        'label-sm':   ['0.6875rem', { lineHeight: '1.3',  fontWeight: '700', letterSpacing: '0.05em' }],
      },

      boxShadow: {
        'glow-primary':    '0 0 20px rgba(78,222,163,0.25), 0 0 40px rgba(78,222,163,0.10)',
        'glow-primary-lg': '0 0 40px rgba(78,222,163,0.35), 0 0 80px rgba(78,222,163,0.15)',
        'glow-cyan':       '0 20px 40px rgba(0,238,252,0.05)',
        'glow-gold':       '0 0 20px rgba(233,196,0,0.20)',
        'ambient-float':   '0 20px 60px rgba(0,0,0,0.60), 0 4px 16px rgba(0,0,0,0.40)',
        'ambient-card':    '0 8px 32px rgba(0,0,0,0.40)',
      },

      spacing: {
        '2.5': '0.5rem',
        '4.5': '1.125rem',
        '18':  '4.5rem',
      },

      animation: {
        'ping-slow':  'ping 3s cubic-bezier(0,0,0.2,1) infinite',
        'pulse-slow': 'pulse 4s ease-in-out infinite',
        'shimmer':    'shimmer 2.5s linear infinite',
      },

      keyframes: {
        shimmer: {
          '0%':   { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition:  '200% center' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};
