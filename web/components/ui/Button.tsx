import { cn } from '@/lib/cn';

type Variant = 'primary' | 'ghost';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = 'primary', className, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      className={cn(
        'inline-flex items-center justify-center rounded-ctl px-3 py-1.5 text-sm font-medium',
        'transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
        'focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-paper',
        variant === 'primary' &&
          'bg-accent text-white hover:opacity-90',
        variant === 'ghost' &&
          'bg-transparent text-ink hover:bg-line/40 border border-line',
        className,
      )}
    />
  );
}
