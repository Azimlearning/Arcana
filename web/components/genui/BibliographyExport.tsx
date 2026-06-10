'use client';
import { useState } from 'react';

import type { BibliographyExport as BibliographyExportBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: BibliographyExportBlock;
}

export function BibliographyExport({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Building bibliography..." rows={4} />;
  if (meta.status === 'error') return <ErrorState message="Could not build bibliography." />;
  if (!data.entries.length && meta.status === 'ready') {
    return <EmptyState title="No references" hint="Ask about documents to generate a bibliography." />;
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <Card className="border-violet/20">{body}</Card>;
}

function Body({ block }: { block: BibliographyExportBlock }) {
  const { data } = block;
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  function handleCopyAll() {
    navigator.clipboard.writeText(data.bibtexAll).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  function toggleEntry(key: string) {
    setExpanded((prev) => (prev === key ? null : key));
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono uppercase text-violet tracking-wide">Bibliography</span>
        <button
          onClick={handleCopyAll}
          className="text-xs font-mono px-2 py-1 rounded bg-surface-2 border border-line/50 text-ink-soft hover:text-ink transition-colors"
        >
          {copied ? 'Copied!' : 'Copy BibTeX'}
        </button>
      </div>
      <div className="space-y-1">
        {data.entries.map((entry) => (
          <div key={entry.key} className="rounded border border-line/40 bg-surface-2">
            <button
              onClick={() => toggleEntry(entry.key)}
              className="w-full flex items-center justify-between px-3 py-2 text-left"
            >
              <div className="min-w-0">
                <span className="text-xs font-mono text-accent mr-2">{entry.key}</span>
                <span className="text-sm text-ink truncate">{entry.docTitle}</span>
              </div>
              <span className="text-ink-softer text-xs ml-2 shrink-0">
                {expanded === entry.key ? '▲' : '▼'}
              </span>
            </button>
            {expanded === entry.key && (
              <pre className="px-3 pb-3 text-xs font-mono text-ink-soft whitespace-pre-wrap break-all border-t border-line/40">
                {entry.bibtex}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
