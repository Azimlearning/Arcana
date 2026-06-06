// DraftEditor — structured academic draft with cited sections.
// uiux_plan.md §4: Writing mode, chat panel. Writing Agent (PRD §12.5).

import type { DraftEditor as DraftEditorBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: DraftEditorBlock;
}

export function DraftEditor({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'error') {
    return <ErrorState message="Could not generate a draft." />;
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Drafting sections…" rows={5} />;
  }

  if (data.sections.length === 0) {
    return (
      <EmptyState
        title="Nothing drafted yet"
        hint="Describe what you want to write about to generate a draft."
      />
    );
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: DraftEditorBlock }) {
  const { data } = block;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-base font-serif font-semibold text-ink leading-snug">
          {data.title}
        </h2>
        <span className="shrink-0 text-xs font-mono text-ink-softer tabular-nums whitespace-nowrap">
          {data.wordCount} words
        </span>
      </div>

      <div className="space-y-4">
        {data.sections.map((section) => (
          <div key={section.heading} className="space-y-1.5">
            <h3 className="text-xs font-mono uppercase tracking-wide text-ink-soft">
              {section.heading}
            </h3>
            <p className="text-sm font-serif text-ink leading-relaxed">
              {section.body}
            </p>
          </div>
        ))}
      </div>

      {data.citations.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-xs font-mono text-accent tracking-wide select-none list-none flex items-center gap-1">
            <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
            {data.citations.length} source{data.citations.length !== 1 ? 's' : ''}
          </summary>
          <ol className="mt-2 space-y-1 pl-4">
            {data.citations.map((cit) => (
              <li key={cit.id} className="text-xs font-mono text-ink-softer">
                <span className="text-accent mr-1">[{cit.id}]</span>
                {cit.docTitle}
                {cit.page != null && `, p.${cit.page}`}
                {cit.quote && (
                  <span className="italic text-ink-softer"> — "{cit.quote}"</span>
                )}
              </li>
            ))}
          </ol>
        </details>
      )}
    </div>
  );
}
