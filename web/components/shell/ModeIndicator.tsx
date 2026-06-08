'use client';

import type { Mode } from '@arcana/schema';

import { cn } from '@/lib/cn';
import { useUIStore } from '@/store/uiStore';

// Ordered for the header switcher. Labels are short to fit the chrome;
// the value is the wire `Mode` sent on every turn (FR-UI-06).
const MODES: ReadonlyArray<{ value: Mode; label: string }> = [
  { value: 'research', label: 'Research' },
  { value: 'study', label: 'Study' },
  { value: 'writing', label: 'Writing' },
  { value: 'socratic', label: 'Socratic' },
  { value: 'exploration', label: 'Explore' },
];

/** Interactive mode switcher (FR-UI-06). Selecting a mode updates the
 *  uiStore; ChatPanel reads `activeMode` and sends it on the next turn so
 *  the orchestrator routes to the matching agent. Manual override is the
 *  whole point here — there is no auto intent classifier yet (FR-UI-07). */
export function ModeIndicator() {
  const activeMode = useUIStore((s) => s.activeMode);
  const setActiveMode = useUIStore((s) => s.setActiveMode);

  return (
    <div
      role="group"
      aria-label="Interaction mode"
      className="inline-flex items-center gap-0.5 p-0.5 rounded-ctl bg-card border border-line"
    >
      {MODES.map(({ value, label }) => {
        const active = value === activeMode;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={active}
            onClick={() => setActiveMode(value)}
            className={cn(
              'px-2.5 py-1 rounded-ctl text-xs font-mono uppercase tracking-wide',
              'transition-colors focus:outline-none focus:ring-2 focus:ring-accent',
              active
                ? 'bg-accent text-card'
                : 'text-ink-soft hover:text-ink hover:bg-line/40',
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
