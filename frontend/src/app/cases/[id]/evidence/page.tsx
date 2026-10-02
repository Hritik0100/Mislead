'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  Search,
  Upload,
  Link2,
  Calendar,
  Loader2,
  ExternalLink,
  Copy,
  Hash,
} from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { EvidencePanel } from '@/components/investigation/evidence-panel';
import { formatDate } from '@/lib/utils';
import api from '@/lib/api';
import { Evidence } from '@/lib/types';

export default function CaseEvidencePage() {
  const params = useParams();
  const caseId = params.id as string;
  const { evidence, setEvidence, loading, setLoading } = useInvestigationStore();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);

  useEffect(() => {
    fetchEvidence();
  }, [caseId]);

  const fetchEvidence = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/cases/${caseId}/evidence`);
      setEvidence(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch evidence:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredEvidence = evidence.filter((item) => {
    const matchesSearch =
      item.title.toLowerCase().includes(search.toLowerCase()) ||
      item.description?.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === 'all' || item.type === typeFilter;
    return matchesSearch && matchesType;
  });

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Evidence</h1>
          <p className="text-gray-400 mt-1">{evidence.length} evidence items</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search evidence..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Types</option>
            <option value="screenshot">Screenshots</option>
            <option value="archive">Archives</option>
            <option value="text">Text</option>
            <option value="image">Images</option>
            <option value="video">Videos</option>
            <option value="document">Documents</option>
            <option value="link">Links</option>
          </select>
          <button className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors">
            <Upload className="w-4 h-4" />
            Upload Evidence
          </button>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
        <h3 className="text-white font-medium mb-3">Evidence Chain</h3>
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {evidence.slice(0, 10).map((item, i) => (
            <div key={item.id} className="flex items-center gap-2">
              <div className="flex-shrink-0 px-3 py-1.5 bg-gray-800 rounded-lg text-xs font-mono text-cyan-400">
                {item.id.slice(0, 8)}
              </div>
              {i < evidence.length - 1 && (
                <div className="w-8 h-px bg-gray-700" />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : filteredEvidence.length === 0 ? (
            <div className="text-center py-12">
              <Link2 className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No evidence found</p>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-gray-400 text-sm border-b border-gray-800">
                    <th className="p-4 font-medium">Title</th>
                    <th className="p-4 font-medium">Type</th>
                    <th className="p-4 font-medium">Hash</th>
                    <th className="p-4 font-medium">Source</th>
                    <th className="p-4 font-medium">Captured</th>
                    <th className="p-4 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {filteredEvidence.map((item) => (
                    <tr
                      key={item.id}
                      className={`hover:bg-gray-800/50 cursor-pointer ${
                        selectedEvidence?.id === item.id ? 'bg-gray-800' : ''
                      }`}
                      onClick={() => setSelectedEvidence(item)}
                    >
                      <td className="p-4">
                        <p className="text-white font-medium text-sm">{item.title}</p>
                        {item.description && (
                          <p className="text-gray-500 text-xs mt-1 truncate max-w-xs">
                            {item.description}
                          </p>
                        )}
                      </td>
                      <td className="p-4">
                        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-900/30 text-blue-400">
                          {item.type.toUpperCase()}
                        </span>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <code className="text-xs font-mono text-gray-400 truncate max-w-[120px]">
                            {item.hash?.slice(0, 16) || 'N/A'}
                          </code>
                          {item.hash && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                copyToClipboard(item.hash!);
                              }}
                              className="p-1 hover:bg-gray-700 rounded transition-colors"
                            >
                              <Copy className="w-3 h-3 text-gray-400" />
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="p-4 text-gray-300 text-sm">
                        {item.added_by}
                      </td>
                      <td className="p-4 text-gray-400 text-sm">
                        {formatDate(item.created_at)}
                      </td>
                      <td className="p-4">
                        {item.url && (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-400 hover:text-white"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <EvidencePanel
        evidence={selectedEvidence}
        onClose={() => setSelectedEvidence(null)}
      />
    </div>
  );
}
