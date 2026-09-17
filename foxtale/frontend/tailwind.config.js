/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          900: "#0b1224",
          800: "#111a33",
          700: "#1a2545",
        },
        fox: {
          400: "#ff9f5a",
          500: "#ff8a3d",
          600: "#f2721f",
        },
        accent: {
          400: "#5ea8ff",
          500: "#3b8dff",
          600: "#2a6fe0",
        },
      },
      boxShadow: {
        glass: "0 8px 32px 0 rgba(17, 26, 51, 0.12)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      animation: {
        "scan-line": "scanline 2.2s ease-in-out infinite",
        "pulse-slow": "pulse 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        scanline: {
          "0%": { transform: "translateY(0%)" },
          "50%": { transform: "translateY(100%)" },
          "100%": { transform: "translateY(0%)" },
        },
      },
    },
  },
  plugins: [],
};
