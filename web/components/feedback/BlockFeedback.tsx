'use client';

import { useState } from 'react';

import { postRating } from '@/lib/feedback';

interface Props {
  blockId: string;
  blockType: string;
  sessionId: string;
  /** Only show once block is fully rendered (not loading/partial) */
  ready?: boolean;
}

export function BlockFeedback({ blockId, blockType, sessionId, ready = true }: Props) {
  const [voted, setVoted] = useState<'up' | 'down' | null>(null);

  if (!ready) return null;

  async function vote(rating: 'up' | 'down') {
    if (voted) return;
    setVoted(rating);
    try {
      await postRating({ sessionId, blockId, rating, blockType });
    } catch {
      // fire-and-forget — analytics failure must not surface to user
    }
  }

  return (
    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-line">
      <span className="text-xs text-ink-softer">Helpful?</span>
      <button
        onClick={() => vote('up')}
        aria-label="Thumbs up"
        className={`p-1 rounded text-sm transition-colors ${
          voted === 'up'
            ? 'text-accent bg-accent/10'
            : 'text-ink-softer hover:text-ink'
        }`}
        disabled={voted !== null}
      >
        👍
      </button>
      <button
        onClick={() => vote('down')}
        aria-label="Thumbs down"
        className={`p-1 rounded text-sm transition-colors ${
          voted === 'down'
            ? 'text-red bg-red/10'
            : 'text-ink-softer hover:text-ink'
        }`}
        disabled={voted !== null}
      >
        👎
      </button>
    </div>
  );
}
