'use client';
import { useState } from 'react';

import type { DataTable as DataTableBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: DataTableBlock;
}

export function DataTable({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Building table..." rows={4} />;
  if (meta.status === 'error') return <ErrorState message="Could not build table." />;
  if (!data.rows.length && meta.status === 'ready') {
    return <EmptyState title="No data" hint="Ask a question that produces structured data." />;
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <Card>{body}</Card>;
}

function Body({ block }: { block: DataTableBlock }) {
  const { data } = block;
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  function handleSort(ci: number) {
    if (!data.columns[ci]?.sortable) return;
    if (sortCol === ci) {
      setSortAsc((prev) => !prev);
    } else {
      setSortCol(ci);
      setSortAsc(true);
    }
  }

  const rows =
    sortCol === null
      ? data.rows
      : [...data.rows].sort((a, b) => {
          const av = a.cells[sortCol] ?? '';
          const bv = b.cells[sortCol] ?? '';
          return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
        });

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium text-ink">{data.title}</div>
      <div className="overflow-x-auto rounded border border-line/40">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-surface-2 border-b border-line/40">
              {data.columns.map((col, ci) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(ci)}
                  className={[
                    'px-3 py-2 text-left font-mono text-ink-softer',
                    col.sortable ? 'cursor-pointer hover:text-ink select-none' : '',
                  ].join(' ')}
                >
                  {col.label}
                  {sortCol === ci && <span className="ml-1">{sortAsc ? '↑' : '↓'}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr
                key={ri}
                className="border-b border-line/20 hover:bg-surface-2/50 transition-colors last:border-0"
              >
                {row.cells.map((cell, ci) => (
                  <td key={ci} className="px-3 py-2 text-ink-soft">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.citations.length > 0 && (
        <ul className="space-y-1 text-xs text-ink-softer font-mono">
          {data.citations.map((c) => (
            <li key={c.id}>
              [{c.id}] {c.docTitle}
              {c.page != null ? ` · p.${c.page}` : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
