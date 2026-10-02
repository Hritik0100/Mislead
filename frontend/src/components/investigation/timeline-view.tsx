'use client';

import { cn } from '@/lib/utils';
import { TimelineEvent } from '@/lib/types';
import {
  UserPlus,
  FileText,
  AlertTriangle,
  Paperclip,
  RefreshCw,
  Brain,
  Clock,
} from 'lucide-react';

interface TimelineViewProps {
  events: TimelineEvent[];
  onEventClick?: (event: TimelineEvent) => void;
  compact?: boolean;
}

const eventIcons: Record<string, React.ElementType> = {
  account_created: UserPlus,
  post_collected: FileText,
  claim_made: AlertTriangle,
  evidence_added: Paperclip,
  status_change: RefreshCw,
  analysis_update: Brain,
};

const eventColors: Record<string, string> = {
  account_created: 'bg-blue-500',
  post_collected: 'bg-cyan-500',
  claim_made: 'bg-amber-500',
  evidence_added: 'bg-green-500',
  status_change: 'bg-purple-500',
  analysis_update: 'bg-pink-500',
};

export function TimelineView({ events, onEventClick, compact = false }: TimelineViewProps) {
  const sortedEvents = [...events].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  if (sortedEvents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-500">
        <Clock className="w-12 h-12 mb-4 opacity-50" />
        <p>No timeline events yet</p>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-800" />

      <div className="space-y-4">
        {sortedEvents.map((event) => {
          const Icon = eventIcons[event.type] || FileText;
          const color = eventColors[event.type] || 'bg-gray-500';

          return (
            <div
              key={event.id}
              className={cn(
                'relative flex items-start gap-4 pl-10',
                onEventClick && 'cursor-pointer hover:bg-gray-800/50 -mx-2 px-2 py-1 rounded-lg transition-colors'
              )}
              onClick={() => onEventClick?.(event)}
            >
              <div
                className={cn(
                  'absolute left-2 w-5 h-5 rounded-full flex items-center justify-center ring-2 ring-gray-900',
                  color
                )}
              >
                <Icon className="w-3 h-3 text-white" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className={cn('text-white font-medium', compact ? 'text-sm' : 'text-base')}>
                    {event.title}
                  </p>
                </div>
                {event.description && !compact && (
                  <p className="text-gray-400 text-sm mt-1">{event.description}</p>
                )}
                <p className="text-gray-500 text-xs mt-1">
                  {new Date(event.timestamp).toLocaleString()}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
