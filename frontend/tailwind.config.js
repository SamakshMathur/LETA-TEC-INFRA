import typography from '@tailwindcss/typography';

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        leta: {
          black: "#0A0A0A",
          white: "#FFFFFF",

          primary: "#4F46E5",   // Indigo (AI Identity)
          gold: "#C9A54C",      // Legal Premium

          gray: {
            50: "#F9FAFB",
            100: "#F3F4F6",
            200: "#E5E7EB",
            500: "#6B7280",
            700: "#374151",
            900: "#111827",
          },

          success: "#16A34A",
          warning: "#F59E0B",
          error: "#DC2626",
        },
      },

      fontFamily: {
        heading: ["Manrope", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },

      fontSize: {
        h1: ["56px", { lineHeight: "1.2" }],
        h2: ["42px", { lineHeight: "1.25" }],
        h3: ["32px", { lineHeight: "1.3" }],
        bodyLg: ["20px", { lineHeight: "1.5" }],
        body: ["16px", { lineHeight: "1.5" }],
        caption: ["14px", { lineHeight: "1.4" }],
        mono: ["14px", { lineHeight: "1.5" }],
      },

      borderRadius: {
        leta: "12px",
      },

      boxShadow: {
        leta: "0 1px 2px rgba(0,0,0,0.05)",
      },
    },
  },
  plugins: [
    typography,
  ],
};
