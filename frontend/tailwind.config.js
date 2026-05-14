import typography from '@tailwindcss/typography';

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Titan Primary Palette (Muted Professional Teal) ──────────────────
        'titan-primary':      '#4FB7C5',
        'titan-primary-hover':'#3EA6B4',
        'titan-primary-soft': 'rgba(79,183,197,0.12)',
        'titan-primary-dark': '#25707C',

        // ── Core aliases ─────────────────────────────────────────────────────
        primary:         '#4FB7C5',
        'primary-hover': '#3EA6B4',
        secondary:       '#6C7A99',

        // ── Background system (Premium Matte Dark Graphite) ──────────────────
        'bg-main':      '#070B11',
        'bg-secondary': '#0F1722',
        'bg-tertiary':  '#131D2B',
        'bg-hover':     '#182536',
        surface:        '#070B11',
        'surface-bright':'#0F1722',

        // ── Neutral palette (Sophisticated Slate-Zincs) ─────────────────────
        gray: {
          50:  '#F4F7FA',
          100: '#E4E4E7',
          300: '#A7B3C2',
          500: '#6C7A99',
          700: '#525D73',
          900: '#070B11',
        },

        // ── LETA Text Hierarchy ──────────────────────────────────────────────
        text: {
          'heading-primary':   '#F4F7FA',
          'heading-secondary': '#A7B3C2',
          'body-primary':      '#A7B3C2',
          'body-secondary':    '#6C7A99',
          'meta':              '#525D73',
          'disabled':          '#525D73',
          'accent':            '#4FB7C5',
        },

        // ── leta.* namespace (dark surfaces use inverted scale) ───────────────
        leta: {
          black:     '#070B11',
          white:     '#F4F7FA',
          primary:   '#4FB7C5',
          secondary: '#6C7A99',
          gold:      '#C9A54C',

          gray: {
            50:  '#0F1722',
            100: '#131D2B',
            200: '#182536',
            500: '#525D73',
            700: '#A7B3C2',
            900: '#F4F7FA',
          },

          success: '#22C55E',
          warning: '#F59E0B',
          error:   '#EF4444',
        },
      },

      fontFamily: {
        display: ['Inter Tight', 'Inter', 'sans-serif'],
        heading: ['Inter Tight', 'Inter', 'sans-serif'],
        body:    ['Inter', 'sans-serif'],
        mono:    ['IBM Plex Mono', 'monospace'],
      },

      fontSize: {
        'display-xl': ['72px', { lineHeight: '0.95', letterSpacing: '-0.04em' }],
        h1:      ['48px', { lineHeight: '1.05'  }],
        h2:      ['32px', { lineHeight: '1.2'  }],
        h3:      ['24px', { lineHeight: '1.3'  }],
        bodyLg:  ['18px', { lineHeight: '1.7'  }],
        body:    ['15px', { lineHeight: '1.6'  }],
        caption: ['13px', { lineHeight: '1.5'  }],
        mono:    ['12px', { lineHeight: '1.6'  }],
      },

      spacing: {
        'leta-xs': '4px',
        'leta-sm': '8px',
        'leta-md': '16px',
        'leta-lg': '24px',
        'leta-xl': '40px',
        'leta-2xl': '64px',
        'leta-3xl': '96px',
        'leta-4xl': '140px',
      },

      borderRadius: {
        leta: '28px',
      },

      boxShadow: {
        leta:       '0 4px 20px rgba(0,0,0,0.18)',
        elevated:   '0 30px 60px -15px rgba(0,0,0,0.9)',
        titan:      '0 4px 12px rgba(0,0,0,0.15)',
        'titan-lg': '0 8px 24px rgba(0,0,0,0.18)',
        'titan-xl': '0 12px 32px rgba(0,0,0,0.2)',
        glow:       'none',
      },

      backgroundImage: {
        'gradient-titan':  'linear-gradient(135deg, #4FB7C5, #131D2B)',
        'gradient-purple': 'linear-gradient(135deg, #4FB7C5, #131D2B)',
        'gradient-card':   'linear-gradient(135deg, rgba(79,183,197,0.02), rgba(108,122,153,0.01))',
        'gradient-page':   'none',
      },
    },
  },
  plugins: [typography],
};
