import type { Timeline as TimelineBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: TimelineBlock;
}

export function Timeline({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Building timeline..." rows={5} />;
  if (meta.status === 'error') return <ErrorState message="Could not build timeline." />;
  if (!data.events.length && meta.status === 'ready') {
    return <EmptyState title="No events found" hint="Ask about a topic's history to generate a timeline." />;
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <Card className="border-amber-500/20">{body}</Card>;
}

function Body({ block }: { block: TimelineBlock }) {
  const { data } = block;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono uppercase text-amber-600 tracking-wide">Timeline</span>
        <span className="text-sm font-medium text-ink">{data.title}</span>
      </div>
      <div className="relative pl-4">
        <div className="absolute left-0 top-2 bottom-2 w-px bg-line" />
        <div className="space-y-4">
          {data.events.map((event, i) => (
            <div key={i} className="relative pl-6">
              <div className="absolute left-0 top-1.5 w-2 h-2 rounded-full bg-amber-500 -translate-x-[3px] border-2 border-surface" />
              <div className="text-xs font-mono text-amber-600 mb-0.5">{event.date}</div>
              <div className="text-sm font-medium text-ink">{event.label}</div>
              {event.description && (
                <p className="text-xs text-ink-soft leading-relaxed mt-1">{event.description}</p>
              )}
            </div>
          ))}
        </div>
      </div>
      {data.citations.length > 0 && (
        <div className="pt-2 border-t border-line">
          <ul className="space-y-1 text-xs text-ink-softer font-mono">
            {data.citations.map((c) => (
              <li key={c.id}>
                [{c.id}] {c.docTitle}
                {c.page != null ? ` · p.${c.page}` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
