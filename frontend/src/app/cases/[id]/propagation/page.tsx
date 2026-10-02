'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  GitBranch,
  Filter,
  LayoutGrid,
  Network,
  Clock,
  Users,
  FileText,
  Loader2,
} from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { GraphView } from '@/components/investigation/graph-view';
import { StatsCard } from '@/components/investigation/stats-card';
import api from '@/lib/api';
import { Node, Edge } from 'reactflow';

export default function CasePropagationPage() {
  const params = useParams();
  const caseId = params.id as string;
  const { graph, setGraph, loading, setLoading } = useInvestigationStore();
  const [layout, setLayout] = useState<'hierarchical' | 'force'>('force');
  const [platformFilter, setPlatformFilter] = useState<string>('all');
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);

  useEffect(() => {
    fetchGraph();
  }, [caseId]);

  const fetchGraph = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/cases/${caseId}/graph`);
      setGraph(response.data);
    } catch (error) {
      console.error('Failed to fetch graph:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleNodeClick = (node: Node) => {
    setSelectedNode(node);
    setSelectedEdge(null);
  };

  const handleEdgeClick = (edge: Edge) => {
    setSelectedEdge(edge);
    setSelectedNode(null);
  };

  const stats = graph
    ? {
        spreadDuration: '24h 32m',
        postsPerHour: (graph.nodes.length / 24).toFixed(1),
        uniqueAccounts: graph.nodes.filter((n) => n.type === 'account').length,
        platforms: [...new Set(graph.nodes.map((n) => n.type))].length,
      }
    : null;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Propagation</h1>
          <p className="text-gray-400 mt-1">Content spread and influence network</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={layout}
            onChange={(e) => setLayout(e.target.value as any)}
            className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="force">Force-directed</option>
            <option value="hierarchical">Hierarchical</option>
          </select>
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
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <StatsCard
            title="Spread Duration"
            value={stats.spreadDuration}
            icon={Clock}
            iconColor="text-cyan-400"
          />
          <StatsCard
            title="Posts/Hour"
            value={stats.postsPerHour}
            icon={FileText}
            iconColor="text-blue-400"
          />
          <StatsCard
            title="Unique Accounts"
            value={stats.uniqueAccounts}
            icon={Users}
            iconColor="text-green-400"
          />
          <StatsCard
            title="Platforms"
            value={stats.platforms}
            icon={Network}
            iconColor="text-purple-400"
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3">
          {loading ? (
            <div className="flex items-center justify-center h-[600px] bg-gray-900 border border-gray-800 rounded-lg">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : graph ? (
            <div className="h-[600px]">
              <GraphView
                data={graph}
                onNodeClick={handleNodeClick}
                onEdgeClick={handleEdgeClick}
              />
            </div>
          ) : (
            <div className="h-[600px] bg-gray-900 border border-gray-800 rounded-lg flex items-center justify-center">
              <div className="text-center">
                <GitBranch className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">No graph data available</p>
              </div>
            </div>
          )}
        </div>

        <div className="lg:col-span-1">
          {selectedNode ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sticky top-6">
              <h3 className="text-white font-medium mb-4">Node Details</h3>
              
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Type</p>
                  <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-cyan-900/30 text-cyan-400 capitalize">
                    {selectedNode.data.type}
                  </span>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Label</p>
                  <p className="text-white text-sm">{selectedNode.data.label}</p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Connections</p>
                  <p className="text-white text-sm">
                    {graph?.edges.filter(
                      (e) => e.source === selectedNode.id || e.target === selectedNode.id
                    ).length || 0} edges
                  </p>
                </div>

                {Object.entries(selectedNode.data)
                  .filter(([key]) => !['type', 'label'].includes(key))
                  .map(([key, value]) => (
                    <div key={key} className="bg-gray-800 rounded-lg p-3">
                      <p className="text-gray-400 text-xs mb-2 capitalize">
                        {key.replace(/_/g, ' ')}
                      </p>
                      <p className="text-white text-sm">
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </p>
                    </div>
                  ))}
              </div>
            </div>
          ) : selectedEdge ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sticky top-6">
              <h3 className="text-white font-medium mb-4">Edge Details</h3>
              
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Relationship</p>
                  <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-900/30 text-purple-400 capitalize">
                    {selectedEdge.data?.type || selectedEdge.id}
                  </span>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Source</p>
                  <p className="text-cyan-400 text-sm font-mono">{selectedEdge.source}</p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Target</p>
                  <p className="text-cyan-400 text-sm font-mono">{selectedEdge.target}</p>
                </div>

                {selectedEdge.data?.weight && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Weight</p>
                    <p className="text-white text-sm">{selectedEdge.data.weight}</p>
                  </div>
                )}

                {selectedEdge.data?.evidence && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Evidence</p>
                    <p className="text-white text-sm">{selectedEdge.data.evidence}</p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center py-12">
              <GitBranch className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">Click a node or edge to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
