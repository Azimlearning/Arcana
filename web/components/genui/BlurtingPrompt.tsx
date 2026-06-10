'use client';
// BlurtingPrompt — free-recall prompt with a reveal-passage toggle.
// uiux_plan.md §4: Study/Learning mode, chat panel. FR-LRN-06.

import { useState } from 'react';

import type { BlurtingPrompt as BlurtingPromptBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: BlurtingPromptBlock;
}

export function BlurtingPrompt({ block }: Props) {
  const { meta, data } = block;

  if (!data.prompt && meta.status === 'ready') {
    return (
      <EmptyState
        title="Ready to blurt?"
        hint="Ask to practise a topic in Study mode to get a free-recall prompt."
      />
    );
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Preparing blurting prompt…" rows={4} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not generate a blurting prompt." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: BlurtingPromptBlock }) {
  const { data } = block;
  const [revealed, setRevealed] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
          Blurting Prompt
        </div>
        <span className="px-2 py-0.5 text-xs font-mono text-accent bg-accent/10 rounded border border-accent/30">
          {data.topic}
        </span>
      </div>

      <div className="rounded-card border border-accent/30 bg-accent/5 px-4 py-3">
        <p className="text-sm font-serif text-ink leading-relaxed">{data.prompt}</p>
      </div>

      <div className="space-y-2">
        <Button
          variant="ghost"
          onClick={() => setRevealed((v) => !v)}
          className="text-xs font-mono"
        >
          {revealed ? 'Hide source passage' : 'Reveal source passage'}
        </Button>

        {revealed && (
          <div className="rounded-card border border-line bg-paper px-4 py-3 space-y-3">
            <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
              Source passage
            </div>
            <p className="text-sm font-serif text-ink-soft leading-relaxed">
              {data.sourcePassage}
            </p>
            {data.citations.length > 0 && (
              <div className="border-t border-line pt-2 space-y-1">
                {data.citations.map((c) => (
                  <div key={c.id} className="text-xs font-mono text-ink-softer truncate">
                    {c.docTitle}
                    {c.page != null && ` · p.${c.page}`}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
