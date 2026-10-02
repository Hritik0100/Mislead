'use client';

import { cn } from '@/lib/utils';

export type AssessmentType =
  | 'supported'
  | 'contradicted'
  | 'misleading'
  | 'unverified'
  | 'pending'
  | 'debunked'
  | 'contested'
  | 'verified'
  | 'fact'
  | 'opinion'
  | 'misinformation'
  | 'disinformation';

interface AssessmentBadgeProps {
  assessment: AssessmentType;
  size?: 'sm' | 'md' | 'lg';
}

const assessmentStyles: Record<AssessmentType, { bg: string; text: string; label: string }> = {
  supported: { bg: 'bg-green-900/30', text: 'text-green-400', label: 'SUPPORTED' },
  contradicted: { bg: 'bg-red-900/30', text: 'text-red-400', label: 'CONTRADICTED' },
  misleading: { bg: 'bg-amber-900/30', text: 'text-amber-400', label: 'MISLEADING' },
  unverified: { bg: 'bg-gray-800', text: 'text-gray-400', label: 'UNVERIFIED' },
  pending: { bg: 'bg-blue-900/30', text: 'text-blue-400', label: 'PENDING' },
  debunked: { bg: 'bg-red-900/30', text: 'text-red-400', label: 'DEBUNKED' },
  contested: { bg: 'bg-orange-900/30', text: 'text-orange-400', label: 'CONTESTED' },
  verified: { bg: 'bg-green-900/30', text: 'text-green-400', label: 'VERIFIED' },
  fact: { bg: 'bg-blue-900/30', text: 'text-blue-400', label: 'FACT' },
  opinion: { bg: 'bg-purple-900/30', text: 'text-purple-400', label: 'OPINION' },
  misinformation: { bg: 'bg-amber-900/30', text: 'text-amber-400', label: 'MISINFORMATION' },
  disinformation: { bg: 'bg-red-900/30', text: 'text-red-400', label: 'DISINFORMATION' },
};

export function AssessmentBadge({ assessment, size = 'md' }: AssessmentBadgeProps) {
  const style = assessmentStyles[assessment] || assessmentStyles.pending;

  return (
    <span
      className={cn(
        'inline-flex items-center font-mono font-bold uppercase tracking-wider border rounded',
        style.bg,
        style.text,
        size === 'sm' && 'text-[10px] px-1.5 py-0.5',
        size === 'md' && 'text-xs px-2 py-1',
        size === 'lg' && 'text-sm px-3 py-1.5',
        assessment === 'supported' && 'border-green-800',
        assessment === 'contradicted' && 'border-red-800',
        assessment === 'misleading' && 'border-amber-800',
        assessment === 'unverified' && 'border-gray-700',
        assessment === 'pending' && 'border-blue-800',
        assessment === 'debunked' && 'border-red-800',
        assessment === 'contested' && 'border-orange-800',
        assessment === 'verified' && 'border-green-800',
        assessment === 'fact' && 'border-blue-800',
        assessment === 'opinion' && 'border-purple-800',
        assessment === 'misinformation' && 'border-amber-800',
        assessment === 'disinformation' && 'border-red-800'
      )}
    >
      {style.label}
    </span>
  );
}
