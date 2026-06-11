// SSE-over-POST consumer. EventSource is GET-only, so we hand-roll
// chunked text parsing on top of fetch() + ReadableStream.
//
// Contract mirrors api/genui/streamer.py:
//   - `ready` once at the start with `{schema_version: 1}`
//   - 0..N `block` events with `UIBlock` payload
//   - exactly one of `done` or `error` as terminator (never both)
//
// Validation: we trust the server validated each block via validate_block,
// but we still type-narrow on `block.type` on the client side so a future
// server bug can't drop garbage into our rendering pipeline.

import type { ChatRequest, UIBlock } from '@arcana/schema';

/** One agent entry in the pipeline trace (mirrors api/genui/trace.py). */
export interface TraceAgent {
  name: string;
  tier: 1 | 2 | 3 | 4;
  status: 'ok' | 'partial' | 'failed';
  is_hop: boolean;
}

/** Full trace payload emitted on `event: trace` before the first block. */
export interface PipelineTrace {
  agents: TraceAgent[];
  hops_used: number;
  intent: string;
}

export interface StreamCallbacks {
  onReady?: (data: { schema_version: number }) => void;
  onTrace?: (trace: PipelineTrace) => void;
  onBlock?: (block: UIBlock) => void;
  onError?: (data: { error: string; code?: string; request_id?: string }) => void;
  onDone?: (data: { emitted: number }) => void;
}

export type ChatStreamRequest = ChatRequest;

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
);

export async function streamChat(
  request: ChatStreamRequest,
  callbacks: StreamCallbacks,
  init?: { signal?: AbortSignal },
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(request),
      signal: init?.signal,
    });
  } catch (err) {
    callbacks.onError?.({
      error: err instanceof Error ? err.message : 'network error',
      code: 'network_error',
    });
    return;
  }

  if (!response.ok) {
    let body = '';
    try {
      body = await response.text();
    } catch {
      // ignore
    }
    callbacks.onError?.({
      error: `HTTP ${response.status}: ${body.slice(0, 200)}`,
      code: 'http_error',
    });
    return;
  }

  if (!response.body) {
    callbacks.onError?.({ error: 'response had no body', code: 'no_body' });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE separates events with a blank line (\n\n). Parse all complete
      // frames and leave any trailing partial frame in `buffer`.
      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        dispatchFrame(raw, callbacks);
      }
    }
    // Flush any trailing data without a terminator.
    if (buffer.trim()) {
      dispatchFrame(buffer, callbacks);
    }
  } catch (err) {
    callbacks.onError?.({
      error: err instanceof Error ? err.message : 'stream read failed',
      code: 'stream_read_error',
    });
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
}

function dispatchFrame(raw: string, callbacks: StreamCallbacks): void {
  const lines = raw.split('\n');
  let event = '';
  let data = '';
  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim();
    } else if (line.startsWith('data:')) {
      data = line.slice('data:'.length).trimStart();
    }
    // `id:` and `retry:` are unused by the slice; the server emits `id:`
    // for forward-compat with `Last-Event-Id` reconnect, but we don't
    // resume from disconnect yet.
  }
  if (!event) return;

  let payload: unknown;
  try {
    payload = JSON.parse(data || 'null');
  } catch {
    callbacks.onError?.({
      error: `malformed JSON in ${event} frame`,
      code: 'malformed_frame',
    });
    return;
  }

  switch (event) {
    case 'ready':
      callbacks.onReady?.(payload as { schema_version: number });
      break;
    case 'block':
      // Defensive: confirm it has the discriminator the registry expects.
      if (payload && typeof payload === 'object' && 'type' in payload) {
        callbacks.onBlock?.(payload as UIBlock);
      } else {
        callbacks.onError?.({
          error: 'block frame missing `type` discriminator',
          code: 'malformed_block',
        });
      }
      break;
    case 'error':
      callbacks.onError?.(
        payload as { error: string; code?: string; request_id?: string },
      );
      break;
    case 'trace':
      callbacks.onTrace?.(payload as PipelineTrace);
      break;
    case 'done':
      callbacks.onDone?.(payload as { emitted: number });
      break;
    // Ignore unknown events so the server can introduce new event types
    // (heartbeat, partial-update, ...) without breaking older clients.
  }
}
