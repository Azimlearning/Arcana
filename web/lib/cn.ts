import { clsx, type ClassValue } from 'clsx';

/** Class-name helper - thin re-export so consumers don't import clsx directly. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
