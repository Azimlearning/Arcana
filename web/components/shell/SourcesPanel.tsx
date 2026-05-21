'use client';

import { Card } from '@/components/ui/Card';

/** Slice scope: hardcoded "demo corpus" listing. The real ingestion-
 *  driven source list (FR-USR-03 + ingestion progress + per-doc status)
 *  lands in subsystem 10 (Makefile ingest-demo) and P1 (Ingestion UI). */
export function SourcesPanel() {
  return (
    <aside className="h-full flex flex-col border-r border-line bg-paper">
      <div className="px-4 py-3 border-b border-line">
        <h2 className="font-display text-lg text-ink">Sources</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <Card className="p-3 text-sm">
          <div className="font-medium text-ink">Demo corpus</div>
          <div className="text-xs text-ink-softer mt-1">
            Drop a PDF into <code className="font-mono">eval/corpus/</code> and
            run <code className="font-mono">make ingest-demo</code>.
          </div>
        </Card>
      </div>
    </aside>
  );
}
