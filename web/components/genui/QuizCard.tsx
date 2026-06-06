// QuizCard — MCQ / short-answer question item.
// uiux_plan.md §4: Study mode, chat panel. FR-LRN-03.

import type { QuizCard as QuizCardBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: QuizCardBlock;
}

const DIFFICULTY_STYLES: Record<string, string> = {
  recall:         'text-green bg-green-bg border-green/30',
  comprehension:  'text-accent bg-accent/10 border-accent/30',
  application:    'text-amber bg-amber-bg border-amber/30',
  analysis:       'text-violet bg-violet-bg border-violet/30',
};

export function QuizCard({ block }: Props) {
  const { meta, data } = block;

  if (!data.question && meta.status === 'ready') {
    return (
      <EmptyState
        title="No question yet"
        hint="Ask about a topic to generate a quiz question."
      />
    );
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Generating quiz question…" rows={4} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not generate the quiz question." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: QuizCardBlock }) {
  const { data } = block;
  const diffStyle = DIFFICULTY_STYLES[data.difficulty] ?? 'text-ink-soft border-line';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
          {data.questionType === 'mcq' ? 'Multiple Choice' : 'Short Answer'}
        </div>
        <span className={`px-2 py-0.5 text-xs font-mono rounded border ${diffStyle}`}>
          {data.difficulty}
        </span>
      </div>

      <p className="text-sm font-medium text-ink leading-snug">{data.question}</p>

      {data.questionType === 'mcq' && data.options.length > 0 && (
        <div className="space-y-1.5">
          {data.options.map((opt) => (
            <div
              key={opt.index}
              className="flex items-start gap-2.5 px-3 py-2 rounded border border-line text-sm text-ink-soft hover:border-accent/50 transition-colors cursor-default"
            >
              <span className="shrink-0 font-mono text-xs text-ink-softer mt-0.5">
                {String.fromCharCode(65 + opt.index)}.
              </span>
              <span className="leading-snug">{opt.text}</span>
            </div>
          ))}
        </div>
      )}

      {data.explanation && (
        <details className="text-xs text-ink-soft">
          <summary className="cursor-pointer font-mono uppercase tracking-wide text-ink-softer hover:text-ink transition-colors">
            Explanation
          </summary>
          <p className="mt-1.5 font-serif text-sm leading-relaxed">{data.explanation}</p>
        </details>
      )}

      <div className="text-xs font-mono text-ink-softer truncate">
        {data.source.docTitle}
        {data.source.page != null && ` · p.${data.source.page}`}
      </div>
    </div>
  );
}
