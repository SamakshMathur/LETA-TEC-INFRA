import typography from '@tailwindcss/typography';

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Titan Primary Palette ────────────────────────────────────────────
        'titan-primary':      '#7C3AED',
        'titan-primary-hover':'#8B5CF6',
        'titan-primary-soft': '#A78BFA',
        'titan-primary-dark': '#5B21B6',

        // ── Core aliases ─────────────────────────────────────────────────────
        primary:         '#7C3AED',
        'primary-hover': '#8B5CF6',
        secondary:       '#60A5FA',

        // ── Background system ────────────────────────────────────────────────
        'bg-main':      '#060816',
        'bg-secondary': '#0B1020',
        'bg-tertiary':  '#111827',
        surface:        '#060816',
        'surface-bright':'#0B1020',

        // ── Neutral palette ──────────────────────────────────────────────────
        gray: {
          50:  '#F8FAFC',
          100: '#E2E8F0',
          300: '#CBD5E1',
          500: '#94A3B8',
          700: '#475569',
          900: '#0F172A',
        },

        // ── leta.* namespace (dark surfaces use inverted scale) ───────────────
        leta: {
          black:     '#060816',
          white:     '#E2E8F0',
          primary:   '#7C3AED',
          secondary: '#60A5FA',
          gold:      '#C9A54C',

          gray: {
            50:  '#111827',
            100: '#1e2235',
            200: '#2a3050',
            500: '#475569',
            700: '#94A3B8',
            900: '#E2E8F0',
          },

          success: '#22C55E',
          warning: '#F59E0B',
          error:   '#EF4444',
        },
      },

      fontFamily: {
        display: ['Space Grotesk', 'Inter', 'sans-serif'],
        heading: ['Space Grotesk', 'Inter', 'sans-serif'],
        body:    ['Inter', 'sans-serif'],
        mono:    ['JetBrains Mono', 'monospace'],
      },

      fontSize: {
        'display-xl': ['72px', { lineHeight: '1.05' }],
        h1:      ['56px', { lineHeight: '1.1'  }],
        h2:      ['42px', { lineHeight: '1.2'  }],
        h3:      ['32px', { lineHeight: '1.3'  }],
        bodyLg:  ['20px', { lineHeight: '1.6'  }],
        body:    ['16px', { lineHeight: '1.6'  }],
        caption: ['14px', { lineHeight: '1.5'  }],
        mono:    ['13px', { lineHeight: '1.6'  }],
      },

      borderRadius: {
        leta: '12px',
      },

      boxShadow: {
        leta:       '0 1px 2px rgba(0,0,0,0.6)',
        elevated:   '0 25px 50px -12px rgba(0,0,0,0.9)',
        titan:      '0 0 20px rgba(124,58,237,0.35)',
        'titan-lg': '0 0 40px rgba(124,58,237,0.25)',
        'titan-xl': '0 0 60px rgba(124,58,237,0.2), 0 0 120px rgba(124,58,237,0.1)',
        glow:       '0 0 40px rgba(124,58,237,0.2), 0 0 80px rgba(96,165,250,0.1)',
      },

      backgroundImage: {
        'gradient-titan':  'linear-gradient(135deg, #7C3AED, #5B21B6)',
        'gradient-purple': 'linear-gradient(135deg, #7C3AED, #60A5FA)',
        'gradient-card':   'linear-gradient(135deg, rgba(124,58,237,0.08), rgba(96,165,250,0.04))',
        'gradient-page':   'linear-gradient(180deg, #060816 0%, #0B1020 100%)',
      },
    },
  },
  plugins: [typography],
};
