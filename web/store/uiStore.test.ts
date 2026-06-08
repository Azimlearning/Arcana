import { beforeEach, describe, expect, it } from 'vitest';

import type { Mode } from '@arcana/schema';

import { useUIStore } from '@/store/uiStore';

const ALL_MODES: Mode[] = ['research', 'study', 'writing', 'socratic', 'exploration'];

describe('uiStore.activeMode', () => {
  beforeEach(() => {
    useUIStore.setState({ activeMode: 'research' });
  });

  it('defaults to research', () => {
    expect(useUIStore.getState().activeMode).toBe('research');
  });

  it('setActiveMode updates the active mode', () => {
    useUIStore.getState().setActiveMode('writing');
    expect(useUIStore.getState().activeMode).toBe('writing');
  });

  it('accepts every wire Mode value', () => {
    for (const mode of ALL_MODES) {
      useUIStore.getState().setActiveMode(mode);
      expect(useUIStore.getState().activeMode).toBe(mode);
    }
  });
});
