// FeynmanExplainer — simplified explanation + flagged gaps.
// uiux_plan.md §4: Study/Socratic mode, chat panel. FR-LRN-04.

import type { FeynmanExplainer as FeynmanExplainerBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: FeynmanExplainerBlock;
}

export function FeynmanExplainer({ block }: Props) {
  const { meta, data } = block;

  if (!data.concept && meta.status === 'ready') {
    return (
      <EmptyState
        title="Pick a concept"
        hint="Ask to explain a concept simply to see a Feynman-style breakdown."
      />
    );
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Simplifying the concept…" rows={4} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not generate the explanation." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: FeynmanExplainerBlock }) {
  const { data } = block;

  return (
    <div className="space-y-4">
      <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
        Feynman Explanation
      </div>

      <div className="text-sm font-medium text-ink">{data.concept}</div>

      <p className="text-sm font-serif text-ink leading-relaxed">{data.explanation}</p>

      {data.gaps.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-mono uppercase text-amber tracking-wide">
            Gaps to revisit
          </div>
          <ul className="space-y-1">
            {data.gaps.map((gap, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-soft">
                <span className="shrink-0 text-amber mt-0.5">•</span>
                <span className="leading-snug">{gap}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="text-xs font-mono text-ink-softer truncate">
        {data.source.docTitle}
        {data.source.page != null && ` · p.${data.source.page}`}
      </div>
    </div>
  );
}
