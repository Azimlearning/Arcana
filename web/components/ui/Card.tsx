import { cn } from '@/lib/cn';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Card({ className, children, ...rest }: CardProps) {
  return (
    <div
      {...rest}
      className={cn(
        'bg-card rounded-card border border-line shadow-sm p-5',
        className,
      )}
    >
      {children}
    </div>
  );
}
