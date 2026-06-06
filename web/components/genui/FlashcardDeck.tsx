// FlashcardDeck — active-recall cards with SR scheduling.
// uiux_plan.md §4: Study mode, chat/studio panel. FR-LRN-01, FR-LRN-02.

import type { FlashcardDeck as FlashcardDeckBlock, Flashcard } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: FlashcardDeckBlock;
}

export function FlashcardDeck({ block }: Props) {
  const { meta, data } = block;

  if (data.cards.length === 0 && meta.status === 'ready') {
    return (
      <EmptyState
        title="No flashcards yet"
        hint="Ask about a topic in Study mode to generate a deck."
      />
    );
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Generating flashcards…" rows={5} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not generate flashcards." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: FlashcardDeckBlock }) {
  const { data } = block;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
          Flashcard Deck
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-ink-soft">
            {data.totalCards} card{data.totalCards !== 1 ? 's' : ''}
          </span>
          {data.dueCount > 0 && (
            <span className="px-2 py-0.5 text-xs font-mono text-amber bg-amber-bg rounded border border-amber/30">
              {data.dueCount} due
            </span>
          )}
        </div>
      </div>

      <div className="text-sm font-medium text-ink">{data.topic}</div>

      <div className="space-y-2">
        {data.cards.map((card, i) => (
          <FlashcardItem key={i} card={card} index={i} />
        ))}
      </div>
    </div>
  );
}

function FlashcardItem({ card, index }: { card: Flashcard; index: number }) {
  return (
    <div className="rounded-card border border-line bg-paper p-3 space-y-2">
      <div className="flex items-start gap-2">
        <span className="shrink-0 text-xs font-mono text-ink-softer mt-0.5">
          {String(index + 1).padStart(2, '0')}
        </span>
        <div className="flex-1 space-y-1.5">
          <div className="text-sm font-medium text-ink leading-snug">{card.front}</div>
          <div className="text-sm font-serif text-ink-soft leading-relaxed border-t border-line/50 pt-1.5">
            {card.back}
          </div>
        </div>
      </div>
      <div className="text-xs font-mono text-ink-softer truncate pl-6">
        {card.source.docTitle}
        {card.source.page != null && ` · p.${card.source.page}`}
      </div>
    </div>
  );
}
