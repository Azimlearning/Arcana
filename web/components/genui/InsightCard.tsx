// InsightCard - a cross-document connection insight.
// uiux_plan.md §4 catalog entry; PRD §16 payload InsightCardData.

import type { InsightCard as InsightCardBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: InsightCardBlock;
}

export function InsightCard({ block }: Props) {
  const { meta, data } = block;

  if (!data.insight && meta.status === 'ready') {
    return <EmptyState title="No insight found" hint="Try a query that spans multiple documents." />;
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Surfacing insights..." rows={3} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not surface insights." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card className="border-green/30">{body}</Card>;
}

function Body({ block }: { block: InsightCardBlock }) {
  const { data } = block;

  return (
    <div className="space-y-3">
      <div className="text-xs font-mono uppercase text-green tracking-wide">Insight</div>
      <p className="text-sm text-ink leading-relaxed font-medium">{data.insight}</p>
      <p className="text-sm text-ink-soft leading-relaxed">{data.connection}</p>
      <div className="flex gap-3 pt-1">
        <div className="flex-1 px-3 py-2 bg-surface-2 rounded border border-line/50">
          <div className="text-xs font-mono text-ink-softer truncate">{data.docATitle}</div>
        </div>
        <div className="flex items-center text-ink-softer text-xs font-mono">&harr;</div>
        <div className="flex-1 px-3 py-2 bg-surface-2 rounded border border-line/50">
          <div className="text-xs font-mono text-ink-softer truncate">{data.docBTitle}</div>
        </div>
      </div>
      {data.citations.length > 0 && (
        <div className="pt-2 border-t border-line">
          <ul className="space-y-1 text-xs text-ink-softer font-mono">
            {data.citations.map((c) => (
              <li key={c.id}>
                [{c.id}] {c.docTitle}
                {c.page != null && ` &middot; p.${c.page}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
