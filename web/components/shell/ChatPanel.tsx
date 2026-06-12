'use client';

import { useEffect, useRef, useState } from 'react';

import type { CitedSummary as CitedSummaryBlock, UIBlock } from '@arcana/schema';

import { renderBlock } from '@/components/genui/registry';
import { EmptyState } from '@/components/genui/BlockStates';
import { BlockFeedback } from '@/components/feedback/BlockFeedback';
import { SUSModal } from '@/components/feedback/SUSModal';
import { Button } from '@/components/ui/Button';
import { streamChat } from '@/lib/stream';
import type { PipelineTrace } from '@/lib/stream';
import { PipelineTrace as PipelineTraceComponent } from '@/components/shell/PipelineTrace';
import { useBlockStore } from '@/store/blockStore';
import { useUIStore } from '@/store/uiStore';

interface Props {
  notebookId: string;
}

export function ChatPanel({ notebookId }: Props) {
  const blocks = useBlockStore((s) => s.blocks);
  const streaming = useBlockStore((s) => s.streaming);

  // Only render blocks destined for the Chat panel. Studio-targeted blocks
  // (LiteratureMatrix, KnowledgeGraphView, GapAnalysis, etc.) are routed to
  // StudioPanel via meta.panel — they must not appear here. FR-UI-04.
  const chatBlocks = blocks.filter((b) => b.meta?.panel !== 'studio');
  const hasStudioBlocks = blocks.some((b) => b.meta?.panel === 'studio');
  const lastError = useBlockStore((s) => s.lastError);
  const startTurn = useBlockStore((s) => s.startTurn);
  const pushBlock = useBlockStore((s) => s.pushBlock);
  const replaceBlockById = useBlockStore((s) => s.replaceBlockById);
  const setError = useBlockStore((s) => s.setError);
  const finishTurn = useBlockStore((s) => s.finishTurn);
  const activeMode = useUIStore((s) => s.activeMode);
  const queryDraft = useUIStore((s) => s.queryDraft);
  const setQueryDraft = useUIStore((s) => s.setQueryDraft);
  const setTrace = useUIStore((s) => s.setTrace);
  const clearTrace = useUIStore((s) => s.clearTrace);

  // When a generator tile fires a query, auto-fill the chat input and focus it.
  useEffect(() => {
    if (queryDraft) {
      setInput(queryDraft);
      setQueryDraft(null);
      document.getElementById('chat-input')?.focus();
    }
  }, [queryDraft, setQueryDraft]);

  const [input, setInput] = useState('');
  const [turnCount, setTurnCount] = useState(0);
  const [showSUS, setShowSUS] = useState(false);
  const [susShownOnce, setSusShownOnce] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  // Fetch suggested questions once — used in the empty-chat activation state.
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'}/suggestions`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { suggestions: string[] } | null) => {
        if (d?.suggestions?.length) setSuggestions(d.suggestions);
      })
      .catch(() => {});
  }, []);

  // Stable session ID for the lifetime of this component mount.
  const sessionId = useRef(crypto.randomUUID()).current;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || streaming) return;

    setInput('');
    clearTrace();
    startTurn();

    const optimisticId = `loading_${crypto.randomUUID()}`;
    const optimistic: CitedSummaryBlock = {
      type: 'CitedSummary',
      id: optimisticId,
      meta: { panel: 'chat', order: blocks.length, status: 'loading' },
      data: { summary: '', segments: [], citations: [] },
    };
    pushBlock(optimistic);

    let skeletonConsumed = false;

    await streamChat(
      { notebookId, message, history: [], activeMode },
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
              data: { ...optimistic.data, summary: err.error || 'Stream failed.' },
            });
            skeletonConsumed = true;
          }
        },
        onTrace: (t: PipelineTrace) => {
          setTrace(t);
        },
        onDone: () => {
          finishTurn();
          setTurnCount((n) => {
            const next = n + 1;
            if (next >= 5 && !susShownOnce) {
              setShowSUS(true);
              setSusShownOnce(true);
            }
            return next;
          });
        },
      },
    );

    if (useBlockStore.getState().streaming) {
      finishTurn();
    }
  }

  return (
    <main className="h-full flex flex-col bg-paper">
      <div className="px-4 py-3 border-b border-line flex items-center justify-between">
        <h2 className="font-display text-lg text-ink">Chat</h2>
      </div>

      <PipelineTraceComponent />
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {chatBlocks.length === 0 && hasStudioBlocks ? (
          <div className="py-12 text-center">
            <p className="text-sm text-ink-soft">
              {streaming
                ? 'Working — response streaming to Studio →'
                : 'Response generated in the Studio panel →'}
            </p>
          </div>
        ) : chatBlocks.length === 0 ? (
          <div className="flex flex-col items-center gap-6 py-10 px-4">
            <EmptyState
              title="Ask a question"
              hint="The research agent will ground its answer in your ingested documents and cite each claim."
            />
            {suggestions.length > 0 && (
              <div className="w-full max-w-lg flex flex-col gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.07em] text-ink-softer text-center mb-1">
                  Suggested questions
                </p>
                {suggestions.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setInput(q);
                      document.getElementById('chat-input')?.focus();
                    }}
                    className="text-left px-4 py-2.5 rounded-ctl border border-line bg-card hover:border-accent/60 hover:bg-accent/5 text-sm text-ink transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          chatBlocks.map((block) => (
            <div key={block.id}>
              {renderBlock(block)}
              <BlockFeedback
                blockId={block.id}
                blockType={block.type}
                sessionId={sessionId}
                ready={block.meta?.status === 'ready'}
              />
            </div>
          ))
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

      {showSUS && (
        <SUSModal sessionId={sessionId} onDismiss={() => setShowSUS(false)} />
      )}
    </main>
  );
}
