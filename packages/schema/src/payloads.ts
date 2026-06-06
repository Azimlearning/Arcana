// Per-component data payloads.
// PRD §16.1. Each GenUI variant has one corresponding *Data interface here.
//
// Slice scope: CitedSummaryData + Slice 2 additions (LiteratureMatrix,
// ContradictionAlert, GapAnalysis, InsightCard, KnowledgeGraphView) +
// Slice 3 additions (FlashcardDeck, QuizCard, SocraticDialog, FeynmanExplainer).

export interface Citation {
  id: string;
  docId: string;
  docTitle: string;
  page: number | null;
  quote: string;
}

export interface SummarySegment {
  text: string;
  citationIds: string[];
}

export interface CitedSummaryData {
  summary: string;
  segments: SummarySegment[];
  citations: Citation[];
}

// ── LiteratureMatrix ──────────────────────────────────────────────────────
// Papers × dimensions comparison grid (Research mode, studio/chat panel).

export interface MatrixCell {
  text: string;
  citationId: string | null;
}

export interface MatrixRow {
  docId: string;
  docTitle: string;
  cells: MatrixCell[];
}

export interface LiteratureMatrixData {
  query: string;
  dimensions: string[];
  rows: MatrixRow[];
  citations: Citation[];
}

// ── ContradictionAlert ────────────────────────────────────────────────────
// Flags where sources disagree on a concept (Research/Graph, chat panel).

export interface ContradictingClaim {
  docId: string;
  docTitle: string;
  stance: string;
  quote: string;
}

export interface ContradictionAlertData {
  concept: string;
  summary: string;
  claims: ContradictingClaim[];
}

// ── GapAnalysis ───────────────────────────────────────────────────────────
// What the corpus does not cover (Research/Discovery, studio panel).

export type GapSeverity = 'high' | 'medium' | 'low';

export interface KnowledgeGap {
  label: string;
  description: string;
  severity: GapSeverity;
}

export interface GapAnalysisData {
  summary: string;
  gaps: KnowledgeGap[];
  coveredTopics: string[];
}

// ── InsightCard ───────────────────────────────────────────────────────────
// A surfaced serendipitous cross-document link (Discovery, chat/studio panel).

export interface InsightCardData {
  insight: string;
  connection: string;
  docAId: string;
  docATitle: string;
  docBId: string;
  docBTitle: string;
  citations: Citation[];
}

// ── KnowledgeGraphView ────────────────────────────────────────────────────
// Entity/edge graph snapshot (Graph/Visual, studio panel).
// Interactive D3 rendering is a P1 §1.2 stretch goal; this slice ships a
// static node-list view. The payload shape is final so agents don't change.

export interface GraphNode {
  id: string;
  label: string;
  nodeType: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

export interface KnowledgeGraphViewData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  focusNodeId?: string;
}

// ── FlashcardDeck ─────────────────────────────────────────────────────────
// Active-recall cards with spaced-repetition scheduling (Learning, chat/studio).
// FR-LRN-01, FR-LRN-02.

export interface ScheduleState {
  dueAt: string;       // ISO 8601 date
  interval: number;    // days until next review
  easeFactor: number;  // FSRS/SM-2 ease factor (default 2.5)
  repetitions: number; // times successfully reviewed
}

export interface Flashcard {
  front: string;
  back: string;
  source: Citation;
  schedule: ScheduleState | null; // null on first generation, set after first review
}

export interface FlashcardDeckData {
  topic: string;
  cards: Flashcard[];
  totalCards: number;
  dueCount: number; // cards due now (0 on first generation)
}

// ── QuizCard ──────────────────────────────────────────────────────────────
// MCQ / short-answer question item (Learning, chat panel).
// FR-LRN-03.

export type QuizType = 'mcq' | 'short_answer';
export type QuizDifficulty = 'recall' | 'comprehension' | 'application' | 'analysis';

export interface QuizOption {
  index: number;
  text: string;
}

export interface QuizCardData {
  question: string;
  questionType: QuizType;
  options: QuizOption[];        // empty for short_answer
  correctIndex: number | null;  // null for short_answer
  explanation: string;
  difficulty: QuizDifficulty;
  source: Citation;
}

// ── SocraticDialog ────────────────────────────────────────────────────────
// Guided questioning that withholds answers (Socratic Tutor, chat panel).
// FR-LRN-08. The `nextQuestion` field MUST never contain a direct answer.

export type SocraticRole = 'tutor' | 'learner';
export type BloomLevel =
  | 'recall'
  | 'comprehension'
  | 'application'
  | 'analysis'
  | 'synthesis'
  | 'evaluation';

export interface SocraticTurn {
  role: SocraticRole;
  text: string;
}

export interface SocraticDialogData {
  concept: string;
  turns: SocraticTurn[];
  nextQuestion: string; // tutor's next probe — NEVER an answer
  bloomLevel: BloomLevel;
}

// ── FeynmanExplainer ──────────────────────────────────────────────────────
// Simplified explanation + flagged gaps (Learning, chat panel).
// FR-LRN-04.

export interface FeynmanExplainerData {
  concept: string;
  explanation: string;
  gaps: string[];  // things the learner should revisit
  source: Citation;
}
