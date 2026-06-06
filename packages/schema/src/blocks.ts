// UIBlock — the typed payload every agent emits and every component renders.
// PRD §13.1 (Listing 13.1). The single source of truth for the wire contract.
//
// Adding a new variant is a three-step change (uiux_plan.md §5):
//   1. Add its *Data interface to payloads.ts and a variant interface here.
//   2. Add the variant to the UIBlock union below.
//   3. Add web/components/genui/<Name>.tsx + one registry.ts line.
// The codegen mirrors steps 1-2 into api/genui/_generated.py automatically.

import type {
  CitedSummaryData,
  ContradictionAlertData,
  FeynmanExplainerData,
  FlashcardDeckData,
  GapAnalysisData,
  InsightCardData,
  KnowledgeGraphViewData,
  LiteratureMatrixData,
  QuizCardData,
  SocraticDialogData,
} from './payloads.js';

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

export interface LiteratureMatrix {
  type: 'LiteratureMatrix';
  id: string;
  meta: BlockMeta;
  data: LiteratureMatrixData;
}

export interface ContradictionAlert {
  type: 'ContradictionAlert';
  id: string;
  meta: BlockMeta;
  data: ContradictionAlertData;
}

export interface GapAnalysis {
  type: 'GapAnalysis';
  id: string;
  meta: BlockMeta;
  data: GapAnalysisData;
}

export interface InsightCard {
  type: 'InsightCard';
  id: string;
  meta: BlockMeta;
  data: InsightCardData;
}

export interface KnowledgeGraphView {
  type: 'KnowledgeGraphView';
  id: string;
  meta: BlockMeta;
  data: KnowledgeGraphViewData;
}

export interface FlashcardDeck {
  type: 'FlashcardDeck';
  id: string;
  meta: BlockMeta;
  data: FlashcardDeckData;
}

export interface QuizCard {
  type: 'QuizCard';
  id: string;
  meta: BlockMeta;
  data: QuizCardData;
}

export interface SocraticDialog {
  type: 'SocraticDialog';
  id: string;
  meta: BlockMeta;
  data: SocraticDialogData;
}

export interface FeynmanExplainer {
  type: 'FeynmanExplainer';
  id: string;
  meta: BlockMeta;
  data: FeynmanExplainerData;
}

// Discriminated union: the `type` field is the discriminator.
// Codegen emits Annotated[X | Y | Z, Field(discriminator='type')] in Python.
export type UIBlock =
  | CitedSummary
  | LiteratureMatrix
  | ContradictionAlert
  | GapAnalysis
  | InsightCard
  | KnowledgeGraphView
  | FlashcardDeck
  | QuizCard
  | SocraticDialog
  | FeynmanExplainer;
