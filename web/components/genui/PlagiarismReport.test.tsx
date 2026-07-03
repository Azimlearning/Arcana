import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { PlagiarismReport as PlagiarismReportBlock } from '@arcana/schema';

import { PlagiarismReport } from './PlagiarismReport';

function block(overrides: Partial<PlagiarismReportBlock> = {}): PlagiarismReportBlock {
  return {
    type: 'PlagiarismReport',
    id: 'b1',
    meta: { panel: 'studio', order: 0, status: 'ready' },
    data: {
      draftTitle: 'My essay',
      originalityScore: 0.9,
      aiLikelihood: 0.05,
      flags: [],
      checkedAt: '2026-07-03T00:00:00+00:00',
      citations: [],
    },
    ...overrides,
  } as PlagiarismReportBlock;
}

describe('PlagiarismReport', () => {
  it('shows a loading skeleton', () => {
    render(<PlagiarismReport block={block({ meta: { panel: 'studio', order: 0, status: 'loading' } })} />);
    expect(screen.getByText(/Checking originality/i)).toBeInTheDocument();
  });

  it('shows the error state', () => {
    render(<PlagiarismReport block={block({ meta: { panel: 'studio', order: 0, status: 'error' } })} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/Originality check failed/i);
  });

  it('shows the empty state when ready with no title or flags', () => {
    render(<PlagiarismReport block={block({ data: { ...block().data, draftTitle: '' } })} />);
    expect(screen.getByText(/Nothing to check/i)).toBeInTheDocument();
  });

  it('renders scores and a no-overlap message when there are no flags', () => {
    render(<PlagiarismReport block={block()} />);
    expect(screen.getByText('My essay')).toBeInTheDocument();
    expect(screen.getByText('90%')).toBeInTheDocument(); // originality
    expect(screen.getByText(/No overlapping passages found/i)).toBeInTheDocument();
  });

  it('lists flagged passages with their match source and similarity', () => {
    render(
      <PlagiarismReport
        block={block({
          data: {
            draftTitle: 'My essay',
            originalityScore: 0.4,
            aiLikelihood: 0.2,
            flags: [
              {
                excerpt: 'the quick brown fox',
                matchSource: 'Paper A',
                docId: 'd1',
                similarity: 0.6,
                flagKind: 'similarity',
              },
            ],
            checkedAt: '2026-07-03T00:00:00+00:00',
            citations: [],
          },
        })}
      />
    );
    expect(screen.getByText('Paper A')).toBeInTheDocument();
    expect(screen.getByText(/the quick brown fox/i)).toBeInTheDocument();
    expect(screen.getByText(/60%/)).toBeInTheDocument();
  });
});
