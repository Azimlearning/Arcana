import type { ProgressDashboard as ProgressDashboardBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: ProgressDashboardBlock;
}

export function ProgressDashboard({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Loading progress..." rows={4} />;
  if (meta.status === 'error') return <ErrorState message="Could not load progress." />;
  if (!data.totalCards && meta.status === 'ready') {
    return <EmptyState title="No progress yet" hint="Generate flashcards to start tracking your progress." />;
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <Card className="border-green-500/20">{body}</Card>;
}

function Body({ block }: { block: ProgressDashboardBlock }) {
  const { data } = block;
  const masteryPct = data.totalCards > 0 ? Math.round((data.masteredCards / data.totalCards) * 100) : 0;

  return (
    <div className="space-y-4">
      <div className="text-xs font-mono uppercase text-green-600 tracking-wide">Progress</div>
      <div className="grid grid-cols-3 gap-3">
        {(
          [
            { label: 'Total cards', value: String(data.totalCards) },
            { label: 'Mastered', value: `${data.masteredCards} (${masteryPct}%)` },
            { label: 'Streak', value: `${data.streakDays}d` },
          ] as const
        ).map(({ label, value }) => (
          <div key={label} className="px-3 py-2 bg-surface-2 rounded border border-line/40 text-center">
            <div className="text-lg font-semibold text-ink">{value}</div>
            <div className="text-xs text-ink-softer font-mono mt-0.5">{label}</div>
          </div>
        ))}
      </div>
      <div className="space-y-1">
        <div className="flex justify-between text-xs font-mono text-ink-softer">
          <span>Overall mastery</span>
          <span>{masteryPct}%</span>
        </div>
        <div className="h-2 bg-surface-2 rounded overflow-hidden">
          {/* dynamic width from data — cannot be expressed as a fixed CSS class */}
          <div className="h-full bg-green-500 transition-all" style={{ width: `${masteryPct}%` }} />
        </div>
      </div>
      {data.topics.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-mono text-ink-softer uppercase tracking-wide">By topic</div>
          {data.topics.map((t) => {
            const pct = t.totalCards > 0 ? Math.round((t.masteredCards / t.totalCards) * 100) : 0;
            return (
              <div key={t.topic} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-ink-soft truncate">{t.topic}</span>
                  <span className="font-mono text-ink-softer ml-2 shrink-0">
                    {t.masteredCards}/{t.totalCards}
                    {t.dueCount > 0 && (
                      <span className="text-amber-600 ml-1">({t.dueCount} due)</span>
                    )}
                  </span>
                </div>
                <div className="h-1 bg-surface-2 rounded overflow-hidden">
                  {/* dynamic width from data — cannot be expressed as a fixed CSS class */}
                  <div className="h-full bg-green-500/60 transition-all" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
      {data.nextReviewAt && (
        <div className="text-xs text-ink-softer font-mono border-t border-line pt-2">
          Next review: {data.nextReviewAt}
        </div>
      )}
    </div>
  );
}
