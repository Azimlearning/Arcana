// Per-component data payloads.
// PRD §16.1. Each GenUI variant has one corresponding *Data interface here.
//
// Slice scope: CitedSummaryData + Slice 2 additions (LiteratureMatrix,
// ContradictionAlert, GapAnalysis, InsightCard, KnowledgeGraphView).

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
