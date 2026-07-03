// DOM tests for CitedSummary — all four states (NFR-USE-02, FR-UI-09) plus
// the §7.4 honest-degradation note when citations are empty.

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { CitedSummary as CitedSummaryBlock } from '@arcana/schema';

import { CitedSummary } from './CitedSummary';

function block(overrides: Partial<CitedSummaryBlock> = {}): CitedSummaryBlock {
  return {
    type: 'CitedSummary',
    id: 'b1',
    meta: { panel: 'chat', order: 0, status: 'ready' },
    data: {
      summary: 'Full summary text.',
      segments: [],
      citations: [],
    },
    ...overrides,
  } as CitedSummaryBlock;
}

describe('CitedSummary', () => {
  it('renders a loading skeleton', () => {
    render(<CitedSummary block={block({ meta: { panel: 'chat', order: 0, status: 'loading' } })} />);
    expect(screen.getByText(/Researching your documents/i)).toBeInTheDocument();
  });

  it('renders the error state with the summary as the message', () => {
    render(
      <CitedSummary
        block={block({
          meta: { panel: 'chat', order: 0, status: 'error' },
          data: { summary: 'The research agent failed.', segments: [], citations: [] },
        })}
      />
    );
    expect(screen.getByRole('alert')).toHaveTextContent('The research agent failed.');
  });

  it('wraps content in a partial-result banner while streaming', () => {
    render(
      <CitedSummary
        block={block({
          meta: { panel: 'chat', order: 0, status: 'partial' },
          data: { summary: 'Streaming in…', segments: [], citations: [] },
        })}
      />
    );
    expect(screen.getByText(/Partial result/i)).toBeInTheDocument();
    expect(screen.getByText('Streaming in…')).toBeInTheDocument();
  });

  it('renders segments with inline citation pills when ready', () => {
    render(
      <CitedSummary
        block={block({
          data: {
            summary: 'ignored when segments present',
            segments: [{ text: 'RAG improves grounding.', citationIds: ['c1'] }],
            citations: [
              { id: 'c1', docId: 'd1', docTitle: 'Paper A', page: 3, quote: 'quote text' },
            ],
          },
        })}
      />
    );
    expect(screen.getByText(/RAG improves grounding/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Citation c1/i })).toBeInTheDocument();
    expect(screen.getByText('Paper A')).toBeInTheDocument();
  });

  it('shows the §7.4 degradation note when ready with zero citations', () => {
    render(<CitedSummary block={block()} />);
    expect(
      screen.getByText(/No source citations found/i)
    ).toBeInTheDocument();
  });

  it('omits the degradation note when citations are present', () => {
    render(
      <CitedSummary
        block={block({
          data: {
            summary: 'x',
            segments: [{ text: 'x', citationIds: ['c1'] }],
            citations: [{ id: 'c1', docId: 'd1', docTitle: 'Paper A', page: null, quote: '' }],
          },
        })}
      />
    );
    expect(screen.queryByText(/No source citations found/i)).not.toBeInTheDocument();
  });
});
