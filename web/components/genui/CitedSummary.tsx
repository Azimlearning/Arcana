// CitedSummary - the slice's only catalog component.
// docs/uiux_plan.md §5 catalog entry; PRD §16.1 payload.
//
// All four states wired via `meta.status`:
//   - 'loading' → shimmer skeleton matching the final shape
//   - 'partial' → render whatever segments are present so far
//   - 'ready'   → final render
//   - 'error'   → error state with the summary as the human message

import type { CitedSummary as CitedSummaryBlock } from '@arcana/schema';

import { CitationPill } from '@/components/ui/CitationPill';
import { Card } from '@/components/ui/Card';
import { ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: CitedSummaryBlock;
}

export function CitedSummary({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') {
    return <LoadingState caption="Researching your documents…" rows={5} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message={data.summary || 'The research agent failed.'} />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: CitedSummaryBlock }) {
  const { data } = block;
  const citationsById = new Map(data.citations.map((c) => [c.id, c]));

  return (
    <div className="space-y-4">
      <div className="font-serif text-ink leading-relaxed text-base">
        {data.segments.length > 0 ? (
          data.segments.map((seg, i) => (
            <span key={i}>
              {seg.text}{' '}
              {seg.citationIds.map((cid) => {
                const cit = citationsById.get(cid);
                if (!cit) return null;
                return (
                  <CitationPill
                    key={cid}
                    id={cit.id}
                    docTitle={cit.docTitle}
                    page={cit.page}
                    quote={cit.quote}
                  />
                );
              })}
              {i < data.segments.length - 1 && ' '}
            </span>
          ))
        ) : (
          <span className="text-ink-soft">{data.summary}</span>
        )}
      </div>

      {data.citations.length > 0 && (
        <div className="pt-3 border-t border-line">
          <div className="text-xs font-mono uppercase text-ink-softer tracking-wide mb-2">
            Sources
          </div>
          <ul className="space-y-1.5 text-sm text-ink-soft">
            {data.citations.map((c) => (
              <li key={c.id} className="flex gap-2">
                <span className="font-mono text-xs text-green pt-0.5">[{c.id}]</span>
                <span>
                  <span className="text-ink">{c.docTitle}</span>
                  {c.page != null && <span className="text-ink-softer"> · page {c.page}</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
