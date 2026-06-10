import type { ConceptMap as ConceptMapBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: ConceptMapBlock;
}

export function ConceptMap({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Mapping concepts..." rows={5} />;
  if (meta.status === 'error') return <ErrorState message="Could not build concept map." />;
  if (!data.nodes.length && meta.status === 'ready') {
    return <EmptyState title="No concepts found" hint="Ask about a topic to generate a concept map." />;
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <Card className="border-accent/20">{body}</Card>;
}

const LEVEL_INDENT = ['', 'pl-4', 'pl-8'];
const LEVEL_TEXT = [
  'text-base font-semibold text-ink border-b border-line pb-2',
  'text-sm font-medium text-ink',
  'text-xs text-ink-soft',
];

function Body({ block }: { block: ConceptMapBlock }) {
  const { data } = block;

  const linksBySource: Record<string, typeof data.links> = {};
  for (const link of data.links) {
    if (!linksBySource[link.source]) linksBySource[link.source] = [];
    linksBySource[link.source].push(link);
  }

  const byLevel = [0, 1, 2].map((lvl) => data.nodes.filter((n) => n.level === lvl));

  return (
    <div className="space-y-4">
      <div className="text-xs font-mono uppercase text-accent tracking-wide">Concept Map</div>
      {byLevel[0].map((root) => (
        <div key={root.id} className="space-y-2">
          <div className={LEVEL_TEXT[0]}>{root.label}</div>
          {root.description && (
            <p className="text-xs text-ink-soft leading-relaxed">{root.description}</p>
          )}
          {byLevel[1].map((p1) => {
            const rootLinks = (linksBySource[root.id] ?? []).filter((l) => l.target === p1.id);
            return (
              <div key={p1.id} className={`space-y-1 ${LEVEL_INDENT[1]}`}>
                <div className={LEVEL_TEXT[1]}>
                  {rootLinks[0] && (
                    <span className="text-xs font-mono text-ink-softer mr-2 italic">
                      {rootLinks[0].label}
                    </span>
                  )}
                  {p1.label}
                </div>
                {p1.description && (
                  <p className="text-xs text-ink-softer leading-relaxed pl-2">{p1.description}</p>
                )}
                {byLevel[2]
                  .filter((s) => (linksBySource[p1.id] ?? []).some((l) => l.target === s.id))
                  .map((s) => {
                    const p1Links = (linksBySource[p1.id] ?? []).filter((l) => l.target === s.id);
                    return (
                      <div key={s.id} className={`${LEVEL_TEXT[2]} ${LEVEL_INDENT[2]}`}>
                        {p1Links[0] && (
                          <span className="text-xs font-mono text-ink-softer mr-2 italic">
                            {p1Links[0].label}
                          </span>
                        )}
                        {s.label}
                      </div>
                    );
                  })}
              </div>
            );
          })}
        </div>
      ))}
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
