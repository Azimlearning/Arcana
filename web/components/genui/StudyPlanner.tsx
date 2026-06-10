// StudyPlanner — SM-2 due-card queue + session stats.
// uiux_plan.md §4: Study mode, studio panel. FR-LRN-09, FR-LRN-10.

import type { StudyPlanner as StudyPlannerBlock, DueCard } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: StudyPlannerBlock;
}

export function StudyPlanner({ block }: Props) {
  const { meta, data } = block;

  if (data.totalDue === 0 && meta.status === 'ready') {
    return (
      <EmptyState
        title="Queue is clear"
        hint={
          data.nextSessionAt
            ? `Next review due on ${formatDate(data.nextSessionAt)}.`
            : 'Generate flashcards in Study mode to build your queue.'
        }
      />
    );
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Loading study queue…" rows={6} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not load the study planner." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: StudyPlannerBlock }) {
  const { data } = block;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
          Study Planner
        </div>
        {data.overdueCount > 0 && (
          <span className="px-2 py-0.5 text-xs font-mono text-red bg-red-bg rounded border border-red/30">
            {data.overdueCount} overdue
          </span>
        )}
      </div>

      <div className="flex items-end gap-4">
        <div>
          <div className="text-2xl font-display font-semibold text-ink leading-none">
            {data.totalDue}
          </div>
          <div className="text-xs font-mono text-ink-soft mt-0.5">cards due</div>
        </div>
        <div>
          <div className="text-2xl font-display font-semibold text-accent leading-none">
            {data.sessionGoal}
          </div>
          <div className="text-xs font-mono text-ink-soft mt-0.5">session goal</div>
        </div>
        {data.nextSessionAt && (
          <div className="ml-auto text-right">
            <div className="text-xs font-mono text-ink-softer">next due</div>
            <div className="text-xs font-mono text-ink-soft">{formatDate(data.nextSessionAt)}</div>
          </div>
        )}
      </div>

      <div className="space-y-1.5 border-t border-line pt-3">
        {data.dueCards.slice(0, data.sessionGoal).map((card) => (
          <DueCardRow key={card.cardId} card={card} />
        ))}
        {data.totalDue > data.sessionGoal && (
          <div className="text-xs font-mono text-ink-softer pt-1 text-center">
            +{data.totalDue - data.sessionGoal} more cards
          </div>
        )}
      </div>
    </div>
  );
}

function DueCardRow({ card }: { card: DueCard }) {
  return (
    <div className="flex items-center gap-3 rounded-card border border-line bg-paper px-3 py-2">
      <span
        className={`shrink-0 w-1.5 h-1.5 rounded-full ${card.overdue ? 'bg-red' : 'bg-amber'}`}
        aria-label={card.overdue ? 'overdue' : 'due'}
      />
      <div className="flex-1 min-w-0">
        <div className="text-sm text-ink truncate">{card.front}</div>
        <div className="text-xs font-mono text-ink-softer truncate">{card.topic}</div>
      </div>
      <div className="shrink-0 text-xs font-mono text-ink-softer">
        {card.overdue ? 'overdue' : formatDate(card.dueAt)}
      </div>
    </div>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
