'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  Search,
  ExternalLink,
  Globe,
  Calendar,
  Loader2,
  Download,
  AlertTriangle,
  CheckCircle2,
} from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { formatDate } from '@/lib/utils';
import api from '@/lib/api';

interface Source {
  id: string;
  url: string;
  type: string;
  platform: string;
  title?: string;
  publishedDate?: string;
  retrievedDate: string;
  content?: string;
}

interface PlatformDef {
  id: string;
  label: string;
  envPrefix: string;
  mode: 'search' | 'urls';
  cookiesEnv?: string;
  loginUrl?: string;
  verifyUrl?: string;
  hint: string;
  placeholder: string;
  disabled?: boolean;
  disabledReason?: string;
}

// Credentials are never entered here. The backend holds them in its own env;
// the UI only names which configured account to use.
const PLATFORMS: PlatformDef[] = [
  {
    id: 'x',
    label: 'X (Twitter)',
    envPrefix: 'X',
    mode: 'search' as const,
    cookiesEnv: 'X_COOKIES_JSON',
    verifyUrl: 'https://x.com/home',
    hint: 'Runs a live search on X with the investigator session.',
    placeholder: 'e.g. CJP protest Delhi',
  },
  {
    id: 'facebook',
    label: 'Facebook',
    envPrefix: 'FB',
    mode: 'urls' as const,
    cookiesEnv: 'FB_COOKIES_JSON',
    loginUrl: 'https://www.facebook.com/login',
    verifyUrl: 'https://www.facebook.com/feed',
    hint: 'Paste a post or photo permalink. Facebook photo posts often have no written caption, so the text shown is the post’s visible text — check the evidence before quoting it.',
    placeholder: 'https://www.facebook.com/photo/?fbid=...',
  },
  {
    id: 'instagram',
    label: 'Instagram',
    envPrefix: 'IG',
    mode: 'urls' as const,
    loginUrl: 'https://www.instagram.com/accounts/login/',
    verifyUrl: 'https://www.instagram.com/',
    hint: 'Paste a public post permalink visible to the investigator account.',
    placeholder: 'https://www.instagram.com/p/...',
  },
];

const BLOCKER_HELP: Record<string, string> = {
  AUTHENTICATION_REQUIRED:
    'The platform rejected the configured credentials. Update them in the backend env, then retry.',
  MFA_REQUIRED:
    'This account needs a verification code (email/SMS/2FA). Complete it manually in the visible browser window, then retry. It is never bypassed.',
  CAPTCHA_REQUIRED: 'A captcha was shown. Solve it manually in the visible browser window, then retry.',
  ACCESS_DENIED: 'The platform denied access for this session. Re-authenticate and retry.',
  RATE_LIMITED: 'Rate limited by the platform. Wait before retrying.',
  BLOCKED: 'The platform blocked the session. Re-authenticate before retrying.',
};

