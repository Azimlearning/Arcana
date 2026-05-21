import { cn } from '@/lib/cn';

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string;
  height?: string;
}

/** A shimmer block sized to whatever the caller passes. Tokens-only —
 *  background color is bound to `--line` via the `.shimmer` class. */
export function Skeleton({ width = '100%', height = '0.75rem', className, style, ...rest }: SkeletonProps) {
  return (
    <div
      {...rest}
      className={cn('shimmer rounded-ctl', className)}
      style={{ width, height, ...style }}
      aria-hidden
    />
  );
}
