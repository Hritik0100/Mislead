'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Activity,
  FileText,
  AlertTriangle,
  Users,
  Plus,
  Database,
  ArrowRight,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { StatsCard } from '@/components/investigation/stats-card';
import { useCaseStore } from '@/lib/store';
import api from '@/lib/api';

const statusColors: Record<string, string> = {
  open: 'bg-blue-500',
  investigating: 'bg-amber-500',
  closed: 'bg-green-500',
  archived: 'bg-gray-500',
};

const platformData = [
  { name: 'X/Twitter', value: 45, color: '#1DA1F2' },
  { name: 'YouTube', value: 25, color: '#FF0000' },
  { name: 'Telegram', value: 15, color: '#0088cc' },
  { name: 'Web', value: 10, color: '#6366f1' },
  { name: 'Matrix', value: 5, color: '#0DBD8B' },
];

const statusDistribution = [
  { name: 'Active', value: 12, color: '#3b82f6' },
  { name: 'Investigating', value: 8, color: '#f59e0b' },
  { name: 'Closed', value: 24, color: '#10b981' },
  { name: 'Archived', value: 6, color: '#6b7280' },
];

export default function DashboardPage() {
  const { cases, setCases, loading, setLoading } = useCaseStore();
  const [stats, setStats] = useState({
    activeInvestigations: 0,
    evidenceCollected: 0,
    claimsAnalyzed: 0,
    accountsDiscovered: 0,
  });

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [casesRes, statsRes] = await Promise.all([
        api.get('/cases?limit=5'),
        api.get('/stats/dashboard'),
      ]);
      setCases(casesRes.data.data);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Dashboard</h1>
            <p className="text-gray-400 mt-1">OSINT Nexus Investigation Platform</p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/cases/new"
              className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Investigation
            </Link>
            <button className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors">
              <Database className="w-4 h-4" />
              Load Demo Data
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatsCard
            title="Active Investigations"
            value={stats.activeInvestigations}
            change="+2 this week"
            changeType="positive"
            icon={Activity}
            iconColor="text-blue-400"
          />
          <StatsCard
            title="Evidence Collected"
            value={stats.evidenceCollected}
            change="+24 today"
            changeType="positive"
            icon={FileText}
            iconColor="text-green-400"
          />
          <StatsCard
            title="Claims Analyzed"
            value={stats.claimsAnalyzed}
            change="+8 pending"
            changeType="neutral"
            icon={AlertTriangle}
            iconColor="text-amber-400"
          />
          <StatsCard
            title="Accounts Discovered"
            value={stats.accountsDiscovered}
            change="+12 new"
            changeType="positive"
            icon={Users}
            iconColor="text-purple-400"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-white font-medium mb-4">Investigation Status</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={statusDistribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a1f2e',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {statusDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-white font-medium mb-4">Platform Distribution</h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={platformData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {platformData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1a1f2e',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap justify-center gap-2 mt-2">
              {platformData.map((platform) => (
                <div key={platform.name} className="flex items-center gap-1 text-xs text-gray-400">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: platform.color }} />
                  {platform.name}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-white font-medium">Recent Investigations</h3>
            <Link href="/cases" className="text-cyan-400 hover:text-cyan-300 text-sm flex items-center gap-1">
              View all <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : cases.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400">No investigations yet</p>
              <Link
                href="/cases/new"
                className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors"
              >
                <Plus className="w-4 h-4" />
                Start your first investigation
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-gray-400 text-sm border-b border-gray-800">
                    <th className="pb-3 font-medium">Title</th>
                    <th className="pb-3 font-medium">Target</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Evidence</th>
                    <th className="pb-3 font-medium">Last Updated</th>
                    <th className="pb-3 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {cases.map((caseItem) => (
                    <tr key={caseItem.id} className="hover:bg-gray-800/50">
                      <td className="py-3">
                        <p className="text-white font-medium">{caseItem.title}</p>
                        <p className="text-gray-500 text-xs">{caseItem.id}</p>
                      </td>
                      <td className="py-3 text-gray-300 text-sm">
                        {caseItem.metadata?.target as string || 'N/A'}
                      </td>
                      <td className="py-3">
                        <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium bg-gray-800 text-gray-300">
                          <span className={`w-2 h-2 rounded-full ${statusColors[caseItem.status]}`} />
                          {caseItem.status}
                        </span>
                      </td>
                      <td className="py-3 text-gray-300 text-sm">
                        {(caseItem.metadata?.evidenceCount as number) || 0}
                      </td>
                      <td className="py-3 text-gray-400 text-sm">
                        {new Date(caseItem.updated_at).toLocaleDateString()}
                      </td>
                      <td className="py-3">
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

        <div className="mt-6 bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-white font-medium mb-4">Collection Jobs</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-gray-400 text-sm">X/Twitter Collector</span>
                <span className="flex items-center gap-1 text-green-400 text-xs">
                  <CheckCircle className="w-3 h-3" />
                  Running
                </span>
              </div>
              <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                <div className="w-2/3 h-full bg-green-500 rounded-full" />
              </div>
              <p className="text-gray-500 text-xs mt-2">142/210 posts collected</p>
            </div>

            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-gray-400 text-sm">YouTube Scraper</span>
                <span className="flex items-center gap-1 text-amber-400 text-xs">
                  <Clock className="w-3 h-3" />
                  Queued
                </span>
              </div>
              <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                <div className="w-0 h-full bg-amber-500 rounded-full" />
              </div>
              <p className="text-gray-500 text-xs mt-2">Waiting to start</p>
            </div>

            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-gray-400 text-sm">Telegram Monitor</span>
                <span className="flex items-center gap-1 text-red-400 text-xs">
                  <XCircle className="w-3 h-3" />
                  Failed
                </span>
              </div>
              <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                <div className="w-1/4 h-full bg-red-500 rounded-full" />
              </div>
              <p className="text-gray-500 text-xs mt-2">Rate limited - retrying in 5m</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
