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
        fox: {
          50: "#fff1e7",
          100: "#ffe1c2",
          300: "#ffb27a",
          400: "#ff9f5a",
          500: "#e54a00",
          600: "#d43f00",
          700: "#bf3800",
          text: "#c2410c",
        },
        accent: {
          400: "#5ea8ff",
          500: "#3b8dff",
          600: "#2a6fe0",
        },
      },
      boxShadow: {
        card: "0 6px 22px rgba(20, 30, 60, 0.07)",
        glow: "0 10px 26px rgba(229, 74, 0, 0.32)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
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
