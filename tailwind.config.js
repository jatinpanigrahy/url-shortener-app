/** @type {import('tailwindcss').Config} */
module.exports = {
  // Class-based dark mode toggling ('dark' class on <html>)
  darkMode: "class",

  // Template and script paths scanned for CSS class generation
  content: ["./src/templates/**/*.html", "./src/static/js/**/*.js"],

  theme: {
    extend: {
      colors: {
        canvas: { base: 'var(--color-canvas-base)', elevated: 'var(--color-canvas-elevated)' },
        ink: { DEFAULT: 'var(--color-text-primary)', muted: 'var(--color-text-secondary)', inverse: 'var(--color-text-inverse)' },
        accent: { DEFAULT: 'var(--color-accent-primary)', hover: 'var(--color-accent-hover)', terracotta: 'var(--color-accent-terracotta)' }
      },
      fontFamily: { sans: ['var(--font-sans)'], mono: ['var(--font-mono)'] },
      boxShadow: { 'border-subtle': 'var(--shadow-border)', 'card-elevated': 'var(--shadow-card)', 'focus-ring': 'var(--shadow-focus)' }
    },
  },

  plugins: [],
};
