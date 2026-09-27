/** @type {import('tailwindcss').Config} */
module.exports = {
  // Class-based dark mode toggling ('dark' class on <html>)
  darkMode: "class",

  // Template and script paths scanned for CSS class generation
  content: ["./src/templates/**/*.html", "./src/static/js/**/*.js"],

  theme: {
    extend: {
      colors: {
        // Brand color palette (Primary Blue and Warm Amber accent)
        brand: {
          DEFAULT: "#2563eb",
          hover: "#1d4ed8",
          light: "#eff6ff",
        },
        accent: {
          DEFAULT: "#f59e0b",
          hover: "#d97706",
          light: "#fef3c7",
        },
      },

      fontFamily: {
        // Primary UI font and monospace font for short codes
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
    },
  },

  plugins: [],
};
