// UIBlock — the typed payload every agent emits and every component renders.
// PRD §13.1 (Listing 13.1). The single source of truth for the wire contract.
//
// Adding a new variant is a three-step change (uiux_plan.md §5):
//   1. Add its *Data interface to payloads.ts and a variant interface here.
//   2. Add the variant to the UIBlock union below.
//   3. Add web/components/genui/<Name>.tsx + one registry.ts line.
// The codegen mirrors steps 1-2 into api/genui/_generated.py automatically.

import type { CitedSummaryData } from './payloads.js';

export type Panel = 'sources' | 'chat' | 'studio';
export type BlockStatus = 'loading' | 'partial' | 'ready' | 'error';

export interface BlockMeta {
  panel: Panel;
  order: number;
  status: BlockStatus;
}

export interface CitedSummary {
  type: 'CitedSummary';
  id: string;
  meta: BlockMeta;
  data: CitedSummaryData;
}

// Single-arm "union" today; codegen emits `UIBlock = CitedSummary`.
// Adding a second variant flips this to `CitedSummary | FlashcardDeck | …`,
// and the codegen automatically emits the discriminated `Field(discriminator='type')` form.
// See .claude/skills/schema-first-change/SKILL.md for the full step list.
export type UIBlock = CitedSummary;
