/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // theme-aware surfaces (see :root / .dark in index.css)
        app: "var(--bg)",
        card: "var(--card)",
        soft: "var(--soft)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        line: "var(--line)",
        sidebar: "var(--sidebar)",
        tint: "var(--tint)",
        peach: "var(--peach)",
        fox: {
          50: "#fdeee6",
          100: "#fde0d0",
          300: "#f7a27c",
          400: "#f07a48",
          // 500 is the brand accent (icons, bars, large display text). White text on it is only 3.7:1, so
          // filled buttons use 600 (4.6:1, WCAG AA) and darken to 700 on hover; small orange text uses "text".
          500: "#e34a01",
          600: "#d14512",
          700: "#b83c0f",
          text: "#b83c0f",
        },
        accent: {
          400: "#5ea8ff",
          500: "#3b8dff",
          600: "#2a6fe0",
        },
      },
      boxShadow: {
        card: "var(--shadow-card)",
        "card-hover": "var(--shadow-card-hover)",
        glow: "var(--shadow-glow)",
      },
      borderRadius: {
        card: "var(--radius-card)",
        hero: "var(--radius-hero)",
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-sans)"],
      },
      animation: {
        "scan-line": "scanline 2.2s ease-in-out infinite",
        "fade-up": "fadeup 0.35s ease-out both",
      },
      keyframes: {
        scanline: {
          "0%": { transform: "translateY(0%)" },
          "50%": { transform: "translateY(100%)" },
          "100%": { transform: "translateY(0%)" },
        },
        fadeup: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
