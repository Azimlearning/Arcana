// HTTP request/response shapes that cross the wire.
// PRD §10 (Listing 10.1). Anything that crosses the wire belongs here.

export type ChatRole = 'user' | 'assistant';

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatRequest {
  notebookId: string;
  message: string;
  history: ChatMessage[];
}
