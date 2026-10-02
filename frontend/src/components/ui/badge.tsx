'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

const badgeVariants = cva(
  'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default:
          'bg-cyber-primary/10 text-cyber-primary-light border border-cyber-primary/20',
        secondary:
          'bg-cyber-card text-cyber-text-muted border border-cyber-border',
        destructive:
          'bg-cyber-danger/10 text-cyber-danger border border-cyber-danger/20',
        success:
          'bg-cyber-success/10 text-cyber-success border border-cyber-success/20',
        warning:
          'bg-cyber-warning/10 text-cyber-warning border border-cyber-warning/20',
        outline:
          'text-cyber-text border border-cyber-border',
        glow:
          'bg-cyber-primary/20 text-cyber-primary-light border border-cyber-primary/30 shadow-sm shadow-cyber-primary/20',
      },
      size: {
        default: 'px-2.5 py-0.5',
        sm: 'px-2 py-0.5 text-[10px]',
        lg: 'px-3 py-1 text-sm',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean;
}

function Badge({ className, variant, size, dot, children, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant, size }), className)} {...props}>
      {dot && (
        <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current" />
      )}
      {children}
    </div>
  );
}

export { Badge, badgeVariants };