export default function CaseSourcesPage() {
  const params = useParams();
  const caseId = params.id as string;
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [platformFilter, setPlatformFilter] = useState<string>('all');
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);

  const [platform, setPlatform] = useState('x');
  const [target, setTarget] = useState('');
  const [collecting, setCollecting] = useState(false);
  const [collectResult, setCollectResult] = useState<{
    status?: string;
    stored?: number;
    received?: number;
    deduped?: number;
    reposts?: number;
    claims?: number;
    errors?: string[];
  } | null>(null);

  useEffect(() => {
    fetchSources();
  }, [caseId]);

  const fetchSources = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/cases/${caseId}/sources`);
      setSources(response.data.data || []);
    } catch (error) {
      console.error('Failed to fetch sources:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredSources = sources.filter((source) => {
    const matchesSearch =
      source.url.toLowerCase().includes(search.toLowerCase()) ||
      source.title?.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === 'all' || source.type === typeFilter;
    const matchesPlatform = platformFilter === 'all' || source.platform === platformFilter;
    return matchesSearch && matchesType && matchesPlatform;
  });

  const activePlatform = PLATFORMS.find((p) => p.id === platform)!;

  const runCollection = async () => {
    const value = target.trim();
    if (!value) return;
    const p = activePlatform;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const source: Record<string, any> = {
      type: 'auth_browser',
      driver: 'playwright',
      platform: p.id,
      env_prefix: p.envPrefix,
      session: `ui-${p.id}`,
      verify_url: p.verifyUrl,
      max_items: 20,
    };
    if (p.cookiesEnv) source.cookies_env = p.cookiesEnv;
    if (p.loginUrl) source.login_url = p.loginUrl;
    if (p.mode === 'search') {
      source.mode = 'search';
      source.search_query = value;
      source.search_url = `https://x.com/search?q=${encodeURIComponent(value)}&f=live`;
    } else {
      source.mode = 'collect_urls';
      source.urls = [value];
    }

    setCollecting(true);
    setCollectResult(null);
    try {
      // A browser-driven collection legitimately takes minutes, so this one call
      // gets a long timeout instead of the global default.
      const response = await api.post(
        `/cases/${caseId}/collect`,
        { sources: [source], max_items: 20 },
        { timeout: 15 * 60 * 1000 }
      );
      setCollectResult(response.data);
      await fetchSources();
    } catch (error: any) {
      const timedOut = error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '');
      if (timedOut) {
        // The worker keeps running server-side, so re-read rather than claim failure.
        await fetchSources();
        setCollectResult({
          status: 'still_running',
          errors: [
            'This collection is still running on the server. The page will not refresh itself — reopen Sources in a moment to see the results.',
          ],
        });
      } else {
        setCollectResult({
          status: 'ERROR',
          errors: [error?.response?.data?.detail || error?.message || 'Collection failed'],
        });
      }
    } finally {
      setCollecting(false);
    }
  };

  return (
    <div className="p-6">
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Download className="w-4 h-4 text-cyan-400" />
          <h2 className="text-white font-medium">Collect from a social platform</h2>
        </div>
        <p className="text-gray-400 text-xs mb-4">
          Uses the investigator&apos;s own authenticated session. Credentials stay on the
          server; verification codes and captchas are never bypassed and must be completed
          manually in the browser window that opens.
        </p>
        <div className="flex flex-col lg:flex-row gap-3 items-start">
          <select
            value={platform}
            onChange={(e) => {
              setPlatform(e.target.value);
              setCollectResult(null);
            }}
            className="px-3 py-2 bg-gray-800 border border-gray-800 rounded-lg text-white focus:outline-none focus:border-cyan-500"
          >
            {PLATFORMS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
                {p.disabled ? ' (unavailable)' : ''}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') runCollection();
            }}
            placeholder={activePlatform.placeholder}
            disabled={activePlatform.disabled}
            className="flex-1 px-3 py-2 bg-gray-800 border border-gray-800 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
          />
          <button
            onClick={runCollection}
            disabled={collecting || !target.trim() || activePlatform.disabled}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg text-white font-medium flex items-center gap-2 whitespace-nowrap"
          >
            {collecting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Collecting
              </>
            ) : (
              'Collect'
            )}
          </button>
        </div>
        <p className="text-gray-500 text-xs mt-2">
          {activePlatform.disabled ? activePlatform.disabledReason : activePlatform.hint}
        </p>

        {collectResult && (
          <div
            className={`mt-4 rounded-lg border p-3 text-sm ${
              collectResult.status === 'succeeded'
                ? 'border-green-800 bg-green-900/20 text-green-300'
                : 'border-amber-800 bg-amber-900/20 text-amber-200'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              {collectResult.status === 'succeeded' ? (
                <CheckCircle2 className="w-4 h-4" />
              ) : (
                <AlertTriangle className="w-4 h-4" />
              )}
              <span className="font-medium">
                {collectResult.status === 'succeeded'
                  ? collectResult.stored
                    ? `Collected ${collectResult.stored} new post${
                        collectResult.stored === 1 ? '' : 's'
                      }${
                        collectResult.deduped
                          ? ` · ${collectResult.deduped} already collected`
                          : ''
                      }`
                    : `Nothing new · all ${collectResult.received ?? 0} posts were already collected`
                  : collectResult.status === 'still_running'
                    ? 'Collection is taking longer than expected'
                    : `Collection did not complete (${collectResult.status ?? 'unknown'})`}
              </span>
            </div>
            {collectResult.claims ? (
              <p className="text-xs opacity-80">{collectResult.claims} claims extracted</p>
            ) : null}
            {(collectResult.errors || []).map((e, i) => (
              <p key={i} className="text-xs mt-1 break-words">
                {e}
                {BLOCKER_HELP[e] ? ` — ${BLOCKER_HELP[e]}` : ''}
              </p>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Sources</h1>
          <p className="text-gray-400 mt-1">{sources.length} sources collected</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              placeholder="Search sources..."
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
            <option value="webpage">Webpage</option>
            <option value="archive">Archive</option>
            <option value="social">Social</option>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
            </div>
          ) : filteredSources.length === 0 ? (
            <div className="text-center py-12">
              <Globe className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No sources found</p>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-gray-400 text-sm border-b border-gray-800">
                    <th className="p-4 font-medium">URL</th>
                    <th className="p-4 font-medium">Type</th>
                    <th className="p-4 font-medium">Platform</th>
                    <th className="p-4 font-medium">Published</th>
                    <th className="p-4 font-medium">Retrieved</th>
                    <th className="p-4 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {filteredSources.map((source) => (
                    <tr
                      key={source.id}
                      className={`hover:bg-gray-800/50 cursor-pointer ${
                        selectedSource?.id === source.id ? 'bg-gray-800' : ''
                      }`}
                      onClick={() => setSelectedSource(source)}
                    >
                      <td className="p-4">
                        <p className="text-cyan-400 text-sm truncate max-w-xs">
                          {source.url}
                        </p>
                        {source.title && (
                          <p className="text-gray-500 text-xs mt-1 truncate">{source.title}</p>
                        )}
                      </td>
                      <td className="p-4">
                        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-800 text-gray-300">
                          {source.type}
                        </span>
                      </td>
                      <td className="p-4 text-gray-300 text-sm">{source.platform}</td>
                      <td className="p-4 text-gray-400 text-sm">
                        {source.publishedDate ? formatDate(source.publishedDate) : 'N/A'}
                      </td>
                      <td className="p-4 text-gray-400 text-sm">
                        {formatDate(source.retrievedDate)}
                      </td>
                      <td className="p-4">
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-400 hover:text-white"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="lg:col-span-1">
          {selectedSource ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sticky top-6">
              <h3 className="text-white font-medium mb-4">Source Details</h3>
              
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">URL</p>
                  <a
                    href={selectedSource.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-cyan-400 text-sm break-all hover:text-cyan-300"
                  >
                    {selectedSource.url}
                  </a>
                </div>

                {selectedSource.title && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Title</p>
                    <p className="text-white text-sm">{selectedSource.title}</p>
                  </div>
                )}

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Type</p>
                  <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-700 text-gray-300">
                    {selectedSource.type}
                  </span>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Platform</p>
                  <p className="text-white text-sm">{selectedSource.platform}</p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Published</p>
                  <p className="text-white text-sm">
                    {selectedSource.publishedDate
                      ? formatDate(selectedSource.publishedDate)
                      : 'N/A'}
                  </p>
                </div>

                <div className="bg-gray-800 rounded-lg p-3">
                  <p className="text-gray-400 text-xs mb-2">Retrieved</p>
                  <p className="text-white text-sm">{formatDate(selectedSource.retrievedDate)}</p>
                </div>

                {selectedSource.content && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-400 text-xs mb-2">Content Preview</p>
                    <p className="text-gray-300 text-sm line-clamp-6">{selectedSource.content}</p>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center py-12">
              <Globe className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">Select a source to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
