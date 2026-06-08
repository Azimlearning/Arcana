'use client';

import { useRef } from 'react';

import { ChatPanel } from '@/components/shell/ChatPanel';
import { ModeIndicator } from '@/components/shell/ModeIndicator';
import { PanelResizer } from '@/components/shell/PanelResizer';
import { SourcesPanel } from '@/components/shell/SourcesPanel';
import { StudioPanel } from '@/components/shell/StudioPanel';
import { selectActiveLayout, useUIStore } from '@/store/uiStore';

interface Props {
  notebookId: string;
}

/**
 * The stable 3-panel frame. Panel widths and visibility adapt per mode via
 * the MODE_LAYOUT map in uiStore (FR-UI-01/05). A session-scoped manual
 * override written by PanelResizer wins over the default (FR-UI-07).
 * Collapsed panels (flex-grow=0) are aria-hidden + inert so their children
 * are invisible to both screen readers and keyboard navigation.
 * uiux_plan.md §3–§4.
 *
 * Note: CSS `flex-grow` is not animatable per spec. Width transitions for
 * mode reshaping are deferred to a follow-up (likely CSS grid fr-tracks or
 * an explicit width approach). uiux_plan.md §2.3 motion tokens still apply
 * to component hydrate fades inside each panel.
 */
export function Shell({ notebookId }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const layout = useUIStore(selectActiveLayout);
  const setLayoutOverride = useUIStore((s) => s.setLayoutOverride);

  const sourcesCollapsed = layout.sources === 0;
  const studioCollapsed = layout.studio === 0;

  return (
    <div className="h-screen flex flex-col bg-paper text-ink">
      <header className="flex items-center justify-between px-6 py-3 border-b border-line bg-card">
        <div className="flex items-center gap-3">
          <span className="font-display text-xl text-ink">Arcana</span>
          <span className="text-xs font-mono text-ink-softer">
            notebook: {notebookId}
          </span>
        </div>
        <ModeIndicator />
      </header>

      <div ref={containerRef} className="flex-1 flex min-h-0">

        {/* Sources panel — flex-grow 0 = collapsed (Exploration mode). */}
        <div
          className="min-w-0 overflow-hidden"
          style={{ flexGrow: layout.sources, flexShrink: 0, flexBasis: 0 }}
          aria-hidden={sourcesCollapsed || undefined}
          {...(sourcesCollapsed ? { inert: true } : {})}
        >
          <SourcesPanel />
        </div>

        <PanelResizer
          which="sources-chat"
          layout={layout}
          containerRef={containerRef}
          onLayoutChange={setLayoutOverride}
        />

        {/* Chat panel — always visible; MIN_CHAT enforced by PanelResizer. */}
        <div
          className="min-w-0 overflow-hidden"
          style={{ flexGrow: layout.chat, flexShrink: 0, flexBasis: 0 }}
        >
          <ChatPanel notebookId={notebookId} />
        </div>

        <PanelResizer
          which="chat-studio"
          layout={layout}
          containerRef={containerRef}
          onLayoutChange={setLayoutOverride}
        />

        {/* Studio panel — flex-grow 0 = hidden (Writing mode). */}
        <div
          className="min-w-0 overflow-hidden"
          style={{ flexGrow: layout.studio, flexShrink: 0, flexBasis: 0 }}
          aria-hidden={studioCollapsed || undefined}
          {...(studioCollapsed ? { inert: true } : {})}
        >
          <StudioPanel />
        </div>

      </div>
    </div>
  );
}
