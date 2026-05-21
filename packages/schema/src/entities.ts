// Domain entities that the frontend may need to know about.
// PRD §19.1. Backend-internal fields (e.g. raw embedding vectors) stay
// in api/ — only the wire-visible shape lives here.
//
// Slice scope: Document + Chunk are enough for the SourceList +
// CitedSummary path. Other entities (GraphNode/Edge, Notebook,
// UserProfile, ReviewState) arrive when first used.

export type IngestStatus = 'pending' | 'parsing' | 'embedding' | 'ready' | 'failed';

export interface Document {
  id: string;
  title: string;
  sourceUri: string;
  ingestStatus: IngestStatus;
}

export interface Chunk {
  id: string;
  docId: string;
  text: string;
  page: number | null;
}
