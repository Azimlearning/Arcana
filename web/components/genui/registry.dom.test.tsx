// DOM smoke test for the registry dispatch (renderBlock) — separate from
// registry.test.ts's node-only type-coverage check. Confirms every kind
// actually mounts to real DOM output via the single dispatch point
// (invariant #3: only the registry ever picks a renderer).

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { UIBlock } from '@arcana/schema';

import { renderBlock } from './registry';

describe('renderBlock (DOM dispatch)', () => {
  it('mounts a CitedSummary block by its type discriminator', () => {
    const block: UIBlock = {
      type: 'CitedSummary',
      id: 'b1',
      meta: { panel: 'chat', order: 0, status: 'ready' },
      data: { summary: 'Grounded answer text.', segments: [], citations: [] },
    };
    render(<div>{renderBlock(block)}</div>);
    expect(screen.getByText(/No source citations found/i)).toBeInTheDocument();
  });

  it('mounts the newly-registered PlagiarismReport and AudioSummary kinds', () => {
    const plagiarism: UIBlock = {
      type: 'PlagiarismReport',
      id: 'b2',
      meta: { panel: 'studio', order: 0, status: 'ready' },
      data: {
        draftTitle: 'Essay',
        originalityScore: 1,
        aiLikelihood: 0,
        flags: [],
        checkedAt: '2026-07-03T00:00:00+00:00',
        citations: [],
      },
    };
    const { unmount } = render(<div>{renderBlock(plagiarism)}</div>);
    expect(screen.getByText('Essay')).toBeInTheDocument();
    unmount();

    const audio: UIBlock = {
      type: 'AudioSummary',
      id: 'b3',
      meta: { panel: 'studio', order: 0, status: 'ready' },
      data: {
        title: 'Overview',
        audioUrl: null,
        durationSec: 0,
        transcript: '',
        segments: [],
        voice: null,
        citations: [],
      },
    };
    render(<div>{renderBlock(audio)}</div>);
    expect(screen.getByText(/No audio overview yet/i)).toBeInTheDocument();
  });

  it('renders an error tile for an unregistered/unknown type instead of throwing', () => {
    const bogus = {
      type: 'NotARealBlockType',
      id: 'b4',
      meta: { panel: 'chat', order: 0, status: 'ready' },
      data: {},
    } as unknown as UIBlock;
    render(<div>{renderBlock(bogus)}</div>);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
