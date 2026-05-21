// Per-component data payloads.
// PRD §16.1. Each GenUI variant has one corresponding *Data interface here.
//
// Slice scope: only CitedSummaryData. Additional payloads are added in
// later slices alongside their UIBlock variant and React component.

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
