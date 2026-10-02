'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Plus,
  Search,
  Grid3X3,
  List,
  Filter,
  Clock,
  FileText,
  AlertTriangle,
  Users,
  Loader2,
} from 'lucide-react';
import { useCaseStore } from '@/lib/store';
import { formatDate } from '@/lib/utils';
import api from '@/lib/api';

type StatusFilter = 'all' | 'open' | 'investigating' | 'closed' | 'archived';

const statusColors: Record<string, string> = {
  open: 'bg-blue-500',
  investigating: 'bg-amber-500',
  closed: 'bg-green-500',
  archived: 'bg-gray-500',
};

const statusLabels: Record<string, string> = {
  open: 'Active',
  investigating: 'Investigating',
  closed: 'Completed',
  archived: 'Archived',
};

export default function CasesPage() {
  const { cases, setCases, loading, setLoading } = useCaseStore();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  useEffect(() => {
    fetchCases();
  }, []);

  const fetchCases = async () => {
    setLoading(true);
    try {
      const response = await api.get('/cases');
      setCases(response.data.data);
    } catch (error) {
      console.error('Failed to fetch cases:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredCases = cases.filter((caseItem) => {
    const matchesSearch =
      caseItem.title.toLowerCase().includes(search.toLowerCase()) ||
      caseItem.description.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || caseItem.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Cases</h1>
            <p className="text-gray-400 mt-1">Manage your investigations</p>
          </div>
          <Link
            href="/cases/new"
            className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Case
          </Link>
        </div>

        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search cases..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div className="flex items-center bg-gray-900 border border-gray-800 rounded-lg p-1">
            {(['all', 'open', 'investigating', 'closed', 'archived'] as StatusFilter[]).map(
              (status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    statusFilter === status
                      ? 'bg-gray-800 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {status === 'all' ? 'All' : statusLabels[status]}
                </button>
              )
            )}
          </div>

          <div className="flex items-center bg-gray-900 border border-gray-800 rounded-lg p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-md transition-colors ${
                viewMode === 'grid' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-md transition-colors ${
                viewMode === 'list' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
          </div>
        ) : filteredCases.length === 0 ? (
          <div className="text-center py-24">
            <Filter className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400 text-lg">No cases found</p>
            <p className="text-gray-500 text-sm mt-1">
              {search || statusFilter !== 'all'
                ? 'Try adjusting your filters'
                : 'Create your first investigation'}
            </p>
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredCases.map((caseItem) => (
              <Link
                key={caseItem.id}
                href={`/cases/${caseItem.id}/overview`}
                className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-white font-medium line-clamp-1">{caseItem.title}</h3>
                  <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-gray-800 text-gray-300">
                    <span className={`w-2 h-2 rounded-full ${statusColors[caseItem.status]}`} />
                    {statusLabels[caseItem.status]}
                  </span>
                </div>

                <p className="text-gray-400 text-sm line-clamp-2 mb-4">
                  {caseItem.description || 'No description'}
                </p>

                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    {(caseItem.metadata?.evidenceCount as number) || 0} evidence
                  </span>
                  <span className="flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    {(caseItem.metadata?.claimCount as number) || 0} claims
                  </span>
                  <span className="flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    {(caseItem.metadata?.accountCount as number) || 0} accounts
                  </span>
                </div>

                <div className="flex items-center gap-1 text-xs text-gray-500 mt-3 pt-3 border-t border-gray-800">
                  <Clock className="w-3 h-3" />
                  Updated {formatDate(caseItem.updated_at)}
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="text-left text-gray-400 text-sm border-b border-gray-800">
                  <th className="p-4 font-medium">Title</th>
                  <th className="p-4 font-medium">Target</th>
                  <th className="p-4 font-medium">Status</th>
                  <th className="p-4 font-medium">Evidence</th>
                  <th className="p-4 font-medium">Claims</th>
                  <th className="p-4 font-medium">Last Updated</th>
                  <th className="p-4 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {filteredCases.map((caseItem) => (
                  <tr key={caseItem.id} className="hover:bg-gray-800/50">
                    <td className="p-4">
                      <p className="text-white font-medium">{caseItem.title}</p>
                      <p className="text-gray-500 text-xs">{caseItem.id}</p>
                    </td>
                    <td className="p-4 text-gray-300 text-sm">
                      {caseItem.metadata?.target as string || 'N/A'}
                    </td>
                    <td className="p-4">
                      <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-gray-800 text-gray-300">
                        <span className={`w-2 h-2 rounded-full ${statusColors[caseItem.status]}`} />
                        {statusLabels[caseItem.status]}
                      </span>
                    </td>
                    <td className="p-4 text-gray-300 text-sm">
                      {(caseItem.metadata?.evidenceCount as number) || 0}
                    </td>
                    <td className="p-4 text-gray-300 text-sm">
                      {(caseItem.metadata?.claimCount as number) || 0}
                    </td>
                    <td className="p-4 text-gray-400 text-sm">
                      {formatDate(caseItem.updated_at)}
                    </td>
                    <td className="p-4">
                      <Link
                        href={`/cases/${caseItem.id}/overview`}
                        className="text-cyan-400 hover:text-cyan-300 text-sm"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
