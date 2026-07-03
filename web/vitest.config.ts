import { defineConfig } from 'vitest/config';
import { resolve } from 'node:path';

export default defineConfig({
  resolve: {
    alias: {
      '@': resolve(__dirname, '.'),
    },
  },
  esbuild: {
    // tsconfig.json sets jsx:"preserve" (Next.js/SWC compiles JSX at build
    // time); Vitest's esbuild transform needs an explicit runtime instead.
    jsx: 'automatic',
  },
  test: {
    environment: 'jsdom',
    include: ['**/*.test.{ts,tsx}'],
    setupFiles: ['./vitest.setup.ts'],
  },
});
