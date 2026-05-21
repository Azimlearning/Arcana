import { ChatPanel } from '@/components/shell/ChatPanel';
import { ModeIndicator } from '@/components/shell/ModeIndicator';
import { SourcesPanel } from '@/components/shell/SourcesPanel';
import { StudioPanel } from '@/components/shell/StudioPanel';

interface Props {
  notebookId: string;
}

/** The stable 3-panel frame. Slice scope: panel widths are fixed
 *  (20% / 45% / 35%) for Research mode per uiux_plan.md §4. The UI
 *  Agent's dynamic width selection (FR-UI-01) lands in P1. */
export function Shell({ notebookId }: Props) {
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

      <div className="flex-1 grid min-h-0" style={{ gridTemplateColumns: '20% 45% 35%' }}>
        <SourcesPanel />
        <ChatPanel notebookId={notebookId} />
        <StudioPanel />
      </div>
    </div>
  );
}
