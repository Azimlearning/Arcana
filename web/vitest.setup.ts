import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
import '@testing-library/jest-dom/vitest';

// testing-library's auto-cleanup detects the test runner via global
// afterEach/expect; this repo doesn't set `test.globals: true` in
// vitest.config.ts, so register cleanup explicitly instead.
afterEach(() => {
  cleanup();
});
