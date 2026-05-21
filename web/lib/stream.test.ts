// SSE consumer unit tests - hand-fed chunks through a mocked fetch().
// Covers the wire-protocol guarantees (chunk boundary handling,
// event dispatch, error frames as terminal).

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { streamChat } from './stream';

function makeStreamingResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  let i = 0;
  const stream = new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i]!));
        i += 1;
      } else {
        controller.close();
      }
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

describe('streamChat', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch');
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('dispatches ready → block → done in order', async () => {
    const chunks = [
      'event: ready\nid: 0\ndata: {"schema_version":1}\n\n',
      'event: block\nid: 1\ndata: {"type":"CitedSummary","id":"b1","meta":{"panel":"chat","order":0,"status":"ready"},"data":{"summary":"hi","segments":[],"citations":[]}}\n\n',
      'event: done\nid: 2\ndata: {"emitted":1}\n\n',
    ];
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeStreamingResponse(chunks),
    );

    const events: string[] = [];
    await streamChat(
      { notebookId: 'nb1', message: 'hi', history: [] },
      {
        onReady: () => events.push('ready'),
        onBlock: () => events.push('block'),
        onDone: () => events.push('done'),
        onError: () => events.push('error'),
      },
    );

    expect(events).toEqual(['ready', 'block', 'done']);
  });

  it('handles a frame split across two TCP chunks', async () => {
    const chunks = [
      'event: ready\nid: 0\ndata: {"schema_v',
      'ersion":1}\n\nevent: done\nid: 1\ndata: {"emitted":0}\n\n',
    ];
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeStreamingResponse(chunks),
    );

    const events: string[] = [];
    await streamChat(
      { notebookId: 'nb1', message: 'hi', history: [] },
      {
        onReady: () => events.push('ready'),
        onDone: () => events.push('done'),
        onError: () => events.push('error'),
      },
    );

    expect(events).toEqual(['ready', 'done']);
  });

  it('calls onError with HTTP status on non-200', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response('bad', { status: 500 }),
    );

    let err: { error: string; code?: string } | undefined;
    await streamChat(
      { notebookId: 'nb1', message: 'hi', history: [] },
      { onError: (e) => (err = e) },
    );

    expect(err).toBeDefined();
    expect(err!.code).toBe('http_error');
    expect(err!.error).toContain('500');
  });

  it('routes an `error` frame to onError (terminal)', async () => {
    const chunks = [
      'event: ready\nid: 0\ndata: {"schema_version":1}\n\n',
      'event: error\nid: 1\ndata: {"error":"orch blew up","code":"internal_error","request_id":"abc"}\n\n',
    ];
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeStreamingResponse(chunks),
    );

    let err: { error: string; code?: string; request_id?: string } | undefined;
    let doneCalled = false;
    await streamChat(
      { notebookId: 'nb1', message: 'hi', history: [] },
      {
        onError: (e) => (err = e),
        onDone: () => (doneCalled = true),
      },
    );

    expect(err).toEqual({
      error: 'orch blew up',
      code: 'internal_error',
      request_id: 'abc',
    });
    expect(doneCalled).toBe(false);   // error is terminal — no done after
  });

  it('flushes a trailing frame missing the final blank line', async () => {
    // The server normally terminates each event with `\n\n`. A network drop
    // or buggy proxy could deliver the last event without it. The parser
    // must still dispatch that trailing frame rather than silently dropping it.
    const chunks = [
      'event: ready\nid: 0\ndata: {"schema_version":1}\n\n',
      'event: done\nid: 1\ndata: {"emitted":0}',   // <-- no trailing \n\n
    ];
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeStreamingResponse(chunks),
    );

    const events: string[] = [];
    await streamChat(
      { notebookId: 'nb1', message: 'hi', history: [] },
      {
        onReady: () => events.push('ready'),
        onDone: () => events.push('done'),
        onError: () => events.push('error'),
      },
    );

    expect(events).toEqual(['ready', 'done']);
  });

  it('ignores unknown event types (forward-compat)', async () => {
    const chunks = [
      'event: heartbeat\nid: 0\ndata: {}\n\n',
      'event: done\nid: 1\ndata: {"emitted":0}\n\n',
    ];
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      makeStreamingResponse(chunks),
    );

    let doneCalled = false;
    let errorCalled = false;
    await streamChat(
      { notebookId: 'nb1', message: 'hi', history: [] },
      {
        onDone: () => (doneCalled = true),
        onError: () => (errorCalled = true),
      },
    );

    expect(doneCalled).toBe(true);
    expect(errorCalled).toBe(false);
  });
});
