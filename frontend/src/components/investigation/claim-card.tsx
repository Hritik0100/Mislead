'use client';

import { cn } from '@/lib/utils';
import { AssessmentBadge, AssessmentType } from './assessment-badge';
import { Clock, User, TrendingUp, TrendingDown, Minus } from 'lucide-react';

export interface ClaimData {
  id: string;
  text: string;
  assessment: AssessmentType;
  confidence: number;
  evidenceCount: number;
  supportingCount: number;
  contradictingCount: number;
  earliestSource?: string;
  earliestSourceDate?: string;
  factCheckStatus?: 'verified' | 'debunked' | 'contested' | 'pending';
  semanticCluster?: string;
}

interface ClaimCardProps {
  claim: ClaimData;
  onSelect?: (claim: ClaimData) => void;
}

export function ClaimCard({ claim, onSelect }: ClaimCardProps) {
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-400';
    if (confidence >= 0.6) return 'text-amber-400';
    if (confidence >= 0.4) return 'text-orange-400';
    return 'text-red-400';
  };

  const getFactCheckColor = (status?: string) => {
    switch (status) {
      case 'verified':
        return 'bg-green-900/30 text-green-400 border-green-800';
      case 'debunked':
        return 'bg-red-900/30 text-red-400 border-red-800';
      case 'contested':
        return 'bg-amber-900/30 text-amber-400 border-amber-800';
      default:
        return 'bg-gray-800 text-gray-400 border-gray-700';
    }
  };

  return (
    <div
      className={cn(
        'bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors',
        onSelect && 'cursor-pointer'
      )}
      onClick={() => onSelect?.(claim)}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <p className="text-white text-sm flex-1">{claim.text}</p>
        <AssessmentBadge assessment={claim.assessment} size="sm" />
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <div className="bg-gray-800 rounded-lg p-2 text-center">
          <div className="flex items-center justify-center gap-1 text-green-400 mb-1">
            <TrendingUp className="w-3 h-3" />
            <span className="text-xs">Supporting</span>
          </div>
          <p className="text-lg font-bold text-white">{claim.supportingCount}</p>
        </div>

        <div className="bg-gray-800 rounded-lg p-2 text-center">
          <div className="flex items-center justify-center gap-1 text-red-400 mb-1">
            <TrendingDown className="w-3 h-3" />
            <span className="text-xs">Contradicting</span>
          </div>
          <p className="text-lg font-bold text-white">{claim.contradictingCount}</p>
        </div>

        <div className="bg-gray-800 rounded-lg p-2 text-center">
          <div className="flex items-center justify-center gap-1 text-gray-400 mb-1">
            <Minus className="w-3 h-3" />
            <span className="text-xs">Total</span>
          </div>
          <p className="text-lg font-bold text-white">{claim.evidenceCount}</p>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-400">
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <span>Confidence:</span>
            <span className={cn('font-mono font-bold', getConfidenceColor(claim.confidence))}>
              {(claim.confidence * 100).toFixed(0)}%
            </span>
          </div>
          {claim.factCheckStatus && (
            <span
              className={cn(
                'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border',
                getFactCheckColor(claim.factCheckStatus)
              )}
            >
              {claim.factCheckStatus.toUpperCase()}
            </span>
          )}
        </div>
        {claim.earliestSource && (
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>Earliest: {claim.earliestSource}</span>
          </div>
        )}
      </div>

      {claim.semanticCluster && (
        <div className="mt-2 pt-2 border-t border-gray-800">
          <span className="text-xs text-gray-500">
            Cluster: <span className="text-cyan-400">{claim.semanticCluster}</span>
          </span>
        </div>
      )}
    </div>
  );
}
