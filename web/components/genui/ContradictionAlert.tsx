// ContradictionAlert - highlights conflicting claims across documents.
// uiux_plan.md §4 catalog entry; PRD §16 payload ContradictionAlertData.

import type { ContradictionAlert as ContradictionAlertBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: ContradictionAlertBlock;
}

export function ContradictionAlert({ block }: Props) {
  const { meta, data } = block;

  if (data.claims.length === 0 && meta.status === 'ready') {
    return <EmptyState title="No contradictions found" hint="The documents appear to be consistent on this topic." />;
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Checking for contradictions..." rows={3} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not check for contradictions." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card className="border-amber/40">{body}</Card>;
}

function Body({ block }: { block: ContradictionAlertBlock }) {
  const { data } = block;

  return (
    <div className="space-y-3">
      <div className="text-xs font-mono uppercase text-amber tracking-wide">
        Contradiction Alert
      </div>
      <div className="text-sm font-medium text-ink">{data.concept}</div>
      <p className="text-sm text-ink-soft leading-relaxed">{data.summary}</p>
      <div className="space-y-2 pt-1">
        {data.claims.map((claim, i) => (
          <div key={i} className="pl-3 border-l-2 border-amber/60 space-y-0.5">
            <div className="text-xs font-mono text-ink-softer">{claim.docTitle}</div>
            <div className="text-xs font-medium text-amber uppercase tracking-wide">
              {claim.stance}
            </div>
            <blockquote className="text-sm text-ink-soft italic">&ldquo;{claim.quote}&rdquo;</blockquote>
          </div>
        ))}
      </div>
    </div>
  );
}
