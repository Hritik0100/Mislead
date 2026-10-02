'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Network, Loader2, AlertTriangle } from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { CoordinationCard, CoordinationCluster } from '@/components/investigation/coordination-card';
import api from '@/lib/api';

export default function CaseCoordinationPage() {
  const params = useParams();
  const caseId = params.id as string;
  const [clusters, setClusters] = useState<CoordinationCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCluster, setSelectedCluster] = useState<CoordinationCluster | null>(null);

  useEffect(() => {
    fetchCoordination();
  }, [caseId]);

  const fetchCoordination = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/cases/${caseId}/coordination`);
      setClusters(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch coordination data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Coordination Analysis</h1>
          <p className="text-gray-400 mt-1">Detected coordination patterns and clusters</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : clusters.length === 0 ? (
            <div className="text-center py-12">
              <Network className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No coordination patterns detected</p>
              <p className="text-gray-500 text-sm mt-1">
                This could indicate organic activity
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="bg-amber-900/20 border border-amber-800 rounded-lg p-4 flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-amber-200 text-sm font-medium">Analyst Review Required</p>
                  <p className="text-amber-200/70 text-sm mt-1">
                    Coordination patterns require manual verification. Automated detection may produce false positives.
                  </p>
                </div>
              </div>

              {clusters.map((cluster) => (
                <CoordinationCard
                  key={cluster.id}
                  cluster={cluster}
                  onSelect={setSelectedCluster}
                />
              ))}
            </div>
          )}
        </div>

        <div className="lg:col-span-1">
          {selectedCluster ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sticky top-6">
              <h3 className="text-white font-medium mb-4">Cluster Details</h3>
              
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Accounts</p>
                  <div className="space-y-1">
                    {selectedCluster.accounts.map((account) => (
                      <p key={account} className="text-white text-sm font-mono">
                        @{account}
                      </p>
                    ))}
                  </div>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Common URLs</p>
                  <div className="space-y-1">
                    {selectedCluster.commonUrls.map((url) => (
                      <p key={url} className="text-cyan-400 text-xs break-all">
                        {url}
                      </p>
                    ))}
                  </div>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Pattern Description</p>
                  <p className="text-white text-sm">{selectedCluster.patternDescription}</p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Confidence</p>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          selectedCluster.confidence >= 0.8
                            ? 'bg-green-500'
                            : selectedCluster.confidence >= 0.6
                            ? 'bg-amber-500'
                            : 'bg-red-500'
                        }`}
                        style={{ width: `${selectedCluster.confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-mono text-white">
                      {(selectedCluster.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center py-12">
              <Network className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">Select a cluster to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
