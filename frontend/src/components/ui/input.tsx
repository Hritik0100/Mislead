'use client';

import * as React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
  error?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, icon, error, ...props }, ref) => {
    return (
      <div className="relative w-full">
        {icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-cyber-text-dim">
            {icon}
          </div>
        )}
        <input
          type={type}
          className={cn(
            'flex h-10 w-full rounded-md border border-cyber-border bg-cyber-card px-3 py-2 text-sm text-cyber-text placeholder:text-cyber-text-dim focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyber-primary focus-visible:border-transparent disabled:cursor-not-allowed disabled:opacity-50 transition-colors duration-200',
            icon && 'pl-10',
            error && 'border-cyber-danger focus-visible:ring-cyber-danger',
            className
          )}
          ref={ref}
          {...props}
        />
        {error && (
          <p className="mt-1 text-xs text-cyber-danger">{error}</p>
        )}
      </div>
    );
  }
);
Input.displayName = 'Input';

export { Input };
