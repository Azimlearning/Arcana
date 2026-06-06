// LiteratureMatrix - cross-document comparison table.
// uiux_plan.md §4 catalog entry; PRD §16 payload LiteratureMatrixData.
// Four states: loading (shimmer table), partial (streaming rows), ready, error.

import type { LiteratureMatrix as LiteratureMatrixBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: LiteratureMatrixBlock;
}

export function LiteratureMatrix({ block }: Props) {
  const { meta, data } = block;

  if (data.rows.length === 0 && meta.status === 'ready') {
    return <EmptyState title="No comparison data" hint="Run a multi-document query to compare results." />;
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Building comparison matrix..." rows={4} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not build the comparison matrix." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: LiteratureMatrixBlock }) {
  const { data } = block;

  return (
    <div className="space-y-3">
      <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
        Comparison Matrix
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-line">
              <th className="text-left font-mono text-ink-softer text-xs pr-4 py-2 whitespace-nowrap">
                Document
              </th>
              {data.dimensions.map((dim) => (
                <th
                  key={dim}
                  className="text-left font-mono text-ink-softer text-xs px-3 py-2 whitespace-nowrap"
                >
                  {dim}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.docId} className="border-b border-line/50 hover:bg-surface-2/30">
                <td className="pr-4 py-2 text-ink text-sm font-medium whitespace-nowrap align-top">
                  {row.docTitle}
                </td>
                {row.cells.map((cell, i) => (
                  <td key={i} className="px-3 py-2 text-ink-soft text-sm align-top">
                    {cell.text || <span className="text-ink-softer">&mdash;</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.query && (
        <div className="text-xs text-ink-softer font-mono">Query: {data.query}</div>
      )}
    </div>
  );
}
