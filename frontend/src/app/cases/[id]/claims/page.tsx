'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { Search, AlertTriangle, Loader2 } from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { ClaimCard, ClaimData } from '@/components/investigation/claim-card';
import api from '@/lib/api';
import { Claim } from '@/lib/types';

export default function CaseClaimsPage() {
  const params = useParams();
  const caseId = params.id as string;
  const { claims, setClaims, loading, setLoading } = useInvestigationStore();
  const [search, setSearch] = useState('');
  const [selectedClaim, setSelectedClaim] = useState<ClaimData | null>(null);

  useEffect(() => {
    fetchClaims();
  }, [caseId]);

  const fetchClaims = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/cases/${caseId}/claims`);
      setClaims(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch claims:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredClaims = claims.filter(
    (claim) => claim.text.toLowerCase().includes(search.toLowerCase())
  );

  const mappedClaims: ClaimData[] = filteredClaims.map((claim: any) => ({
    id: claim.id,
    text: claim.text,
    assessment: claim.status as any,
    confidence: claim.confidence,
    evidenceCount: claim.evidence_count,
    supportingCount:
      claim.supporting_count ?? Math.floor(claim.evidence_count * 0.6),
    contradictingCount:
      claim.contradicting_count ?? Math.floor(claim.evidence_count * 0.3),
    earliestSource: claim.metadata?.earliestSource as string,
    factCheckStatus: claim.status as any,
    semanticCluster: claim.metadata?.cluster as string,
  }));

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Claims</h1>
          <p className="text-gray-400 mt-1">{claims.length} claims identified</p>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search claims..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 pr-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : mappedClaims.length === 0 ? (
            <div className="text-center py-12">
              <AlertTriangle className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No claims found</p>
            </div>
          ) : (
            <div className="space-y-4">
              {mappedClaims.map((claim) => (
                <ClaimCard
                  key={claim.id}
                  claim={claim}
                  onSelect={setSelectedClaim}
                />
              ))}
            </div>
          )}
        </div>

        <div className="lg:col-span-1">
          {selectedClaim ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sticky top-6">
              <h3 className="text-white font-medium mb-4">Claim Details</h3>
              
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Claim Text</p>
                  <p className="text-white text-sm">{selectedClaim.text}</p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Assessment</p>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-900/30 text-blue-400 border border-blue-800">
                    {selectedClaim.assessment.toUpperCase()}
                  </span>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Confidence</p>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-cyan-500 rounded-full"
                        style={{ width: `${selectedClaim.confidence * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-mono text-white">
                      {(selectedClaim.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-gray-800 rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-green-400">{selectedClaim.supportingCount}</p>
                    <p className="text-gray-400 text-xs">Supporting</p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-red-400">{selectedClaim.contradictingCount}</p>
                    <p className="text-gray-400 text-xs">Contradicting</p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-white">{selectedClaim.evidenceCount}</p>
                    <p className="text-gray-400 text-xs">Total</p>
                  </div>
                </div>

                {selectedClaim.earliestSource && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Earliest Source</p>
                    <p className="text-white text-sm">{selectedClaim.earliestSource}</p>
                  </div>
                )}

                {selectedClaim.semanticCluster && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Semantic Cluster</p>
                    <p className="text-cyan-400 text-sm">{selectedClaim.semanticCluster}</p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center py-12">
              <AlertTriangle className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">Select a claim to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
