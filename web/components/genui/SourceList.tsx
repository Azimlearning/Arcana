import type { SourceList as SourceListBlock } from '@arcana/schema';

import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: SourceListBlock;
}

export function SourceList({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Loading sources..." rows={4} />;
  if (meta.status === 'error') return <ErrorState message="Could not load sources." />;
  if (!data.documents.length && meta.status === 'ready') {
    return <EmptyState title="No documents yet" hint="Upload a PDF or paste a URL to get started." />;
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <>{body}</>;
}

const STATUS_STYLES: Record<string, string> = {
  ready: 'text-green-600 bg-green-50',
  parsing: 'text-amber-600 bg-amber-50',
  embedding: 'text-amber-600 bg-amber-50',
  pending: 'text-gray-500 bg-gray-100',
  failed: 'text-red-600 bg-red-50',
};

function Body({ block }: { block: SourceListBlock }) {
  const { data } = block;
  return (
    <div className="space-y-2">
      <div className="text-xs font-mono uppercase text-ink-softer tracking-wide mb-3">
        {data.totalCount} document{data.totalCount !== 1 ? 's' : ''}
      </div>
      {data.documents.map((doc) => (
        <div
          key={doc.docId}
          className="flex items-start gap-3 px-3 py-2 rounded bg-surface-2 border border-line/40"
        >
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-ink truncate">{doc.title}</div>
            <div className="text-xs text-ink-softer font-mono truncate mt-0.5">{doc.sourceUri}</div>
            {doc.error && (
              <div className="text-xs text-red-600 mt-1 font-mono">{doc.error}</div>
            )}
          </div>
          <div className="shrink-0 flex flex-col items-end gap-1">
            <span
              className={`text-xs font-mono px-2 py-0.5 rounded-full ${STATUS_STYLES[doc.status] ?? STATUS_STYLES['pending']}`}
            >
              {doc.status}
            </span>
            {doc.status === 'ready' && (
              <span className="text-xs text-ink-softer font-mono">{doc.chunkCount}c</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
