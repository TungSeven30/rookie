import type { Config } from 'tailwindcss'

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary - Confident Amber/Gold (Rookie brand)
        primary: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',  // Main accent
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
          950: '#451a03',
        },
        // Warm neutrals (stone palette)
        surface: {
          50: '#fafaf9',   // Page background
          100: '#f5f5f4',  // Alternate surfaces
          200: '#e7e5e4',  // Borders
          300: '#d6d3d1',
          400: '#a8a29e',
          500: '#78716c',  // Muted text
          600: '#57534e',
          700: '#44403c',
          800: '#292524',
          900: '#1c1917',  // Primary text
          950: '#0c0a09',
        },
      },
      fontFamily: {
        display: ['DM Sans', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
