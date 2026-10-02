'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  Search,
  ExternalLink,
  Heart,
  MessageCircle,
  Repeat2,
  Filter,
  FileText,
  Loader2,
} from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { formatDate } from '@/lib/utils';
import api from '@/lib/api';
import { Post } from '@/lib/types';

export default function CasePostsPage() {
  const params = useParams();
  const caseId = params.id as string;
  const { posts, setPosts, loading, setLoading } = useInvestigationStore();
  const [search, setSearch] = useState('');
  const [platformFilter, setPlatformFilter] = useState<string>('all');
  const [selectedPost, setSelectedPost] = useState<Post | null>(null);

  useEffect(() => {
    fetchPosts();
  }, [caseId]);

  const fetchPosts = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/cases/${caseId}/posts`);
      setPosts(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch posts:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredPosts = posts.filter((post) => {
    const matchesSearch = post.content.toLowerCase().includes(search.toLowerCase());
    const matchesPlatform = platformFilter === 'all' || post.platform === platformFilter;
    return matchesSearch && matchesPlatform;
  });

  const getPlatformColor = (platform: string) => {
    const colors: Record<string, string> = {
      twitter: '#1DA1F2',
      youtube: '#FF0000',
      telegram: '#0088cc',
      matrix: '#0DBD8B',
      web: '#6366f1',
    };
    return colors[platform.toLowerCase()] || '#6b7280';
  };

  const truncateText = (text: string, maxLength: number) => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '...';
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Posts</h1>
          <p className="text-gray-400 mt-1">{posts.length} posts collected</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search posts..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : filteredPosts.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No posts found</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredPosts.map((post) => (
                <div
                  key={post.id}
                  className={`bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors cursor-pointer ${
                    selectedPost?.id === post.id ? 'border-cyan-600' : ''
                  }`}
                  onClick={() => setSelectedPost(post)}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0">
                      <span
                        className="inline-flex items-center px-2 py-1 rounded text-xs font-medium"
                        style={{
                          backgroundColor: `${getPlatformColor(post.platform)}20`,
                          color: getPlatformColor(post.platform),
                        }}
                      >
                        {post.platform}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      {post.author_display || post.author_username ? (
                        <a
                          href={post.author_profile || undefined}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-cyan-400 text-xs font-medium hover:underline mb-1 inline-block"
                        >
                          @{post.author_display || post.author_username}
                        </a>
                      ) : null}
                      <p className="text-gray-300 text-sm mb-2">{truncateText(post.content, 200)}</p>
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <Heart className="w-3 h-3" />
                          {post.likes || 0}
                        </span>
                        <span className="flex items-center gap-1">
                          <Repeat2 className="w-3 h-3" />
                          {post.shares || 0}
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageCircle className="w-3 h-3" />
                          {post.comments || 0}
                        </span>
                        <span>•</span>
                        <span>{formatDate(post.posted_at)}</span>
                      </div>
                    </div>
                    {post.post_url && (
                      <a
                        href={post.post_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-400 hover:text-white"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="lg:col-span-1">
          {selectedPost ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sticky top-6">
              <h3 className="text-white font-medium mb-4">Post Details</h3>
              
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Content</p>
                  <p className="text-white text-sm whitespace-pre-wrap">{selectedPost.content}</p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Platform</p>
                  <span
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium"
                    style={{
                      backgroundColor: `${getPlatformColor(selectedPost.platform)}20`,
                      color: getPlatformColor(selectedPost.platform),
                    }}
                  >
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: getPlatformColor(selectedPost.platform) }}
                    />
                    {selectedPost.platform}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-gray-800 rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-white">{selectedPost.likes || 0}</p>
                    <p className="text-gray-400 text-xs">Likes</p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-white">{selectedPost.shares || 0}</p>
                    <p className="text-gray-400 text-xs">Shares</p>
                  </div>
                  <div className="bg-gray-800 rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-white">{selectedPost.comments || 0}</p>
                    <p className="text-gray-400 text-xs">Comments</p>
                  </div>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Posted At</p>
                  <p className="text-white text-sm">{formatDate(selectedPost.posted_at)}</p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Collected At</p>
                  <p className="text-white text-sm">{formatDate(selectedPost.collected_at)}</p>
                </div>

                {selectedPost.topics && selectedPost.topics.length > 0 && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Topics</p>
                    <div className="flex flex-wrap gap-2">
                      {selectedPost.topics.map((topic) => (
                        <span key={topic} className="px-2 py-1 bg-gray-700 rounded text-xs text-white">
                          {topic}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedPost.sentiment && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Sentiment</p>
                    <span
                      className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                        selectedPost.sentiment === 'positive'
                          ? 'bg-green-900/30 text-green-400'
                          : selectedPost.sentiment === 'negative'
                          ? 'bg-red-900/30 text-red-400'
                          : 'bg-gray-700 text-gray-300'
                      }`}
                    >
                      {selectedPost.sentiment}
                    </span>
                  </div>
                )}

                {selectedPost.media_urls && selectedPost.media_urls.length > 0 && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Media ({selectedPost.media_urls.length})</p>
                    <div className="grid grid-cols-2 gap-2">
                      {selectedPost.media_urls.slice(0, 4).map((url, i) => (
                        <div key={i} className="aspect-square bg-gray-700 rounded-lg flex items-center justify-center">
                          <img src={url} alt="" className="w-full h-full object-cover rounded-lg" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center py-12">
              <FileText className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">Select a post to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
