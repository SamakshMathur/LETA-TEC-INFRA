import typography from '@tailwindcss/typography';

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Core brand ──────────────────────────────────────────────────────
        primary:       '#4edea3',
        'primary-hover': '#3bc98f',
        surface:       '#0e0e0e',
        'surface-bright': '#1a1a1a',

        // ── leta.* namespace (used by linter-generated code) ────────────────
        leta: {
          black:   '#0a0a0a',
          white:   '#e5e2e1',        // off-white for text, NOT page background
          primary: '#4edea3',        // green — the real brand colour
          gold:    '#C9A54C',

          gray: {
            50:  '#1a1a1a',
            100: '#242424',
            200: '#2e2e2e',
            500: '#9a9a9a',
            700: '#c0bdb9',
            900: '#e5e2e1',
          },

          success: '#16A34A',
          warning: '#F59E0B',
          error:   '#DC2626',
        },
      },

      fontFamily: {
        display: ['Syne', 'Inter', 'sans-serif'],
        heading: ['Syne', 'Inter', 'sans-serif'],
        body:    ['Inter', 'sans-serif'],
        mono:    ['JetBrains Mono', 'monospace'],
      },

      fontSize: {
        h1:      ['56px', { lineHeight: '1.2'  }],
        h2:      ['42px', { lineHeight: '1.25' }],
        h3:      ['32px', { lineHeight: '1.3'  }],
        bodyLg:  ['20px', { lineHeight: '1.5'  }],
        body:    ['16px', { lineHeight: '1.5'  }],
        caption: ['14px', { lineHeight: '1.4'  }],
        mono:    ['14px', { lineHeight: '1.5'  }],
      },

      borderRadius: {
        leta: '12px',
      },

      boxShadow: {
        leta:     '0 1px 2px rgba(0,0,0,0.4)',
        elevated: '0 25px 50px -12px rgba(0,0,0,0.8)',
      },
    },
  },
  plugins: [typography],
};
