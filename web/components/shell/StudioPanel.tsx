'use client';

/** Slice scope: empty. The Studio panel hosts the interactive graph view
 *  (FR-KG-08) and per-mode work surfaces in P1. */
export function StudioPanel() {
  return (
    <aside className="h-full flex flex-col border-l border-line bg-paper">
      <div className="px-4 py-3 border-b border-line">
        <h2 className="font-display text-lg text-ink">Studio</h2>
      </div>
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center max-w-xs">
          <p className="text-sm text-ink-soft">
            The Studio panel hosts the knowledge-graph view and per-mode
            work surfaces.
          </p>
          <p className="text-xs text-ink-softer mt-2 font-mono">
            Lands in P1 §1.6.
          </p>
        </div>
      </div>
    </aside>
  );
}
