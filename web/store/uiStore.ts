// Zustand store for shell UI state.
//
// Slice scope: only `activeMode`, fixed to 'research'. Mode switcher,
// panel-width overrides (FR-UI-07), and animation flags land in P1.
//
// TODO(P1, FR-UI-07): wire setActiveMode from the mode switcher in the
// header. Slice ships the setter unused so the ModeIndicator stays a
// pure read site.

import { create } from 'zustand';

export type Mode = 'research' | 'study' | 'writing' | 'socratic' | 'exploration';

interface UIStore {
  activeMode: Mode;
  setActiveMode: (m: Mode) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  activeMode: 'research',
  setActiveMode: (m) => set({ activeMode: m }),
}));
