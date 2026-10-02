'use client';

import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';
import { FileText, Download, Printer, Copy } from 'lucide-react';

interface ReportSection {
  id: string;
  title: string;
  included: boolean;
}

interface ReportPreviewProps {
  title: string;
  sections: ReportSection[];
  content?: string;
  onExport?: (format: 'pdf' | 'json' | 'csv') => void;
  onPrint?: () => void;
  onCopy?: () => void;
}

export function ReportPreview({
  title,
  sections,
  content,
  onExport,
  onPrint,
  onCopy,
}: ReportPreviewProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-cyan-400" />
          <h3 className="text-white font-medium">{title || 'Report Preview'}</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onCopy}
            className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
            title="Copy"
          >
            <Copy className="w-4 h-4 text-gray-400" />
          </button>
          <button
            onClick={onPrint}
            className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
            title="Print"
          >
            <Printer className="w-4 h-4 text-gray-400" />
          </button>
          <div className="relative group">
            <button className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-white transition-colors">
              <Download className="w-4 h-4" />
              Export
            </button>
            <div className="absolute right-0 top-full mt-1 w-32 bg-gray-800 border border-gray-700 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
              <button
                onClick={() => onExport?.('pdf')}
                className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-700 rounded-t-lg"
              >
                PDF
              </button>
              <button
                onClick={() => onExport?.('json')}
                className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-700"
              >
                JSON
              </button>
              <button
                onClick={() => onExport?.('csv')}
                className="w-full px-3 py-2 text-left text-sm text-gray-300 hover:bg-gray-700 rounded-b-lg"
              >
                CSV
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="p-4">
        <div className="mb-4">
          <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
            Report Sections
          </h4>
          <div className="space-y-1">
            {sections.map((section) => (
              <div
                key={section.id}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-lg text-sm',
                  section.included
                    ? 'bg-gray-800 text-white'
                    : 'bg-gray-900 text-gray-500'
                )}
              >
                <div
                  className={cn(
                    'w-2 h-2 rounded-full',
                    section.included ? 'bg-green-500' : 'bg-gray-600'
                  )}
                />
                {section.title}
              </div>
            ))}
          </div>
        </div>

        {content && (
          <div className="border-t border-gray-800 pt-4">
            <h4 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
              Preview
            </h4>
            <div className="bg-gray-950 rounded-lg p-5 max-h-[32rem] overflow-y-auto">
              <ReactMarkdown
                components={{
                  h1: ({ children }) => (
                    <h1 className="text-xl font-bold text-white mb-3 mt-1">{children}</h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-lg font-semibold text-cyan-300 mb-2 mt-5 first:mt-0">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-base font-semibold text-white mb-2 mt-4">{children}</h3>
                  ),
                  p: ({ children }) => (
                    <p className="text-sm text-gray-300 leading-relaxed mb-2">{children}</p>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc pl-5 space-y-1.5 mb-3">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal pl-5 space-y-1.5 mb-3">{children}</ol>
                  ),
                  li: ({ children }) => (
                    <li className="text-sm text-gray-300 leading-relaxed">{children}</li>
                  ),
                  strong: ({ children }) => (
                    <strong className="text-white font-semibold">{children}</strong>
                  ),
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-cyan-400 hover:text-cyan-300 underline break-all"
                    >
                      {children}
                    </a>
                  ),
                  code: ({ children }) => (
                    <code className="bg-gray-800 px-1.5 py-0.5 rounded text-xs text-cyan-200 font-mono">
                      {children}
                    </code>
                  ),
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
