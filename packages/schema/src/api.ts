// HTTP request/response shapes that cross the wire.
// PRD §10 (Listing 10.1). Anything that crosses the wire belongs here.

export type ChatRole = 'user' | 'assistant';

// The active interaction mode. Single source of truth for both the wire
// (ChatRequest.activeMode) and the frontend uiStore. The backend maps these
// to agent intents (api/agents/graph.py:_MODE_TO_INTENT). FR-UI-06.
export type Mode = 'research' | 'study' | 'writing' | 'socratic' | 'exploration';

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
}
