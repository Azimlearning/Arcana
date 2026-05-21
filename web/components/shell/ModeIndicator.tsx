'use client';

import { useUIStore } from '@/store/uiStore';

/** Shows the active mode. Slice has only 'research'; the mode switcher
 *  + manual override (FR-UI-07) land in P1. */
export function ModeIndicator() {
  const mode = useUIStore((s) => s.activeMode);
  return (
    <div
      className="inline-flex items-center gap-2 px-2.5 py-1 rounded-ctl bg-card border border-line"
      aria-label={`Active mode: ${mode}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-green" aria-hidden />
      <span className="text-xs font-mono uppercase tracking-wide text-ink-soft">
        {mode}
      </span>
    </div>
  );
}
