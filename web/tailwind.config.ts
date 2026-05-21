// Design tokens mirror docs/uiux_plan.md §2. CSS custom properties live
// in app/globals.css; this config binds them to Tailwind utilities
// (so `bg-paper`, `text-ink-soft`, etc. are real classes).

import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: 'var(--paper)',
        card: 'var(--card)',
        ink: {
          DEFAULT: 'var(--ink)',
          soft: 'var(--ink-soft)',
          softer: 'var(--ink-softer)',
        },
        line: 'var(--line)',
        accent: 'var(--accent)',
        green: { DEFAULT: 'var(--green)', bg: 'var(--green-bg)' },
        amber: { DEFAULT: 'var(--amber)', bg: 'var(--amber-bg)' },
        red:   { DEFAULT: 'var(--red)',   bg: 'var(--red-bg)' },
        violet:{ DEFAULT: 'var(--violet)',bg: 'var(--violet-bg)' },
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        serif: ['var(--font-serif)', 'Georgia', 'serif'],
        display: ['var(--font-display)', 'Georgia', 'serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        ctl: '6px',
        card: '10px',
        panel: '14px',
      },
      boxShadow: {
        sm: '0 1px 0 var(--line)',
        DEFAULT: '0 1px 2px rgba(35, 33, 28, 0.06), 0 0 0 1px var(--line)',
        pop: '0 8px 24px rgba(35, 33, 28, 0.12)',
      },
    },
  },
  plugins: [],
};

export default config;
