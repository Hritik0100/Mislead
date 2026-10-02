'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  Upload,
  Search,
  Image,
  Film,
  Music,
  FileText,
  X,
  Loader2,
  ExternalLink,
  Copy,
  Hash,
} from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { MediaGrid, MediaItem } from '@/components/investigation/media-grid';
import { formatDate } from '@/lib/utils';
import api from '@/lib/api';

export default function CaseMediaPage() {
  const params = useParams();
  const caseId = params.id as string;
  const [mediaItems, setMediaItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<MediaItem | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>('all');

  useEffect(() => {
    fetchMedia();
  }, [caseId]);

  const fetchMedia = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/cases/${caseId}/media`);
      setMediaItems(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch media:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredMedia = mediaItems.filter(
    (item) => typeFilter === 'all' || item.type === typeFilter
  );

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Media</h1>
          <p className="text-gray-400 mt-1">{mediaItems.length} media items collected</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Types</option>
            <option value="image">Images</option>
            <option value="video">Videos</option>
            <option value="audio">Audio</option>
            <option value="document">Documents</option>
          </select>
          <button className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors">
            <Upload className="w-4 h-4" />
            Upload Media
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : (
            <MediaGrid items={filteredMedia} onItemClick={setSelectedItem} />
          )}
        </div>

        <div className="lg:col-span-1">
          {selectedItem ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sticky top-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-medium">Media Details</h3>
                <button
                  onClick={() => setSelectedItem(null)}
                  className="p-1 hover:bg-gray-800 rounded transition-colors"
                >
                  <X className="w-4 h-4 text-gray-400" />
                </button>
              </div>
              
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Preview</p>
                  <div className="aspect-video bg-gray-900 rounded-lg flex items-center justify-center">
                    {selectedItem.thumbnail ? (
                      <img
                        src={selectedItem.thumbnail}
                        alt={selectedItem.title}
                        className="w-full h-full object-contain rounded-lg"
                      />
                    ) : (
                      <div className="text-center">
                        {selectedItem.type === 'image' && <Image className="w-12 h-12 text-gray-600 mx-auto" />}
                        {selectedItem.type === 'video' && <Film className="w-12 h-12 text-gray-600 mx-auto" />}
                        {selectedItem.type === 'audio' && <Music className="w-12 h-12 text-gray-600 mx-auto" />}
                        {selectedItem.type === 'document' && <FileText className="w-12 h-12 text-gray-600 mx-auto" />}
                      </div>
                    )}
                  </div>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Title</p>
                  <p className="text-white text-sm">{selectedItem.title || 'Untitled'}</p>
                </div>

                {selectedItem.description && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Description</p>
                    <p className="text-white text-sm">{selectedItem.description}</p>
                  </div>
                )}

                <div className="bg-gray-800 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-gray-400 text-xs">Hash</p>
                    <button
                      onClick={() => copyToClipboard(selectedItem.hash || '')}
                      className="p-1 hover:bg-gray-700 rounded transition-colors"
                    >
                      <Copy className="w-3 h-3 text-gray-400" />
                    </button>
                  </div>
                  <code className="text-xs font-mono text-cyan-400 break-all">
                    {selectedItem.hash || 'N/A'}
                  </code>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">EXIF Data</p>
                  {selectedItem.exifData && Object.keys(selectedItem.exifData).length > 0 ? (
                    <div className="space-y-1">
                      {Object.entries(selectedItem.exifData).map(([key, value]) => (
                        <div key={key} className="flex justify-between text-xs">
                          <span className="text-gray-500">{key}</span>
                          <span className="text-white">{value}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-gray-500 text-sm">No EXIF data</p>
                  )}
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">First Observed</p>
                  <p className="text-white text-sm">
                    {selectedItem.firstObserved ? formatDate(selectedItem.firstObserved) : 'N/A'}
                  </p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Associated Posts</p>
                  <p className="text-white text-sm">{selectedItem.postCount || 0} posts</p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Similarity Matches</p>
                  <p className="text-white text-sm">0 matches found</p>
                </div>

                <a
                  href={selectedItem.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 w-full px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                  Open Original
                </a>
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center py-12">
              <Image className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">Select media to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
