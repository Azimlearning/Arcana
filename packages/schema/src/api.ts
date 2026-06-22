// HTTP request/response shapes that cross the wire.
// PRD §10 (Listing 10.1). Anything that crosses the wire belongs here.

export type ChatRole = 'user' | 'assistant';

// The active interaction mode. Single source of truth for both the wire
// (ChatRequest.activeMode) and the frontend uiStore. The backend maps these
// to agent intents (api/agents/graph.py:_MODE_TO_INTENT). FR-UI-06.
export type Mode = 'research' | 'study' | 'writing' | 'socratic' | 'exploration';

// Retrieval scope for grounded agents (FR-RET-07). 'auto' lets the backend
// pick local/global/hybrid from the query shape.
export type RetrievalMode = 'local' | 'global' | 'hybrid' | 'auto';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatRequest {
  notebookId: string;
  message: string;
  history: ChatMessage[];
  // Optional so older clients (and tests) that omit it still validate; the
  // backend coalesces a missing mode to 'research'. FR-UI-06.
  activeMode?: Mode;
  // Optional retrieval scope; backend defaults to 'auto'. FR-RET-07.
  retrievalMode?: RetrievalMode;
}

// Response from POST /ingest (FR-ING-01). The request is multipart/form-data
// so it has no schema type; only the response crosses the wire as JSON.
export interface IngestResponse {
  docId: string;
  title: string;
  status: 'ready' | 'failed';
  chunkCount: number;
  error: string | null;  // populated when status='failed'
}

// POST /ingest/url request body (FR-ING-02).
export interface UrlIngestRequest {
  url: string;
  notebookId?: string;
}

// POST /ingest/youtube request body (FR-ING-03).
export interface YoutubeIngestRequest {
  url: string;
  notebookId?: string;
}

// POST /highlights request body (FR-USR-05) — a user highlight/note to fold
// back into the knowledge graph, attributed to its source document.
export interface HighlightRequest {
  docId: string;
  text: string;
  note?: string;
  notebookId?: string;
}

export interface HighlightResponse {
  docId: string;
  nodesAdded: number;
  edgesAdded: number;
  concepts: string[];
}

// GET /docs and GET /docs/{docId} (FR-ING-08).
export interface DocStatusResponse {
  docId: string;
  title: string;
  sourceUri: string;
  status: 'pending' | 'parsing' | 'embedding' | 'ready' | 'failed';
  sizeBytes: number;
  error: string | null;
  createdAt: string;  // ISO 8601
}

export interface DocListResponse {
  docs: DocStatusResponse[];
}

// ── Spaced-repetition review (FR-LRN-02) ─────────────────────────────────────

// Rating for spaced-repetition review: 0-2 = fail (again); 3 = hard; 4 = good; 5 = easy.
export type ReviewRating = number;

export interface ReviewRequest {
  cardId: string;
  rating: ReviewRating;
  // currentSchedule omitted — server reconstructs from its own store.
  // Keeps the wire minimal and prevents client-side schedule tampering.
}

export interface ReviewResponse {
  cardId: string;
  dueAt: string;        // ISO 8601
  interval: number;     // days until next review
  easeFactor: number;   // SM-2 ease factor
  repetitions: number;  // times successfully reviewed
}

// ── Notebook CRUD (FR-USR-03) ────────────────────────────────────────────────

export interface NotebookCreate {
  title: string;
}

export interface NotebookItem {
  id: string;
  userId: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  docCount: number;
}

export interface NotebookListResponse {
  notebooks: NotebookItem[];
}

export interface NotebookDeleteResponse {
  deleted: string;
}

// ── Analytics / User Study (FR-ANL-01, FR-ANL-03, R-03) ─────────────────────

export interface TurnEvent {
  sessionId: string;
  userId: string;
  timestamp: string;           // ISO 8601
  query: string;               // truncated to 500 chars
  mode: Mode;
  intent: string;
  agentsTriggered: string[];
  latencyMs: number;
  blockTypes: string[];
  retrievedChunkCount: number;
}

export interface FeedbackRating {
  sessionId: string;
  blockId: string;
  userId: string;
  rating: 'up' | 'down';
  blockType: string;
  timestamp: string;           // ISO 8601
}

export interface SurveySubmission {
  sessionId: string;
  userId: string;
  timestamp: string;           // ISO 8601
  responses: number[];         // 10 items, Likert 1-5
  susScore: number;            // computed 0-100
  taskDescription: string;
}

// ── Graph view (FR-KG-08) ─────────────────────────────────────────────────────
// Wire types for GET /graph — returns the calling user's knowledge graph so the
// frontend can render an interactive visualisation.

export interface GraphViewNode {
  id: string;
  label: string;
  nodeType: string;             // 'Concept' | 'Person' | 'Document' | 'Topic' | …
  properties: Record<string, unknown>;
  community?: number;           // Louvain community id (FR-KG-04)
  pagerank?: number;            // PageRank score 0..1 (FR-KG-05)
}

export interface GraphViewEdge {
  id: string;                   // "{src}-[{type}]->{dst}"
  src: string;
  dst: string;
  edgeType: string;
}

export interface GraphViewResponse {
  nodes: GraphViewNode[];
  edges: GraphViewEdge[];
  nodeCount: number;
  edgeCount: number;
}

// ── User profile CRUD (FR-USR-02) ─────────────────────────────────────────────
// GET /profile returns UserProfile (defined in entities.ts).
// PUT /profile accepts UpdateProfileRequest; returns the updated UserProfile.

export interface UpdateProfileRequest {
  displayName?: string | null;
  defaultMode?: string;
  theme?: string;
  citationStyle?: string;
  studyContext?: string;
}
