'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Clock, Filter, ZoomIn, ZoomOut, Loader2 } from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { TimelineView } from '@/components/investigation/timeline-view';
import api from '@/lib/api';
import { TimelineEvent } from '@/lib/types';

export default function CaseTimelinePage() {
  const params = useParams();
  const caseId = params.id as string;
  const { timeline, setTimeline, loading, setLoading } = useInvestigationStore();
  const [platformFilter, setPlatformFilter] = useState<string>('all');
  const [accountFilter, setAccountFilter] = useState<string>('all');
  const [claimFilter, setClaimFilter] = useState<string>('all');
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);

  useEffect(() => {
    fetchTimeline();
  }, [caseId]);

  const fetchTimeline = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/cases/${caseId}/timeline`);
      setTimeline(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch timeline:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredTimeline = timeline.filter((event) => {
    if (platformFilter !== 'all' && event.metadata?.platform !== platformFilter) {
      return false;
    }
    if (accountFilter !== 'all' && event.related_ids?.account_id !== accountFilter) {
      return false;
    }
    if (claimFilter !== 'all' && event.related_ids?.claim_id !== claimFilter) {
      return false;
    }
    return true;
  });

  const getEventTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      account_created: 'bg-blue-500',
      post_collected: 'bg-cyan-500',
      claim_made: 'bg-amber-500',
      evidence_added: 'bg-green-500',
      status_change: 'bg-purple-500',
      analysis_update: 'bg-pink-500',
    };
    return colors[type] || 'bg-gray-500';
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Timeline</h1>
          <p className="text-gray-400 mt-1">{timeline.length} events</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Platforms</option>
            <option value="twitter">X/Twitter</option>
            <option value="youtube">YouTube</option>
            <option value="telegram">Telegram</option>
            <option value="matrix">Matrix</option>
            <option value="web">Web</option>
          </select>
          <button className="p-2 bg-gray-900 border border-gray-800 rounded-lg hover:bg-gray-800 transition-colors">
            <ZoomIn className="w-4 h-4 text-gray-400" />
          </button>
          <button className="p-2 bg-gray-900 border border-gray-800 rounded-lg hover:bg-gray-800 transition-colors">
            <ZoomOut className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : filteredTimeline.length === 0 ? (
            <div className="text-center py-12">
              <Clock className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No timeline events</p>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <TimelineView
                events={filteredTimeline}
                onEventClick={setSelectedEvent}
              />
            </div>
          )}
        </div>

        <div className="lg:col-span-1">
          {selectedEvent ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sticky top-6">
              <h3 className="text-white font-medium mb-4">Event Details</h3>
              
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Event Type</p>
                  <div className="flex items-center gap-2">
                    <div className={`w-3 h-3 rounded-full ${getEventTypeColor(selectedEvent.type)}`} />
                    <span className="text-white text-sm capitalize">
                      {selectedEvent.type.replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Title</p>
                  <p className="text-white text-sm">{selectedEvent.title}</p>
                </div>

                {selectedEvent.description && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Description</p>
                    <p className="text-white text-sm">{selectedEvent.description}</p>
                  </div>
                )}

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Timestamp</p>
                  <p className="text-white text-sm">
                    {new Date(selectedEvent.timestamp).toLocaleString()}
                  </p>
                </div>

                {selectedEvent.related_ids && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Related IDs</p>
                    <div className="space-y-1">
                      {selectedEvent.related_ids.account_id && (
                        <p className="text-sm text-gray-300">
                          Account: <span className="text-cyan-400 font-mono">{selectedEvent.related_ids.account_id}</span>
                        </p>
                      )}
                      {selectedEvent.related_ids.post_id && (
                        <p className="text-sm text-gray-300">
                          Post: <span className="text-cyan-400 font-mono">{selectedEvent.related_ids.post_id}</span>
                        </p>
                      )}
                      {selectedEvent.related_ids.claim_id && (
                        <p className="text-sm text-gray-300">
                          Claim: <span className="text-cyan-400 font-mono">{selectedEvent.related_ids.claim_id}</span>
                        </p>
                      )}
                      {selectedEvent.related_ids.evidence_id && (
                        <p className="text-sm text-gray-300">
                          Evidence: <span className="text-cyan-400 font-mono">{selectedEvent.related_ids.evidence_id}</span>
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {selectedEvent.metadata && Object.keys(selectedEvent.metadata).length > 0 && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Metadata</p>
                    <pre className="text-xs font-mono text-gray-300 bg-gray-900 p-2 rounded overflow-x-auto">
                      {JSON.stringify(selectedEvent.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center py-12">
              <Clock className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">Select an event to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
