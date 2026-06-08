// Zustand store for shell UI state.
//
// `activeMode` drives both the UI (panel layout, mode chrome) and the wire:
// ChatPanel sends it on every turn so the backend can route to the matching
// agent (api/agents/graph.py:_MODE_TO_INTENT). FR-UI-06.
//
// `Mode` is owned by the schema package (single source of truth across the
// wire) and re-exported here so shell components import it from one place.

import { create } from 'zustand';

import type { Mode } from '@arcana/schema';

export type { Mode };

interface UIStore {
  activeMode: Mode;
  setActiveMode: (m: Mode) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  activeMode: 'research',
  setActiveMode: (m) => set({ activeMode: m }),
}));
