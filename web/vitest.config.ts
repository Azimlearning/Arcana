import { defineConfig } from 'vitest/config';
import { resolve } from 'node:path';

export default defineConfig({
  resolve: {
    alias: {
      '@': resolve(__dirname, '.'),
    },
  },
  test: {
    // TODO(P1): flip `environment` to 'jsdom' and widen `include` to
    // `*.test.{ts,tsx}` when React-component DOM tests land. The slice
    // ships logic-only tests (stream parser, registry presence).
    environment: 'node',
    include: ['**/*.test.ts'],
  },
});
