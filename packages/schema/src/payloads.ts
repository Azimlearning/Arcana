// Per-component data payloads.
// PRD §16.1. Each GenUI variant has one corresponding *Data interface here.
//
// Slice scope: CitedSummaryData + Slice 2 additions (LiteratureMatrix,
// ContradictionAlert, GapAnalysis, InsightCard, KnowledgeGraphView) +
// Slice 3 additions (FlashcardDeck, QuizCard, SocraticDialog, FeynmanExplainer) +
// Slice 4 additions (DraftEditor).

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
  community?: number;   // Louvain community id for colour-coding (FR-KG-04)
  pagerank?: number;    // PageRank score 0..1 for node sizing (FR-KG-05)
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

// ── DraftEditor ───────────────────────────────────────────────────────────
// Structured academic draft with cited sections (Writing mode, chat panel).
// FR-WRT-01 (P1).

export interface DraftSection {
  heading: string;
  body: string;         // prose with inline [cN] citation markers
  citationIds: string[];
}

export interface DraftEditorData {
  title: string;
  sections: DraftSection[];
  citations: Citation[];
  wordCount: number;
}

// ── StudyPlanner ────────────────────────────────────────────────────────
// SM-2 due-card queue + session stats (StudyPlannerAgent tier-4, studio panel).
// FR-LRN-09, FR-LRN-10.

export interface DueCard {
  cardId: string;
  front: string;        // question side shown in the queue
  topic: string;
  dueAt: string;        // ISO 8601 date
  intervalDays: number;
  overdue: boolean;
}

export interface StudyPlannerData {
  notebookId: string;
  dueCards: DueCard[];
  totalDue: number;
  overdueCount: number;
  nextSessionAt: string | null; // ISO date of the next card not yet due, null if queue empty
  sessionGoal: number;          // target cards to review this session (default 10)
}

// ── BlurtingPrompt ────────────────────────────────────────────────────
// Free-recall prompt + grounding passage revealed after blurt (Learning, chat).
// FR-LRN-06.

export interface BlurtingPromptData {
  topic: string;
  prompt: string;         // e.g. "Without looking at your notes, write down everything you know about X"
  sourcePassage: string;  // grounding text revealed after the user blurts
  citations: Citation[];
}

// ── CornellNotes ────────────────────────────────────────────────────────
// Structured cue / notes / summary note (Learning, studio panel).
// FR-LRN-05.

export interface CornellNote {
  cue: string;           // left-column question / keyword
  content: string;       // right-column answer / elaboration
  citationIds: string[];
}

export interface CornellNotesData {
  topic: string;
  notes: CornellNote[];
  summary: string;       // bottom summary paragraph
  citations: Citation[];
}

// ── SourceList ────────────────────────────────────────────────────────────
// Ingested-sources panel (sources panel, P0).

export interface SourceDocument {
  docId: string;
  title: string;
  sourceUri: string;
  status: 'pending' | 'parsing' | 'embedding' | 'ready' | 'failed';
  sizeBytes: number;
  chunkCount: number;
  createdAt: string;    // ISO 8601
  error: string | null;
}

export interface SourceListData {
  notebookId: string;
  documents: SourceDocument[];
  totalCount: number;
}

// ── CitationPreview ────────────────────────────────────────────────────────
// Formatted single-document citation in a chosen style (Citation, chat).

export type CitationStyle = 'apa' | 'mla' | 'chicago' | 'ieee' | 'harvard';

export interface CitationPreviewData {
  docId: string;
  docTitle: string;
  authors: string[];
  year: number | null;
  sourceUri: string;
  formatted: string;    // pre-formatted citation string
  style: CitationStyle;
}

// ── BibliographyExport ─────────────────────────────────────────────────────
// BibTeX / RIS export panel (Citation, studio). FR-EXP-08.

export interface BibEntry {
  key: string;          // citation key e.g. "Smith2020"
  docId: string;
  docTitle: string;
  authors: string[];
  year: number | null;
  sourceType: 'article' | 'book' | 'misc';
  bibtex: string;       // full BibTeX entry string
}

export interface BibliographyExportData {
  entries: BibEntry[];
  bibtexAll: string;    // concatenated BibTeX for one-click copy
}

// ── ConceptMap ─────────────────────────────────────────────────────────────
// Concept-relationship map for reasoning (Visual/Socratic, studio). P1.

export interface ConceptNode {
  id: string;
  label: string;
  description: string;
  level: number;        // 0 = root, 1 = primary, 2 = secondary
}

export interface ConceptLink {
  source: string;
  target: string;
  label: string;        // e.g. "influences", "contradicts"
}

export interface ConceptMapData {
  rootConcept: string;
  nodes: ConceptNode[];
  links: ConceptLink[];
  citations: Citation[];
}

// ── ComparisonChart ────────────────────────────────────────────────────────
// Structured comparative data chart (Visual, chat/studio). P1.

export interface ChartSeries {
  name: string;
  values: number[];
}

export type ChartType = 'bar' | 'radar' | 'scatter';

export interface ComparisonChartData {
  title: string;
  chartType: ChartType;
  labels: string[];     // x-axis / dimension labels
  series: ChartSeries[];
  unit: string | null;
  citations: Citation[];
}

// ── Timeline ───────────────────────────────────────────────────────────────
// Chronological event view (Visual/Research, studio). P1.

export interface TimelineEvent {
  date: string;         // ISO 8601 or plain year "1905"
  label: string;
  description: string;
  docId: string | null;
  citationId: string | null;
}

export interface TimelineData {
  title: string;
  events: TimelineEvent[];
  citations: Citation[];
}

// ── DataTable ─────────────────────────────────────────────────────────────
// Sortable structured data table (Visual/Research, chat). P1.

export interface TableColumn {
  key: string;
  label: string;
  sortable: boolean;
}

export interface DataTableRow {
  cells: string[];   // ordered to match columns
}

export interface DataTableData {
  title: string;
  columns: TableColumn[];
  rows: DataTableRow[];
  citations: Citation[];
}

// ── ProgressDashboard ──────────────────────────────────────────────────────
// Learning-progress and retention metrics (Analytics, studio). FR-LRN-10.

export interface TopicProgress {
  topic: string;
  totalCards: number;
  masteredCards: number;   // cards with interval >= 21 days
  dueCount: number;
  retentionRate: number;   // 0–1
}

export interface ProgressDashboardData {
  notebookId: string;
  totalCards: number;
  masteredCards: number;
  streakDays: number;
  topics: TopicProgress[];
  nextReviewAt: string | null;  // ISO 8601, null if queue empty
}
