'use client';

import { X, ExternalLink, Copy, Hash, Calendar, Tag } from 'lucide-react';
import { Evidence } from '@/lib/types';
import { formatDate } from '@/lib/utils';

interface EvidencePanelProps {
  evidence: Evidence | null;
  onClose: () => void;
}

export function EvidencePanel({ evidence, onClose }: EvidencePanelProps) {
  if (!evidence) return null;

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="fixed right-0 top-0 h-full w-[480px] bg-gray-900 border-l border-gray-800 z-50 overflow-y-auto">
      <div className="sticky top-0 bg-gray-900 border-b border-gray-800 p-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-white">Evidence Details</h3>
        <button
          onClick={onClose}
          className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
        >
          <X className="w-5 h-5 text-gray-400" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Title</h4>
          <p className="text-white">{evidence.title}</p>
        </div>

        {evidence.description && (
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">Description</h4>
            <p className="text-gray-300">{evidence.description}</p>
          </div>
        )}

        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Type</h4>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-900/30 text-blue-400 border border-blue-800">
            {evidence.type.toUpperCase()}
          </span>
        </div>

        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Hash</h4>
          <div className="flex items-center gap-2">
            <code className="text-xs font-mono text-cyan-400 bg-gray-800 px-2 py-1 rounded flex-1 overflow-x-auto">
              {evidence.hash || 'N/A'}
            </code>
            {evidence.hash && (
              <button
                onClick={() => copyToClipboard(evidence.hash!)}
                className="p-1.5 hover:bg-gray-800 rounded transition-colors"
              >
                <Copy className="w-4 h-4 text-gray-400" />
              </button>
            )}
          </div>
        </div>

        {evidence.url && (
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">Source URL</h4>
            <a
              href={evidence.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300 text-sm break-all"
            >
              <ExternalLink className="w-4 h-4 flex-shrink-0" />
              {evidence.url}
            </a>
          </div>
        )}

        {evidence.file_path && (
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">File Path</h4>
            <code className="text-xs font-mono text-gray-300 bg-gray-800 px-2 py-1 rounded block overflow-x-auto">
              {evidence.file_path}
            </code>
          </div>
        )}

        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Tags</h4>
          <div className="flex flex-wrap gap-2">
            {evidence.tags.length > 0 ? (
              evidence.tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-gray-800 text-gray-300"
                >
                  <Tag className="w-3 h-3" />
                  {tag}
                </span>
              ))
            ) : (
              <span className="text-gray-500 text-sm">No tags</span>
            )}
          </div>
        </div>

        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Added By</h4>
          <p className="text-gray-300 text-sm">{evidence.added_by}</p>
        </div>

        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Created At</h4>
          <div className="flex items-center gap-2 text-gray-300 text-sm">
            <Calendar className="w-4 h-4" />
            {formatDate(evidence.created_at)}
          </div>
        </div>

        {evidence.claim_id && (
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">Linked Claim</h4>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-900/30 text-purple-400 border border-purple-800">
              {evidence.claim_id}
            </span>
          </div>
        )}

        {evidence.metadata && Object.keys(evidence.metadata).length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">Metadata</h4>
            <pre className="text-xs font-mono text-gray-300 bg-gray-800 p-3 rounded overflow-x-auto">
              {JSON.stringify(evidence.metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
