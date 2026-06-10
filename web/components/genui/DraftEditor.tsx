'use client';

import { useState } from 'react';

import type { DraftEditor as DraftEditorBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';

import { EmptyState, ErrorState, LoadingState, PartialState } from './BlockStates';

export function DraftEditor({ block }: { block: DraftEditorBlock }) {
  const { meta, data } = block;
  const [copied, setCopied] = useState(false);

  if (meta.status === 'loading') return <LoadingState rows={6} caption="Drafting…" />;
  if (meta.status === 'error') return <ErrorState message="Draft failed" />;
  if (meta.status === 'partial') {
    return (
      <PartialState>
        {data.sections.map((s, i) => (
          <div key={i} className="mb-3">
            {s.heading && <h4 className="font-semibold text-ink text-sm mb-1">{s.heading}</h4>}
            <p className="text-sm text-ink leading-relaxed font-serif">{s.body}</p>
          </div>
        ))}
      </PartialState>
    );
  }

  function handleCopy() {
    const text = data.sections.map(s => `${s.heading ? s.heading + '\n' : ''}${s.body}`).join('\n\n');
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <Card>
      {/* header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold text-ink text-sm">{data.title}</h3>
          {data.wordCount != null && (
            <span className="text-xs text-ink-softer font-mono">{data.wordCount} words</span>
          )}
        </div>
        <button
          onClick={handleCopy}
          className="text-xs px-2 py-1 rounded border border-line text-ink-softer hover:text-ink hover:border-ink-softer transition-colors"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      {/* sections */}
      <div className="space-y-4">
        {data.sections.map((s, i) => (
          <div key={i}>
            {s.heading && (
              <h4 className="font-semibold text-ink text-sm mb-1">{s.heading}</h4>
            )}
            <p className="text-sm text-ink leading-relaxed font-serif">{s.body}</p>
          </div>
        ))}
      </div>

      {/* citations */}
      {data.citations && data.citations.length > 0 && (
        <details className="mt-4">
          <summary className="text-xs text-ink-softer cursor-pointer hover:text-ink select-none mb-1">
            {data.citations.length} source{data.citations.length !== 1 ? 's' : ''}
          </summary>
          <ol className="mt-1 space-y-0.5 pl-4 list-decimal">
            {data.citations.map((cit) => (
              <li key={cit.id} className="text-xs text-ink-softer font-mono">
                <span className="text-accent mr-1">[{cit.id}]</span>
                {cit.docTitle}
                {cit.page != null && `, p.${cit.page}`}
                {cit.quote && (
                  <span className="italic text-ink-softer"> &mdash; &ldquo;{cit.quote}&rdquo;</span>
                )}
              </li>
            ))}
          </ol>
        </details>
      )}
    </Card>
  );
}
