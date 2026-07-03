import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { FlashcardDeck as FlashcardDeckBlock } from '@arcana/schema';

import { FlashcardDeck } from './FlashcardDeck';

function block(overrides: Partial<FlashcardDeckBlock> = {}): FlashcardDeckBlock {
  return {
    type: 'FlashcardDeck',
    id: 'b1',
    meta: { panel: 'chat', order: 0, status: 'ready' },
    data: {
      topic: 'Attention mechanisms',
      totalCards: 0,
      dueCount: 0,
      cards: [],
    },
    ...overrides,
  } as FlashcardDeckBlock;
}

describe('FlashcardDeck', () => {
  it('shows the empty state when ready with no cards', () => {
    render(<FlashcardDeck block={block()} />);
    expect(screen.getByText(/No flashcards yet/i)).toBeInTheDocument();
  });

  it('shows a loading skeleton', () => {
    render(<FlashcardDeck block={block({ meta: { panel: 'chat', order: 0, status: 'loading' } })} />);
    expect(screen.getByText(/Generating flashcards/i)).toBeInTheDocument();
  });

  it('shows the error state', () => {
    render(<FlashcardDeck block={block({ meta: { panel: 'chat', order: 0, status: 'error' } })} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/Could not generate flashcards/i);
  });

  it('renders every card front/back and the due-count badge', () => {
    render(
      <FlashcardDeck
        block={block({
          data: {
            topic: 'Attention mechanisms',
            totalCards: 2,
            dueCount: 1,
            cards: [
              {
                front: 'What is self-attention?',
                back: 'A mechanism relating positions of one sequence.',
                source: { id: 'c1', docId: 'd1', docTitle: 'Paper A', page: 4, quote: '' },
                schedule: null,
              },
              {
                front: 'What is multi-head attention?',
                back: 'Running attention in parallel subspaces.',
                source: { id: 'c2', docId: 'd1', docTitle: 'Paper A', page: 5, quote: '' },
                schedule: null,
              },
            ],
          },
        })}
      />
    );
    expect(screen.getByText('What is self-attention?')).toBeInTheDocument();
    expect(screen.getByText('What is multi-head attention?')).toBeInTheDocument();
    expect(screen.getByText('2 cards')).toBeInTheDocument();
    expect(screen.getByText('1 due')).toBeInTheDocument();
  });
});
