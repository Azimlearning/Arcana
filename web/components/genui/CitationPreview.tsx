'use client';
import { useState } from 'react';

import type { CitationPreview as CitationPreviewBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: CitationPreviewBlock;
}

export function CitationPreview({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Formatting citation..." rows={2} />;
  if (meta.status === 'error') return <ErrorState message="Could not format citation." />;
  if (!data.formatted && meta.status === 'ready') {
    return <EmptyState title="No citation" hint="Ask for a citation to a specific document." />;
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <Card>{body}</Card>;
}

function Body({ block }: { block: CitationPreviewBlock }) {
  const { data } = block;
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(data.formatted).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono uppercase text-ink-softer tracking-wide">
          Citation &middot; {data.style.toUpperCase()}
        </span>
        <button
          onClick={handleCopy}
          className="text-xs font-mono px-2 py-1 rounded bg-surface-2 border border-line/50 text-ink-soft hover:text-ink transition-colors"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <p className="text-sm text-ink leading-relaxed font-serif">{data.formatted}</p>
      {data.authors.length > 0 && (
        <div className="text-xs text-ink-softer font-mono">
          {data.authors.join('; ')}
          {data.year ? ` (${data.year})` : ''}
        </div>
      )}
      {data.sourceUri && (
        <a
          href={data.sourceUri}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-accent font-mono hover:underline truncate block"
        >
          {data.sourceUri}
        </a>
      )}
    </div>
  );
}
