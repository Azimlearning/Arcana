import type { PlagiarismReport as PlagiarismReportBlock } from '@arcana/schema';

import { Card } from '@/components/ui/Card';
import { EmptyState, ErrorState, LoadingState, PartialState } from '@/components/genui/BlockStates';

interface Props {
  block: PlagiarismReportBlock;
}

export function PlagiarismReport({ block }: Props) {
  const { meta, data } = block;

  if (meta.status === 'loading') return <LoadingState caption="Checking originality..." rows={4} />;
  if (meta.status === 'error') return <ErrorState message="Originality check failed." />;
  if (meta.status === 'ready' && !data.flags.length && !data.draftTitle) {
    return (
      <EmptyState
        title="Nothing to check"
        hint="Paste a passage and ask for an originality check to see matches against your sources."
      />
    );
  }

  const body = <Body block={block} />;
  if (meta.status === 'partial') return <PartialState>{body}</PartialState>;
  return <Card className="border-red/20">{body}</Card>;
}

function ScoreBar({ label, value, tone }: { label: string; value: number; tone: 'good' | 'warn' }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs font-mono text-ink-softer">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 bg-surface-2 rounded overflow-hidden">
        {/* dynamic width from data — cannot be expressed as a fixed CSS class */}
        <div
          className={`h-full transition-all ${tone === 'good' ? 'bg-green-500' : 'bg-amber'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function Body({ block }: { block: PlagiarismReportBlock }) {
  const { data } = block;

  return (
    <div className="space-y-4">
      <div className="text-xs font-mono uppercase text-red tracking-wide">Originality report</div>
      <h3 className="font-display text-lg text-ink">{data.draftTitle}</h3>

      <div className="space-y-3">
        <ScoreBar label="Originality" value={data.originalityScore} tone="good" />
        <ScoreBar label="AI-likeness (heuristic)" value={data.aiLikelihood} tone="warn" />
      </div>

      {data.flags.length === 0 ? (
        <p className="text-sm text-ink-soft">
          No overlapping passages found against your sources.
        </p>
      ) : (
        <div className="space-y-2">
          <div className="text-xs font-mono text-ink-softer uppercase tracking-wide">
            Flagged passages ({data.flags.length})
          </div>
          {data.flags.map((flag, i) => (
            <div key={i} className="px-3 py-2 bg-surface-2 rounded border border-line/40 space-y-1">
              <div className="flex justify-between text-xs font-mono text-ink-softer">
                <span className="truncate">{flag.matchSource}</span>
                <span className="ml-2 shrink-0">
                  {flag.flagKind === 'ai_generated' ? 'AI-like' : 'similarity'}{' '}
                  {Math.round(flag.similarity * 100)}%
                </span>
              </div>
              <p className="text-sm text-ink-soft italic">&ldquo;{flag.excerpt}&rdquo;</p>
            </div>
          ))}
        </div>
      )}

      <div className="text-xs text-ink-softer font-mono border-t border-line pt-2">
        Trigram-overlap check against your corpus — not a certified plagiarism detector.
        Checked {data.checkedAt}
      </div>
    </div>
  );
}
