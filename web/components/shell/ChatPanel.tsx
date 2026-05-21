'use client';

import { useState } from 'react';

import type { CitedSummary as CitedSummaryBlock, UIBlock } from '@arcana/schema';

import { renderBlock } from '@/components/genui/registry';
import { EmptyState } from '@/components/genui/BlockStates';
import { Button } from '@/components/ui/Button';
import { streamChat } from '@/lib/stream';
import { useBlockStore } from '@/store/blockStore';

interface Props {
  notebookId: string;
}

export function ChatPanel({ notebookId }: Props) {
  const blocks = useBlockStore((s) => s.blocks);
  const streaming = useBlockStore((s) => s.streaming);
  const lastError = useBlockStore((s) => s.lastError);
  const startTurn = useBlockStore((s) => s.startTurn);
  const pushBlock = useBlockStore((s) => s.pushBlock);
  const replaceBlockById = useBlockStore((s) => s.replaceBlockById);
  const setError = useBlockStore((s) => s.setError);
  const finishTurn = useBlockStore((s) => s.finishTurn);

  const [input, setInput] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || streaming) return;

    setInput('');
    startTurn();

    // Optimistic skeleton: append a loading-state block so the panel has
    // shape within ~50ms (uiux_plan.md §1 principle 2 — structure before
    // content). Tracked by id so multi-block turns (P1) don't clobber it.
    const optimisticId = `loading_${crypto.randomUUID()}`;
    const optimistic: CitedSummaryBlock = {
      type: 'CitedSummary',
      id: optimisticId,
      meta: { panel: 'chat', order: blocks.length, status: 'loading' },
      data: { summary: '', segments: [], citations: [] },
    };
    pushBlock(optimistic);

    // Track whether we've consumed the optimistic skeleton yet. First
    // real block REPLACES it (by id); subsequent blocks APPEND. Same
    // skeleton-key on error.
    let skeletonConsumed = false;

    await streamChat(
      { notebookId, message, history: [] },
      {
        onBlock: (block: UIBlock) => {
          if (!skeletonConsumed) {
            replaceBlockById(optimisticId, block);
            skeletonConsumed = true;
          } else {
            pushBlock(block);
          }
        },
        onError: (err) => {
          setError(err);
          if (!skeletonConsumed) {
            replaceBlockById(optimisticId, {
              ...optimistic,
              meta: { ...optimistic.meta, status: 'error' },
              data: {
                ...optimistic.data,
                summary: err.error || 'Stream failed.',
              },
            });
            skeletonConsumed = true;
          }
        },
        onDone: () => finishTurn(),
      },
    );

    // Belt-and-suspenders: streamChat catches internally and routes to
    // onError, but if neither onDone nor onError fired (shouldn't happen)
    // make sure `streaming` clears so the user can submit again.
    if (useBlockStore.getState().streaming) {
      finishTurn();
    }
  }

  return (
    <main className="h-full flex flex-col bg-paper">
      <div className="px-4 py-3 border-b border-line flex items-center justify-between">
        <h2 className="font-display text-lg text-ink">Chat</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {blocks.length === 0 ? (
          <EmptyState
            title="Ask a question"
            hint="The research agent will ground its answer in your ingested documents and cite each claim."
          />
        ) : (
          blocks.map((block) => <div key={block.id}>{renderBlock(block)}</div>)
        )}
      </div>

      <form
        onSubmit={submit}
        className="border-t border-line p-4 flex gap-2 bg-card"
      >
        <label className="sr-only" htmlFor="chat-input">
          Question
        </label>
        <input
          id="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="What does my corpus say about…"
          className="flex-1 px-3 py-2 rounded-ctl border border-line bg-paper font-serif text-ink placeholder:text-ink-softer focus:outline-none focus:ring-2 focus:ring-accent"
          disabled={streaming}
          autoComplete="off"
        />
        <Button type="submit" disabled={streaming || !input.trim()}>
          {streaming ? 'Streaming…' : 'Send'}
        </Button>
      </form>

      {lastError && !streaming && (
        <div className="px-4 py-2 text-xs font-mono text-red bg-red-bg border-t border-red/30">
          {lastError.code ?? 'error'}: {lastError.error}
        </div>
      )}
    </main>
  );
}
