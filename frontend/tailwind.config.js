/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        signal: {
          red:    '#EF4444',
          yellow: '#F59E0B',
          green:  '#22C55E',
        },
        surface: {
          DEFAULT: '#0F1117',
          card:    '#1A1D27',
          border:  '#2A2D3A',
        },
        accent: {
          DEFAULT: '#3B82F6',
          dim:     '#1D4ED8',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        pulse_slow: 'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        blink:      'blink 1s step-end infinite',
      },
      keyframes: {
        blink: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0 } },
      },
    },
  },
  plugins: [],
}
