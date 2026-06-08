import { beforeEach, describe, expect, it } from 'vitest';

import type { Mode } from '@arcana/schema';

import { MODE_LAYOUT, selectActiveLayout, useUIStore } from '@/store/uiStore';
import type { PanelLayout } from '@/store/uiStore';

const ALL_MODES: Mode[] = ['research', 'study', 'writing', 'socratic', 'exploration'];

describe('uiStore.activeMode', () => {
  beforeEach(() => {
    useUIStore.setState({ activeMode: 'research', layoutOverride: null });
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

  it('setActiveMode clears any layout override', () => {
    const override: PanelLayout = { sources: 10, chat: 60, studio: 30 };
    useUIStore.getState().setLayoutOverride(override);
    expect(useUIStore.getState().layoutOverride).toEqual(override);

    useUIStore.getState().setActiveMode('study');
    expect(useUIStore.getState().layoutOverride).toBeNull();
  });
});

describe('uiStore layout', () => {
  beforeEach(() => {
    useUIStore.setState({ activeMode: 'research', layoutOverride: null });
  });

  it('MODE_LAYOUT covers all five modes', () => {
    for (const mode of ALL_MODES) {
      expect(MODE_LAYOUT[mode]).toBeDefined();
    }
  });

  it('selectActiveLayout returns MODE_LAYOUT when no override', () => {
    for (const mode of ALL_MODES) {
      useUIStore.setState({ activeMode: mode, layoutOverride: null });
      const layout = selectActiveLayout(useUIStore.getState());
      expect(layout).toEqual(MODE_LAYOUT[mode]);
    }
  });

  it('selectActiveLayout returns the override when set', () => {
    const override: PanelLayout = { sources: 5, chat: 55, studio: 40 };
    useUIStore.getState().setLayoutOverride(override);
    const layout = selectActiveLayout(useUIStore.getState());
    expect(layout).toEqual(override);
  });

  it('override wins over the default mode layout', () => {
    useUIStore.getState().setActiveMode('writing');
    // writing default: studio=0 (hidden)
    expect(selectActiveLayout(useUIStore.getState()).studio).toBe(0);

    const override: PanelLayout = { sources: 15, chat: 50, studio: 35 };
    useUIStore.getState().setLayoutOverride(override);
    expect(selectActiveLayout(useUIStore.getState()).studio).toBe(35);
  });

  it('writing mode has studio=0 (hidden)', () => {
    expect(MODE_LAYOUT.writing.studio).toBe(0);
  });

  it('exploration mode has sources=0 (hidden)', () => {
    expect(MODE_LAYOUT.exploration.sources).toBe(0);
  });

  it('chat is always non-zero in every default layout', () => {
    for (const mode of ALL_MODES) {
      expect(MODE_LAYOUT[mode].chat).toBeGreaterThan(0);
    }
  });

  it('every mode layout sums to 100', () => {
    for (const mode of ALL_MODES) {
      const { sources, chat, studio } = MODE_LAYOUT[mode];
      expect(sources + chat + studio).toBe(100);
    }
  });

  it('selectActiveLayout reflects cleared override after mode switch (round-trip)', () => {
    const override: PanelLayout = { sources: 5, chat: 55, studio: 40 };
    useUIStore.getState().setLayoutOverride(override);
    expect(selectActiveLayout(useUIStore.getState())).toEqual(override);

    useUIStore.getState().setActiveMode('exploration');
    expect(selectActiveLayout(useUIStore.getState())).toEqual(MODE_LAYOUT.exploration);
  });
});
