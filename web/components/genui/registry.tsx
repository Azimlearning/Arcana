// Block-renderer registry - the only place that maps `block.type` to a
// React component. Per PRD §14.2 + invariant #2/#3: the chat renderer
// never hand-switches on type.
//
// Adding a new GenUI component is a three-step change (uiux_plan.md §5):
//   1. Add the variant to packages/schema/src/blocks.ts + payloads.ts
//   2. Create components/genui/<Name>.tsx implementing all four states
//   3. Add ONE line here
// `pnpm --filter @arcana/schema codegen` mirrors steps 1 into the
// generated Pydantic. This file enforces the third step at type level —
// TS errors on `renderBlock` if you forget.

import type { ComponentType } from 'react';

import type { UIBlock } from '@arcana/schema';

import { CitedSummary } from '@/components/genui/CitedSummary';
import { LiteratureMatrix } from '@/components/genui/LiteratureMatrix';
import { ContradictionAlert } from '@/components/genui/ContradictionAlert';
import { DraftEditor } from '@/components/genui/DraftEditor';
import { FeynmanExplainer } from '@/components/genui/FeynmanExplainer';
import { FlashcardDeck } from '@/components/genui/FlashcardDeck';
import { GapAnalysis } from '@/components/genui/GapAnalysis';
import { InsightCard } from '@/components/genui/InsightCard';
import { KnowledgeGraphView } from '@/components/genui/KnowledgeGraphView';
import { QuizCard } from '@/components/genui/QuizCard';
import { SocraticDialog } from '@/components/genui/SocraticDialog';
import { BlurtingPrompt } from '@/components/genui/BlurtingPrompt';
import { CornellNotes } from '@/components/genui/CornellNotes';
import { StudyPlanner } from '@/components/genui/StudyPlanner';
import { ErrorState } from '@/components/genui/BlockStates';

type BlockType = UIBlock['type'];

type RendererMap = {
  [T in BlockType]: ComponentType<{ block: Extract<UIBlock, { type: T }> }>;
};

const registry: RendererMap = {
  CitedSummary,
  LiteratureMatrix,
  ContradictionAlert,
  DraftEditor,
  FeynmanExplainer,
  FlashcardDeck,
  GapAnalysis,
  InsightCard,
  KnowledgeGraphView,
  QuizCard,
  SocraticDialog,
  BlurtingPrompt,
  CornellNotes,
  StudyPlanner,
};

/** Render a UIBlock by looking up its component via the discriminator.
 *  Returns an error tile if the type isn't registered (shouldn't happen
 *  because TS won't compile if the map is incomplete, but defensive
 *  against runtime payloads that lie about their `type`). */
export function renderBlock(block: UIBlock): JSX.Element {
  // The Map's value type is keyed on T; the indexed lookup loses that
  // narrowing, so cast at the boundary. Runtime safety: the registry is
  // complete by construction (RendererMap is exhaustive).
  const Component = registry[block.type] as
    | ComponentType<{ block: UIBlock }>
    | undefined;
  if (!Component) {
    // Unreachable for typed UIBlock; safety net for malformed payloads.
    const unknownType = (block as { type?: string }).type ?? '<missing>';
    return <ErrorState message={`No renderer for block type "${unknownType}"`} />;
  }
  return <Component block={block} />;
}

/** Test-only helper - lets unit tests assert the registry covers every
 *  variant without reaching into module internals. */
export function _registeredTypes(): readonly BlockType[] {
  return Object.keys(registry) as BlockType[];
}
