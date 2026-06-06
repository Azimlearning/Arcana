// GapAnalysis - shows knowledge gaps and covered topics.
// uiux_plan.md §4 catalog entry; PRD §16 payload GapAnalysisData.

import type { GapAnalysis as GapAnalysisBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: GapAnalysisBlock;
}

const SEVERITY_STYLES: Record<string, string> = {
  high: 'text-red border-red/60 bg-red-bg/20',
  medium: 'text-amber border-amber/60 bg-amber-bg/20',
  low: 'text-green border-green/60 bg-green-bg/20',
};

export function GapAnalysis({ block }: Props) {
  const { meta, data } = block;

  if (data.gaps.length === 0 && data.coveredTopics.length === 0 && meta.status === 'ready') {
    return <EmptyState title="No gaps identified" hint="The query is well-covered by your documents." />;
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Analysing knowledge gaps..." rows={4} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not complete gap analysis." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: GapAnalysisBlock }) {
  const { data } = block;

  return (
    <div className="space-y-4">
      <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
        Gap Analysis
      </div>
      <p className="text-sm text-ink-soft leading-relaxed">{data.summary}</p>
      {data.gaps.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">Gaps</div>
          {data.gaps.map((gap, i) => {
            const style = SEVERITY_STYLES[gap.severity] ?? 'text-ink-soft border-line';
            return (
              <div key={i} className={`pl-3 border-l-2 rounded-r py-1 ${style}`}>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{gap.label}</span>
                  <span className="text-xs font-mono uppercase tracking-wide opacity-70">
                    {gap.severity}
                  </span>
                </div>
                <p className="text-xs mt-0.5 opacity-80">{gap.description}</p>
              </div>
            );
          })}
        </div>
      )}
      {data.coveredTopics.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">Covered</div>
          <div className="flex flex-wrap gap-1.5">
            {data.coveredTopics.map((topic) => (
              <span
                key={topic}
                className="px-2 py-0.5 text-xs font-mono text-ink-soft bg-surface-2 rounded border border-line/50"
              >
                {topic}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
