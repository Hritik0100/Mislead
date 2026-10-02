'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Image, Film, Music, FileText, ExternalLink, Eye } from 'lucide-react';

export interface MediaItem {
  id: string;
  type: 'image' | 'video' | 'audio' | 'document';
  url: string;
  thumbnail?: string;
  title?: string;
  description?: string;
  hash?: string;
  firstObserved?: string;
  postCount?: number;
  exifData?: Record<string, string>;
}

interface MediaGridProps {
  items: MediaItem[];
  onItemClick?: (item: MediaItem) => void;
}

const typeIcons: Record<string, React.ElementType> = {
  image: Image,
  video: Film,
  audio: Music,
  document: FileText,
};

const typeColors: Record<string, string> = {
  image: 'bg-blue-900/30 text-blue-400',
  video: 'bg-purple-900/30 text-purple-400',
  audio: 'bg-green-900/30 text-green-400',
  document: 'bg-amber-900/30 text-amber-400',
};

export function MediaGrid({ items, onItemClick }: MediaGridProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-500">
        <Image className="w-12 h-12 mb-4 opacity-50" />
        <p>No media items collected</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {items.map((item) => {
        const Icon = typeIcons[item.type] || FileText;
        const colorClass = typeColors[item.type] || 'bg-gray-800 text-gray-400';

        return (
          <div
            key={item.id}
            className={cn(
              'relative group bg-gray-900 border border-gray-800 rounded-lg overflow-hidden',
              'hover:border-gray-700 transition-all duration-200',
              onItemClick && 'cursor-pointer'
            )}
            onMouseEnter={() => setHoveredId(item.id)}
            onMouseLeave={() => setHoveredId(null)}
            onClick={() => onItemClick?.(item)}
          >
            <div className="aspect-square bg-gray-800 flex items-center justify-center">
              {item.thumbnail ? (
                <img
                  src={item.thumbnail}
                  alt={item.title || 'Media'}
                  className="w-full h-full object-cover"
                />
              ) : (
                <Icon className="w-12 h-12 text-gray-600" />
              )}
            </div>

            <div className="absolute top-2 right-2">
              <span className={cn('inline-flex items-center px-2 py-1 rounded text-[10px] font-medium', colorClass)}>
                {item.type.toUpperCase()}
              </span>
            </div>

            {hoveredId === item.id && (
              <div className="absolute inset-0 bg-black/60 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button className="p-2 bg-white/10 rounded-lg hover:bg-white/20 transition-colors">
                  <Eye className="w-5 h-5 text-white" />
                </button>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 bg-white/10 rounded-lg hover:bg-white/20 transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink className="w-5 h-5 text-white" />
                </a>
              </div>
            )}

            <div className="p-3">
              <p className="text-white text-sm font-medium truncate">
                {item.title || `Media ${item.id}`}
              </p>
              {item.description && (
                <p className="text-gray-400 text-xs mt-1 truncate">{item.description}</p>
              )}
              <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                {item.firstObserved && (
                  <span>{new Date(item.firstObserved).toLocaleDateString()}</span>
                )}
                {item.postCount && <span>• {item.postCount} posts</span>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
