// CornellNotes — structured cue / notes / summary layout.
// uiux_plan.md §4: Study/Learning mode, studio panel. FR-LRN-05.

import type { CornellNotes as CornellNotesBlock, CornellNote } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: CornellNotesBlock;
}

export function CornellNotes({ block }: Props) {
  const { meta, data } = block;

  if (data.notes.length === 0 && meta.status === 'ready') {
    return (
      <EmptyState
        title="No Cornell notes yet"
        hint="Ask to take structured notes on a topic in Study mode."
      />
    );
  }

  if (meta.status === 'loading') {
    return <LoadingState caption="Generating Cornell notes…" rows={7} />;
  }

  if (meta.status === 'error') {
    return <ErrorState message="Could not generate Cornell notes." />;
  }

  const body = <Body block={block} />;

  if (meta.status === 'partial') {
    return <PartialState>{body}</PartialState>;
  }

  return <Card>{body}</Card>;
}

function Body({ block }: { block: CornellNotesBlock }) {
  const { data } = block;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono uppercase text-ink-softer tracking-wide">
          Cornell Notes
        </div>
        <span className="text-xs font-mono text-ink-soft">
          {data.notes.length} note{data.notes.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="text-sm font-medium text-ink">{data.topic}</div>

      {/* Column headers */}
      <div className="grid grid-cols-[1fr_2fr] gap-0 border border-line rounded-card overflow-hidden">
        <div className="px-3 py-1.5 bg-card border-b border-r border-line">
          <span className="text-xs font-mono uppercase text-ink-softer tracking-wide">Cue</span>
        </div>
        <div className="px-3 py-1.5 bg-card border-b border-line">
          <span className="text-xs font-mono uppercase text-ink-softer tracking-wide">Notes</span>
        </div>

        {data.notes.map((note, i) => (
          <NoteRow key={i} note={note} last={i === data.notes.length - 1} />
        ))}
      </div>

      {/* Summary strip */}
      {data.summary && (
        <div className="rounded-card border border-accent/30 bg-accent/5 px-4 py-3 space-y-1">
          <div className="text-xs font-mono uppercase text-accent tracking-wide">Summary</div>
          <p className="text-sm font-serif text-ink leading-relaxed">{data.summary}</p>
        </div>
      )}

      {/* Citations */}
      {data.citations.length > 0 && (
        <div className="border-t border-line pt-2 space-y-1">
          {data.citations.map((c) => (
            <div key={c.id} className="text-xs font-mono text-ink-softer truncate">
              {c.docTitle}
              {c.page != null && ` · p.${c.page}`}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function NoteRow({ note, last }: { note: CornellNote; last: boolean }) {
  const borderClass = last ? '' : 'border-b border-line';
  return (
    <>
      <div className={`px-3 py-2.5 border-r border-line ${borderClass} bg-paper`}>
        <p className="text-sm font-medium text-ink leading-snug">{note.cue}</p>
        {note.citationIds.length > 0 && (
          <div className="flex gap-1 mt-1 flex-wrap">
            {note.citationIds.map((id) => (
              <span key={id} className="text-xs font-mono text-ink-softer">
                [{id}]
              </span>
            ))}
          </div>
        )}
      </div>
      <div className={`px-3 py-2.5 ${borderClass} bg-paper`}>
        <p className="text-sm font-serif text-ink-soft leading-relaxed">{note.content}</p>
      </div>
    </>
  );
}
