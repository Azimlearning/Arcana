import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { AudioSummary as AudioSummaryBlock } from '@arcana/schema';

import { AudioSummary } from './AudioSummary';

function block(overrides: Partial<AudioSummaryBlock> = {}): AudioSummaryBlock {
  return {
    type: 'AudioSummary',
    id: 'b1',
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
    ...overrides,
  } as AudioSummaryBlock;
}

describe('AudioSummary', () => {
  it('shows a loading skeleton', () => {
    render(<AudioSummary block={block({ meta: { panel: 'studio', order: 0, status: 'loading' } })} />);
    expect(screen.getByText(/Preparing audio overview/i)).toBeInTheDocument();
  });

  it('shows the error state', () => {
    render(<AudioSummary block={block({ meta: { panel: 'studio', order: 0, status: 'error' } })} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/Audio overview failed/i);
  });

  it('shows the empty state when ready with no transcript or audio', () => {
    render(<AudioSummary block={block()} />);
    expect(screen.getByText(/No audio overview yet/i)).toBeInTheDocument();
  });

  it('shows a pending-synthesis note and the transcript when audioUrl is null', () => {
    render(
      <AudioSummary
        block={block({
          data: {
            title: 'Attention, explained',
            audioUrl: null,
            durationSec: 65,
            transcript: 'Hello listener, today we cover attention.',
            segments: [{ label: 'Intro', startSec: 0, endSec: 65 }],
            voice: null,
            citations: [],
          },
        })}
      />
    );
    expect(screen.getByText('Attention, explained')).toBeInTheDocument();
    expect(screen.getByText(/isn.t available yet/i)).toBeInTheDocument();
    expect(screen.getByText('Intro')).toBeInTheDocument();
    expect(screen.getByText(/Hello listener, today we cover attention\./)).toBeInTheDocument();
    expect(screen.queryByRole('audio')).not.toBeInTheDocument();
  });

  it('renders an audio player when audioUrl is present', () => {
    const { container } = render(
      <AudioSummary
        block={block({
          data: {
            title: 'Attention, explained',
            audioUrl: 'https://example.com/audio.mp3',
            durationSec: 65,
            transcript: 'Hello listener.',
            segments: [],
            voice: 'default',
            citations: [],
          },
        })}
      />
    );
    const audioEl = container.querySelector('audio');
    expect(audioEl).not.toBeNull();
    expect(audioEl).toHaveAttribute('src', 'https://example.com/audio.mp3');
  });
});
