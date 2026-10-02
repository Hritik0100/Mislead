'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  FileText,
  Users,
  AlertTriangle,
  Link2,
  Clock,
  Activity,
  Loader2,
  ExternalLink,
  Download,
} from 'lucide-react';
import { StatsCard } from '@/components/investigation/stats-card';
import { AssessmentBadge } from '@/components/investigation/assessment-badge';
import { TimelineView } from '@/components/investigation/timeline-view';
import { GraphView } from '@/components/investigation/graph-view';
import { useCaseStore, useInvestigationStore } from '@/lib/store';
import { formatDate } from '@/lib/utils';
import api from '@/lib/api';
import { buildCollectSources, runCollection } from '@/lib/collect';
import toast from 'react-hot-toast';

export default function CaseOverviewPage() {
  const params = useParams();
  const caseId = params.id as string;
  const { currentCase, setCurrentCase, loading, setLoading } = useCaseStore();
  const { accounts, posts, claims, evidence, graph, timeline, setAccounts, setPosts, setClaims, setEvidence, setGraph, setTimeline } = useInvestigationStore();
  const [aiSummary, setAiSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [collecting, setCollecting] = useState(false);
  const [termInput, setTermInput] = useState('');
  const [savingTerms, setSavingTerms] = useState(false);

  /** Add real search terms to an existing case (objectives are not terms). */
  const addSearchTerms = async () => {
    const terms = termInput
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);
    if (terms.length === 0) return;
    setSavingTerms(true);
    try {
      await api.post(`/cases/${caseId}/keywords`, { keywords: terms });
      setTermInput('');
      await fetchCaseData();
      toast.success(`Added ${terms.length} search term(s)`);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Could not save search terms');
    } finally {
      setSavingTerms(false);
    }
  };
  const [collectResult, setCollectResult] = useState<{
    status?: string;
    stored?: number;
    received?: number;
    deduped?: number;
    claims?: number;
    errors?: string[];
  } | null>(null);

  /**
   * Creating a case only creates the container - no sources are fetched. This
   * is the visible way to actually populate an empty case, using the case's own
   * platforms and keywords.
   */
  /** Run a collection and reflect the real outcome (including partial errors). */
  const runCollectionNow = async (sources: any[]) => {
    setCollecting(true);
    setCollectResult(null);
    try {
      const res = await runCollection(caseId, sources);
      setCollectResult(res);
      await fetchCaseData();
    } catch (error: any) {
      setCollectResult({
        status: 'ERROR',
        errors: [
          error?.code === 'ECONNABORTED'
            ? 'Still running on the server. Reopen the Overview in a moment to see the results.'
            : error?.response?.data?.detail || error?.message || 'Collection failed',
        ],
      });
    } finally {
      setCollecting(false);
    }
  };

  const handleStartCollection = async () => {
    setCollectResult(null);
    try {
      const targets: string[] = [];
      const meta = (currentCase as any)?.metadata || {};
      if (typeof meta.target === 'string' && meta.target.trim()) {
        targets.push(meta.target.trim());
      }
      if (Array.isArray(meta.targets)) targets.push(...meta.targets);
      const sources = buildCollectSources({
        platforms: (currentCase as any)?.platforms || meta.platforms || [],
        targets,
        keywords: (currentCase as any)?.keywords || meta.searchTerms || [],
        caseId,
      });
      if (sources.length === 0) {
        const needsTerms =
          ((currentCase as any)?.platforms || meta.platforms || []).length > 0 &&
          (((currentCase as any)?.keywords || []).length === 0);
        setCollectResult({
          status: 'NOTHING_TO_COLLECT',
          errors: needsTerms
            ? [
                'This case has no search terms, so a platform search would return nothing. Add terms below and try again.',
              ]
            : [
                'This case has no collectable source. Add a URL as the target, or pick X/Twitter with search terms, then try again.',
              ],
        });
        return;
      }
      await runCollectionNow(sources);
    } catch (error: any) {
      setCollectResult({
        status: 'ERROR',
        errors: [
          error?.code === 'ECONNABORTED'
            ? 'Still running on the server. Reopen the Overview in a moment to see the results.'
            : error?.response?.data?.detail || error?.message || 'Collection failed',
        ],
      });
    } finally {
      setCollecting(false);
    }
  };

  const handleGenerateSummary = async () => {
    setSummaryLoading(true);
    try {
      const res = await api.get(`/cases/${caseId}/analysis`);
      const d = res.data || {};
      const parts: string[] = [];
      if (d.assessment) parts.push(`Verdict: ${d.assessment} (${Math.round((d.confidence || 0) * 100)}% confidence).`);
      if (d.reasoning && d.reasoning.length) parts.push(d.reasoning.join(' '));
      if (d.limitations && d.limitations.length) parts.push(`Limits: ${d.limitations.join('; ')}`);
      setAiSummary(parts.join(' ') || 'Analysis available — open the Analysis tab for the full reasoning chain.');
    } catch (error) {
      console.error('Failed to generate summary:', error);
      setAiSummary('Could not load analysis yet. Run analysis from the Analysis tab first.');
    } finally {
      setSummaryLoading(false);
    }
  };

  useEffect(() => {
    fetchCaseData();
  }, [caseId]);

  /**
   * The new-case wizard hands its collection sources over via sessionStorage
   * rather than blocking the wizard for minutes. Pick them up and run here, where
   * the progress and result are already rendered.
   */
  useEffect(() => {
    if (!caseId) return;
    const key = `autocollect:${caseId}`;
    let sources: any[] | null = null;
    try {
      const raw = sessionStorage.getItem(key);
      if (raw) sources = JSON.parse(raw);
    } catch {
      sources = null;
    }
    if (sources && sources.length > 0) {
      const t = setTimeout(() => {
        // Consume the handoff only once the run is actually starting. In
        // StrictMode the effect runs, cleans up, then runs again; removing the
        // key during the first pass left the second pass with nothing to run
        // and the collection silently never happened.
        try {
          sessionStorage.removeItem(key);
        } catch {
          /* ignore */
        }
        runCollectionNow(sources);
      }, 400);
      return () => clearTimeout(t);
    }
  }, [caseId]);

  const fetchCaseData = async () => {
    setLoading(true);
    try {
      const [caseRes, accountsRes, postsRes, claimsRes, evidenceRes, graphRes, timelineRes] =
        await Promise.all([
          api.get(`/cases/${caseId}`),
          api.get(`/cases/${caseId}/accounts`),
          api.get(`/cases/${caseId}/posts`),
          api.get(`/cases/${caseId}/claims`),
          api.get(`/cases/${caseId}/evidence`),
          api.get(`/cases/${caseId}/graph`),
          api.get(`/cases/${caseId}/timeline`),
        ]);

      setCurrentCase(caseRes.data);
      setAccounts(accountsRes.data.data || []);
      setPosts(postsRes.data.data || []);
      setClaims(claimsRes.data.data || []);
      setEvidence(evidenceRes.data.data || []);
      setGraph(graphRes.data);
      setTimeline(timelineRes.data.data || []);
    } catch (error) {
      console.error('Failed to fetch case data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">{currentCase?.title || 'Case Overview'}</h1>
        <p className="text-gray-400 mt-1">
          {currentCase?.description || 'No description provided'}
        </p>
      </div>

      {(posts.length === 0 && evidence.length === 0) && (
        <div className="mb-6 bg-gray-900 border border-cyan-900/60 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Download className="w-4 h-4 text-cyan-400" />
            <h3 className="text-white font-medium">No sources collected yet</h3>
          </div>
          <p className="text-gray-400 text-sm mb-3">
            Creating a case only opens the investigation — it does not fetch anything. Run a
            collection to pull posts, evidence and claims for the platforms and search terms in
            this case. Authenticated runs open a browser window and can take a few minutes.
          </p>
          {!((currentCase as any)?.keywords || []).length && (
            <div className="mb-3">
              <label className="block text-sm font-medium text-white mb-1">
                Search terms
              </label>
              <p className="text-xs text-amber-400 mb-2">
                This case has no search terms, so a keyword search would come back empty.
                Add them to collect posts.
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={termInput}
                  onChange={(e) => setTermInput(e.target.value)}
                  placeholder="e.g. CJP protest, Jantar Mantar"
                  className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
                />
                <button
                  onClick={addSearchTerms}
                  disabled={!termInput.trim() || savingTerms}
                  className="px-3 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white text-sm whitespace-nowrap"
                >
                  {savingTerms ? 'Saving...' : 'Add'}
                </button>
              </div>
              {((currentCase as any)?.keywords || []).length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {((currentCase as any)?.keywords || []).map((k: string) => (
                    <span
                      key={k}
                      className="px-2 py-1 rounded bg-cyan-900/30 text-cyan-300 text-xs"
                    >
                      {k}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
          <button
            onClick={handleStartCollection}
            disabled={collecting}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg text-white font-medium flex items-center gap-2"
          >
            {collecting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Collecting...
              </>
            ) : (
              <>
                <Download className="w-4 h-4" /> Start collection
              </>
            )}
          </button>
          {collectResult && (
            <div
              className={`mt-3 rounded-lg border p-3 text-sm ${
                // A job can "succeed" while every source errored, so colour by
                // what was actually stored, not by the job status alone.
                collectResult.status === 'succeeded' && !collectResult.errors?.length
                  ? 'border-green-800 bg-green-900/20 text-green-300'
                  : collectResult.status === 'succeeded'
                  ? 'border-amber-800 bg-amber-900/20 text-amber-200'
                  : 'border-red-800 bg-red-900/20 text-red-200'
              }`}
            >
              <p className="font-medium">
                {collectResult.status === 'succeeded'
                  ? collectResult.errors?.length
                    ? `Collection finished but every source failed (${collectResult.errors.length} error${
                        collectResult.errors.length === 1 ? '' : 's'
                      })`
                    : collectResult.stored
                    ? `Collected ${collectResult.stored} new post${
                        collectResult.stored === 1 ? '' : 's'
                      }${collectResult.claims ? `, ${collectResult.claims} claims` : ''}`
                    : `Nothing new — all ${collectResult.received ?? 0} posts were already collected`
                  : collectResult.status === 'NOTHING_TO_COLLECT'
                  ? 'Nothing to collect'
                  : 'Collection did not complete'}
              </p>
              {(collectResult.errors || []).map((e, i) => (
                <p key={i} className="text-xs mt-1 break-words">{e}</p>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatsCard
          title="Evidence"
          value={evidence.length}
          icon={FileText}
          iconColor="text-green-400"
        />
        <StatsCard
          title="Accounts"
          value={accounts.length}
          icon={Users}
          iconColor="text-blue-400"
        />
        <StatsCard
          title="Claims"
          value={claims.length}
          icon={AlertTriangle}
          iconColor="text-amber-400"
        />
        <StatsCard
          title="Sources"
          value={posts.length}
          icon={Link2}
          iconColor="text-purple-400"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-white font-medium mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            Assessment
          </h3>
          {claims.length > 0 ? (
            <div className="space-y-3">
              {claims.slice(0, 3).map((claim) => (
                <div key={claim.id} className="bg-gray-800 rounded-lg p-3">
                  <p className="text-white text-sm mb-2">{claim.text}</p>
                  <div className="flex items-center gap-2">
                    <AssessmentBadge assessment={claim.status as any} size="sm" />
                    <span className="text-gray-400 text-xs">
                      Confidence: {(claim.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No claims analyzed yet</p>
          )}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-white font-medium mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-cyan-400" />
            Timeline Preview
          </h3>
          <TimelineView events={timeline.slice(0, 5)} compact />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-white font-medium mb-4">Graph Preview</h3>
          {graph ? (
            <div className="h-64">
              <GraphView data={graph} />
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500">
              No graph data available
            </div>
          )}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-white font-medium mb-4">AI Summary</h3>
          {aiSummary ? (
            <p className="text-gray-300 text-sm leading-relaxed">{aiSummary}</p>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-500 text-sm mb-3">Run analysis to generate AI summary</p>
              <button
                onClick={handleGenerateSummary}
                disabled={summaryLoading}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
              >
                {summaryLoading ? 'Generating...' : 'Generate Summary'}
              </button>
            </div>
          )}
        </div>
      </div>

      {evidence.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-white font-medium mb-4">Key Evidence</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {evidence.slice(0, 6).map((item) => (
              <div key={item.id} className="bg-gray-800 rounded-lg p-3 hover:bg-gray-750 transition-colors">
                <div className="flex items-start justify-between mb-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-blue-900/30 text-blue-400">
                    {item.type.toUpperCase()}
                  </span>
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-400 hover:text-white"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <p className="text-white text-sm font-medium mb-1">{item.title}</p>
                {item.description && (
                  <p className="text-gray-400 text-xs line-clamp-2">{item.description}</p>
                )}
                <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                  <Clock className="w-3 h-3" />
                  {formatDate(item.created_at)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
