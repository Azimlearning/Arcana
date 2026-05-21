// Zustand store for the current turn's UIBlocks.
//
// Slice scope keeps the API tiny:
//   - `blocks` — current turn's blocks, in arrival order
//   - `streaming` — is a turn in flight?
//   - `lastError` — most recent error frame (cleared when a new turn starts)
//
// History across turns lives in `sessionStore` (P1). Per-panel routing
// (Sources / Chat / Studio) is read from `block.meta.panel` at render time.

import { create } from 'zustand';

import type { UIBlock } from '@arcana/schema';

interface BlockStore {
  blocks: UIBlock[];
  streaming: boolean;
  lastError: { error: string; code?: string } | null;

  startTurn: () => void;
  pushBlock: (block: UIBlock) => void;
  replaceBlockById: (id: string, block: UIBlock) => void;
  setError: (err: { error: string; code?: string } | null) => void;
  finishTurn: () => void;
  reset: () => void;
}

export const useBlockStore = create<BlockStore>((set) => ({
  blocks: [],
  streaming: false,
  lastError: null,

  startTurn: () => set({ streaming: true, lastError: null }),
  pushBlock: (block) => set((s) => ({ blocks: [...s.blocks, block] })),
  // Replace BY ID (not position) so multi-block turns - which land in P1
  // when the orchestrator emits intermediate partials - don't clobber
  // each other. If the id isn't found, no-op (e.g., user reset mid-stream).
  replaceBlockById: (id, block) =>
    set((s) => {
      const idx = s.blocks.findIndex((b) => b.id === id);
      if (idx === -1) return s;
      const next = s.blocks.slice();
      next[idx] = block;
      return { blocks: next };
    }),
  setError: (err) => set({ lastError: err }),
  finishTurn: () => set({ streaming: false }),
  reset: () => set({ blocks: [], streaming: false, lastError: null }),
}));
