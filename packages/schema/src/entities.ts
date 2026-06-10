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

// ── UserProfile ───────────────────────────────────────────────────────────
// Persistent user identity + preferences. FR-USR-02.

export interface UserProfile {
  uid: string;           // Firebase UID or dev stub id
  email: string | null;
  displayName: string | null;
  createdAt: string;     // ISO 8601
  updatedAt: string;     // ISO 8601
  preferences: UserPreferences;
}

export interface UserPreferences {
  defaultMode: string;     // 'research' | 'study' | 'writing' | 'socratic' | 'exploration'
  theme: string;           // 'light' | 'dark' | 'system'
  citationStyle: string;   // 'apa' | 'mla' | 'chicago' | 'ieee' | 'harvard'
  studyContext: string;    // free-text; injected into agent system prompts for personalisation
}

// ── Notebook ──────────────────────────────────────────────────────────────
// Named workspace scoped to a user. FR-USR-03, FR-USR-06.

export interface Notebook {
  id: string;
  userId: string;
  title: string;
  createdAt: string;  // ISO 8601
  updatedAt: string;  // ISO 8601
  docCount: number;
}
