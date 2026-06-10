import type { ComparisonChart as ComparisonChartBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: ComparisonChartBlock;
}

export function ComparisonChart({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Generating comparison..." rows={4} />;
  if (meta.status === 'error') return <ErrorState message="Could not generate chart." />;
  if (!data.series.length && meta.status === 'ready') {
    return <EmptyState title="No data to compare" hint="Ask a question that compares multiple items." />;
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <Card>{body}</Card>;
}

const SERIES_BG = ['bg-accent', 'bg-green-500', 'bg-violet', 'bg-amber-500'] as const;
const SERIES_TEXT = ['text-accent', 'text-green-600', 'text-violet', 'text-amber-600'] as const;

function Body({ block }: { block: ComparisonChartBlock }) {
  const { data } = block;
  const allValues = data.series.flatMap((s) => s.values);
  const maxVal = Math.max(...allValues, 1);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">Comparison</div>
          <div className="text-sm font-medium text-ink mt-0.5">{data.title}</div>
        </div>
        {data.unit && <span className="text-xs font-mono text-ink-softer">{data.unit}</span>}
      </div>
      <div className="flex flex-wrap gap-3">
        {data.series.map((s, i) => (
          <div key={s.name} className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-sm ${SERIES_BG[i % SERIES_BG.length]}`} />
            <span className={`text-xs font-mono ${SERIES_TEXT[i % SERIES_TEXT.length]}`}>{s.name}</span>
          </div>
        ))}
      </div>
      <div className="space-y-4">
        {data.labels.map((label, li) => (
          <div key={label} className="space-y-1.5">
            <div className="text-xs text-ink-soft font-mono">{label}</div>
            {data.series.map((s, si) => {
              const val = s.values[li] ?? 0;
              const pct = Math.round((val / maxVal) * 100);
              return (
                <div key={s.name} className="flex items-center gap-2">
                  <div className="flex-1 h-4 bg-surface-2 rounded overflow-hidden">
                    <div
                      className={`h-full transition-all ${SERIES_BG[si % SERIES_BG.length]} opacity-80`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono text-ink-softer w-10 text-right">{val}</span>
                </div>
              );
            })}
          </div>
        ))}
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
