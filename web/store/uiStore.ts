// Zustand store for shell UI state.
//
// `activeMode` drives both the UI (panel layout, mode chrome) and the wire:
// ChatPanel sends it on every turn so the backend can route to the matching
// agent (api/agents/graph.py:_MODE_TO_INTENT). FR-UI-06.
//
// `layoutOverride` holds a user-set panel width override (via PanelResizer)
// that wins over the default MODE_LAYOUT for the session. It is cleared when
// the user switches modes (mode switch always resets to the mode's default
// layout so the workspace reshapes correctly). FR-UI-07.
//
// `Mode` is owned by the schema package (single source of truth across the
// wire) and re-exported here so shell components import it from one place.

import { create } from 'zustand';

import type { Mode } from '@arcana/schema';
import type { PipelineTrace } from '@/lib/stream';

export type { Mode };

/** Width ratios for the three shell panels. Values are flex-grow units;
 *  they are proportional (sum need not equal 100). A value of 0 means the
 *  panel is fully collapsed / hidden. uiux_plan.md §4. */
export interface PanelLayout {
  sources: number;
  chat: number;
  studio: number;
}

/** Default layout per mode. Values chosen from uiux_plan.md §4 targets. */
export const MODE_LAYOUT: Record<Mode, PanelLayout> = {
  research:    { sources: 20, chat: 45, studio: 35 },
  study:       { sources: 8,  chat: 45, studio: 47 },
  writing:     { sources: 20, chat: 80, studio: 0  }, // studio hidden
  socratic:    { sources: 18, chat: 40, studio: 42 },
  exploration: { sources: 0,  chat: 25, studio: 75 }, // sources hidden
};

interface UIStore {
  activeMode: Mode;
  /** Switch mode and clear any manual layout override. FR-UI-06. */
  setActiveMode: (m: Mode) => void;
  /** Manual panel layout set by PanelResizer. Null = use MODE_LAYOUT. FR-UI-07. */
  layoutOverride: PanelLayout | null;
  /** Persist a drag-resized layout for the session. FR-UI-07. */
  setLayoutOverride: (layout: PanelLayout) => void;
  /** Pre-filled query set by Studio generator tiles; consumed by ChatPanel. */
  queryDraft: string | null;
  setQueryDraft: (q: string | null) => void;
  /** Agent pipeline trace for the most recent completed turn. FR-UI (§1.6). */
  trace: PipelineTrace | null;
  setTrace: (t: PipelineTrace) => void;
  clearTrace: () => void;
}

/** Selector: returns the active layout — override wins if set. */
export function selectActiveLayout(state: UIStore): PanelLayout {
  return state.layoutOverride ?? MODE_LAYOUT[state.activeMode];
}

export const useUIStore = create<UIStore>((set) => ({
  activeMode: 'research',
  setActiveMode: (m) => set({ activeMode: m, layoutOverride: null }),
  layoutOverride: null,
  setLayoutOverride: (layout) => set({ layoutOverride: layout }),
  queryDraft: null,
  setQueryDraft: (q) => set({ queryDraft: q }),
  trace: null,
  setTrace: (t) => set({ trace: t }),
  clearTrace: () => set({ trace: null }),
}));
