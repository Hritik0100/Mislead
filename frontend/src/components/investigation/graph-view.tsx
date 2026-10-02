'use client';

import { useCallback, useMemo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  MarkerType,
  NodeTypes,
  EdgeTypes,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { GraphData } from '@/lib/types';
import { cn } from '@/lib/utils';
import {
  User,
  FileText,
  AlertTriangle,
  Link2,
  Hash,
  Image,
} from 'lucide-react';

interface GraphViewProps {
  data: GraphData;
  onNodeClick?: (node: Node) => void;
  onEdgeClick?: (edge: Edge) => void;
  className?: string;
}

const nodeTypeIcons: Record<string, React.ElementType> = {
  account: User,
  post: FileText,
  claim: AlertTriangle,
  evidence: Link2,
  hashtag: Hash,
  url: Link2,
  media: Image,
};

const nodeTypeColors: Record<string, string> = {
  account: '#3b82f6',
  post: '#06b6d4',
  claim: '#f59e0b',
  evidence: '#10b981',
  hashtag: '#8b5cf6',
  url: '#ec4899',
  media: '#f97316',
};

const edgeTypeColors: Record<string, string> = {
  posted_by: '#3b82f6',
  supports: '#10b981',
  refutes: '#ef4444',
  mentions: '#f59e0b',
  shares: '#06b6d4',
  related_to: '#64748b',
};

export function GraphView({ data, onNodeClick, onEdgeClick, className }: GraphViewProps) {
  const initialNodes: Node[] = useMemo(
    () =>
      data.nodes.map((node) => ({
        id: node.id,
        position: { x: node.x || 0, y: node.y || 0 },
        data: { label: node.label, type: node.type, ...node.data },
        type: 'default',
        style: {
          background: nodeTypeColors[node.type] || '#64748b',
          color: '#fff',
          border: `2px solid ${nodeTypeColors[node.type] || '#64748b'}`,
          borderRadius: '8px',
          padding: '10px',
          fontSize: '12px',
          fontWeight: 500,
        },
      })),
    [data.nodes]
  );

  const initialEdges: Edge[] = useMemo(
    () =>
      data.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: 'smoothstep',
        animated: true,
        style: {
          stroke: edgeTypeColors[edge.type] || '#64748b',
          strokeWidth: edge.weight ? Math.max(1, Math.min(4, edge.weight)) : 1,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: edgeTypeColors[edge.type] || '#64748b',
        },
        data: { type: edge.type, weight: edge.weight, ...edge.metadata },
      })),
    [data.edges]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeClick?.(node);
    },
    [onNodeClick]
  );

  const handleEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      onEdgeClick?.(edge);
    },
    [onEdgeClick]
  );

  return (
    <div className={cn('w-full h-full bg-gray-900 rounded-lg border border-gray-800', className)}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        fitView
        attributionPosition="bottom-left"
        defaultEdgeOptions={{
          type: 'smoothstep',
          animated: true,
        }}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="#1e293b" />
        <Controls
          className="!bg-gray-800 !border-gray-700 !rounded-lg"
          showInteractive={false}
        />
      </ReactFlow>
    </div>
  );
}
