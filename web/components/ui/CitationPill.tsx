import { cn } from '@/lib/cn';

interface CitationPillProps {
  id: string;
  docTitle: string;
  page: number | null;
  quote?: string;
  onClick?: () => void;
}

/** Compact clickable citation - inline-rendered next to the claim it
 *  supports. Style mirrors uiux_plan.md §2.1 "Grounded" token (green). */
export function CitationPill({ id, docTitle, page, quote, onClick }: CitationPillProps) {
  const label = page != null ? `${docTitle} · p${page}` : docTitle;
  const title = quote ? `${label}\n\n"${quote}"` : label;
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={cn(
        'inline-flex items-center gap-1 align-baseline',
        'bg-green-bg text-green text-xs font-mono px-1.5 py-0.5 rounded-ctl',
        'hover:underline focus:outline-none focus:ring-2 focus:ring-green',
        'transition-colors',
      )}
      aria-label={`Citation ${id}: ${label}`}
    >
      <span aria-hidden>[{id}]</span>
    </button>
  );
}
