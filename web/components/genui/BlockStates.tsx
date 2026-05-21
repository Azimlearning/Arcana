// Shared Empty / Loading / Partial / Error wrappers used by every
// catalog component. NFR-USE-02, FR-UI-09 - a component without all
// four states is not done.
//
// Components import these for the *structural* states; the loading
// skeleton's *shape* is component-specific (see e.g. CitedSummary's
// LoadingShape below).

import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/cn';

interface EmptyStateProps {
  title: string;
  hint: string;
  className?: string;
}

export function EmptyState({ title, hint, className }: EmptyStateProps) {
  return (
    <Card className={cn('text-center py-12', className)}>
      <h3 className="font-display text-xl text-ink">{title}</h3>
      <p className="mt-2 text-ink-soft text-sm">{hint}</p>
    </Card>
  );
}

interface LoadingStateProps {
  /** Total number of shimmering rows. */
  rows?: number;
  /** Optional caption shown above the skeleton (a11y). */
  caption?: string;
}

export function LoadingState({ rows = 5, caption = 'Researching…' }: LoadingStateProps) {
  return (
    <Card aria-busy aria-live="polite">
      <div className="sr-only">{caption}</div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} width={i === rows - 1 ? '60%' : '100%'} height="0.75rem" />
        ))}
        <div className="flex gap-2 pt-2">
          <Skeleton width="3rem" height="1.25rem" />
          <Skeleton width="3rem" height="1.25rem" />
        </div>
      </div>
    </Card>
  );
}

interface PartialStateProps {
  children: React.ReactNode;
}

export function PartialState({ children }: PartialStateProps) {
  return (
    <Card className="border-amber/40 bg-amber-bg/30" aria-live="polite">
      <div className="text-xs font-mono uppercase text-amber tracking-wide mb-2">
        Partial result
      </div>
      {children}
    </Card>
  );
}

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <Card className="border-red/40 bg-red-bg/30" role="alert">
      <div className="text-xs font-mono uppercase text-red tracking-wide mb-1">
        Something went wrong
      </div>
      <p className="text-ink text-sm mb-3">{message}</p>
      {onRetry && (
        <Button variant="ghost" onClick={onRetry}>
          Retry
        </Button>
      )}
    </Card>
  );
}
