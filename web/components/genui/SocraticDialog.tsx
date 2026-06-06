// SocraticDialog — guided questioning that withholds answers.
// uiux_plan.md §4: Socratic mode, chat panel. FR-LRN-08.
// The `nextQuestion` from the tutor NEVER contains a direct answer.

import type { SocraticDialog as SocraticDialogBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: SocraticDialogBlock;
}

const BLOOM_STYLES: Record<string, string> = {
  recall:         'text-green bg-green-bg border-green/30',
  comprehension:  'text-accent bg-accent/10 border-accent/30',
  application:    'text-amber bg-amber-bg border-amber/30',
  analysis:       'text-violet bg-violet-bg border-violet/30',
  synthesis:      'text-violet bg-violet-bg border-violet/30',
  evaluation:     'text-red bg-red-bg border-red/30',
};

export function SocraticDialog({ block }: Props) {
  const { meta, data } = block;

  if (data.turns.length === 0 && meta.status === 'ready') {
    return (
      <EmptyState
        title="Start the dialogue"
        hint="Ask about a concept to begin Socratic questioning."
      />
    );
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Preparing a question for you…" rows={3} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not generate a probing question." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: SocraticDialogBlock }) {
  const { data } = block;
  const bloomStyle = BLOOM_STYLES[data.bloomLevel] ?? 'text-ink-soft border-line';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
          Socratic Dialogue
        </div>
        <span className={`px-2 py-0.5 text-xs font-mono rounded border ${bloomStyle}`}>
          {data.bloomLevel}
        </span>
      </div>

      <div className="text-sm font-medium text-ink">{data.concept}</div>

      {data.turns.length > 0 && (
        <div className="space-y-2 border-t border-line pt-3">
          {data.turns.map((turn, i) => (
            <div
              key={i}
              className={`flex gap-2 text-sm ${turn.role === 'tutor' ? 'justify-start' : 'justify-end'}`}
            >
              <div
                className={`max-w-[85%] rounded-card px-3 py-2 leading-relaxed font-serif ${
                  turn.role === 'tutor'
                    ? 'bg-accent/10 text-ink border border-accent/20'
                    : 'bg-paper text-ink-soft border border-line'
                }`}
              >
                {turn.text}
              </div>
            </div>
          ))}
        </div>
      )}

      {data.nextQuestion && (
        <div className="border border-accent/40 rounded-card px-3 py-2.5 bg-accent/5">
          <div className="text-xs font-mono uppercase text-accent tracking-wide mb-1">
            Next question
          </div>
          <p className="text-sm font-serif text-ink leading-relaxed">{data.nextQuestion}</p>
        </div>
      )}
    </div>
  );
}
