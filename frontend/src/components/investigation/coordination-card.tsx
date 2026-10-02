'use client';

import { Users, Link2, FileText, Clock, AlertTriangle, Eye } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface CoordinationCluster {
  id: string;
  accounts: string[];
  commonUrls: string[];
  textSimilarity: number;
  mediaSimilarity: number;
  temporalProximity: number;
  patternDescription: string;
  confidence: number;
}

interface CoordinationCardProps {
  cluster: CoordinationCluster;
  onSelect?: (cluster: CoordinationCluster) => void;
}

export function CoordinationCard({ cluster, onSelect }: CoordinationCardProps) {
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-400';
    if (confidence >= 0.6) return 'text-amber-400';
    return 'text-red-400';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.8) return 'HIGH';
    if (confidence >= 0.6) return 'MEDIUM';
    return 'LOW';
  };

  return (
    <div
      className={cn(
        'bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors',
        onSelect && 'cursor-pointer'
      )}
      onClick={() => onSelect?.(cluster)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-purple-900/30 rounded-lg">
            <Users className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h3 className="text-white font-medium">Cluster {cluster.id}</h3>
            <p className="text-gray-400 text-sm">{cluster.accounts.length} accounts</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-mono bg-amber-900/30 text-amber-400 border border-amber-800">
            <AlertTriangle className="w-3 h-3" />
            REQUIRES ANALYST REVIEW
          </span>
        </div>
      </div>

      <p className="text-gray-300 text-sm mb-4">{cluster.patternDescription}</p>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">
            <FileText className="w-3 h-3" />
            Text Similarity
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-cyan-500 rounded-full"
                style={{ width: `${cluster.textSimilarity * 100}%` }}
              />
            </div>
            <span className="text-sm font-mono text-white">
              {(cluster.textSimilarity * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-3">
          <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">
            <Eye className="w-3 h-3" />
            Media Similarity
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-500 rounded-full"
                style={{ width: `${cluster.mediaSimilarity * 100}%` }}
              />
            </div>
            <span className="text-sm font-mono text-white">
              {(cluster.mediaSimilarity * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-3">
          <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">
            <Clock className="w-3 h-3" />
            Temporal Proximity
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full"
                style={{ width: `${cluster.temporalProximity * 100}%` }}
              />
            </div>
            <span className="text-sm font-mono text-white">
              {(cluster.temporalProximity * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-3">
          <div className="flex items-center gap-2 text-gray-400 text-xs mb-1">
            <Link2 className="w-3 h-3" />
            Common URLs
          </div>
          <span className="text-lg font-bold text-white">{cluster.commonUrls.length}</span>
        </div>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-gray-400 text-xs">Confidence:</span>
          <span className={cn('text-sm font-bold', getConfidenceColor(cluster.confidence))}>
            {getConfidenceLabel(cluster.confidence)}
          </span>
          <span className="text-gray-500 text-xs">
            ({(cluster.confidence * 100).toFixed(0)}%)
          </span>
        </div>
        <div className="flex -space-x-2">
          {cluster.accounts.slice(0, 5).map((account, i) => (
            <div
              key={account}
              className="w-7 h-7 rounded-full bg-gray-700 border-2 border-gray-900 flex items-center justify-center text-[10px] font-medium text-white"
              style={{ zIndex: 5 - i }}
              title={account}
            >
              {account.charAt(0).toUpperCase()}
            </div>
          ))}
          {cluster.accounts.length > 5 && (
            <div className="w-7 h-7 rounded-full bg-gray-600 border-2 border-gray-900 flex items-center justify-center text-[10px] font-medium text-white">
              +{cluster.accounts.length - 5}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
