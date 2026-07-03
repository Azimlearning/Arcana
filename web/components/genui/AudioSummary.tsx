import type { AudioSummary as AudioSummaryBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: AudioSummaryBlock;
}

function formatDuration(totalSec: number): string {
  const m = Math.floor(totalSec / 60);
  const s = Math.round(totalSec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export function AudioSummary({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Preparing audio overview..." rows={4} />;
  if (meta.status === 'error') return <ErrorState message="Audio overview failed." />;
  if (meta.status === 'ready' && !data.transcript && !data.audioUrl) {
    return (
      <EmptyState
        title="No audio overview yet"
        hint="Ask for an audio overview of a document to generate a listenable summary."
      />
    );
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <Card className="border-violet-500/20">{body}</Card>;
}

function Body({ block }: { block: AudioSummaryBlock }) {
  const { data } = block;

  return (
    <div className="space-y-4">
      <div className="text-xs font-mono uppercase text-violet-600 tracking-wide">Audio overview</div>
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-display text-lg text-ink">{data.title}</h3>
        {data.durationSec > 0 && (
          <span className="text-xs font-mono text-ink-softer shrink-0">
            ~{formatDuration(data.durationSec)}
          </span>
        )}
      </div>

      {data.audioUrl ? (
        // eslint-disable-next-line jsx-a11y/media-has-caption -- transcript rendered below
        <audio controls src={data.audioUrl} className="w-full" />
      ) : (
        <div className="px-3 py-2 bg-surface-2 rounded border border-line/40 text-sm text-ink-soft">
          Audio synthesis isn&rsquo;t available yet — read the script below.
        </div>
      )}

      {data.segments.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs font-mono text-ink-softer uppercase tracking-wide">Chapters</div>
          {data.segments.map((seg, i) => (
            <div key={i} className="flex justify-between text-xs">
              <span className="text-ink-soft truncate">{seg.label}</span>
              <span className="font-mono text-ink-softer ml-2 shrink-0">
                {formatDuration(seg.startSec)}–{formatDuration(seg.endSec)}
              </span>
            </div>
          ))}
        </div>
      )}

      {data.transcript && (
        <details open={!data.audioUrl}>
          <summary className="text-xs font-mono text-ink-softer uppercase tracking-wide cursor-pointer">
            Transcript
          </summary>
          <p className="mt-2 text-sm text-ink-soft whitespace-pre-wrap">{data.transcript}</p>
        </details>
      )}
    </div>
  );
}
