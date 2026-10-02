'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Target,
  FileText,
  Globe,
  Calendar,
  Loader2,
} from 'lucide-react';
import { useCaseStore } from '@/lib/store';
import api from '@/lib/api';
import { buildCollectSources } from '@/lib/collect';
import toast from 'react-hot-toast';

interface CaseFormData {
  title: string;
  description: string;
  target: string;
  targetType: string;
  /** Real search terms. Distinct from `objectives`, which are workflow steps. */
  searchTerms: string;
  objectives: string[];
  platforms: string[];
  dateRange: {
    start: string;
    end: string;
  };
}

const steps = [
  { id: 1, title: 'Basic Info', icon: FileText },
  { id: 2, title: 'Target', icon: Target },
  { id: 3, title: 'Objectives', icon: Check },
  { id: 4, title: 'Platforms', icon: Globe },
  { id: 5, title: 'Date Range', icon: Calendar },
  { id: 6, title: 'Review', icon: Check },
];

const objectives = [
  { id: 'identify-source', label: 'Identify source' },
  { id: 'find-earliest-source', label: 'Find earliest source' },
  { id: 'verify-claim', label: 'Verify claim' },
  { id: 'trace-propagation', label: 'Trace propagation' },
  { id: 'analyze-relationships', label: 'Analyze relationships' },
  { id: 'detect-coordination', label: 'Detect coordination' },
  { id: 'analyze-media', label: 'Analyze media' },
  { id: 'generate-report', label: 'Generate report' },
];

const platforms = [
  { id: 'twitter', label: 'X/Twitter', color: '#1DA1F2' },
  { id: 'youtube', label: 'YouTube', color: '#FF0000' },
  { id: 'telegram', label: 'Telegram', color: '#0088cc' },
  { id: 'matrix', label: 'Matrix', color: '#0DBD8B' },
  { id: 'web', label: 'Web', color: '#6366f1' },
];

const targetTypes = [
  { id: 'url', label: 'URL', placeholder: 'https://example.com/post/123' },
  { id: 'username', label: 'Username', placeholder: '@username' },
  { id: 'domain', label: 'Domain', placeholder: 'example.com' },
  { id: 'ip', label: 'IP Address', placeholder: '192.168.1.1' },
  { id: 'email', label: 'Email', placeholder: 'user@example.com' },
  { id: 'claim', label: 'Claim', placeholder: 'Enter the claim text' },
  { id: 'keyword', label: 'Keyword', placeholder: 'Enter keyword' },
  { id: 'hashtag', label: 'Hashtag', placeholder: '#hashtag' },
  { id: 'image', label: 'Image URL', placeholder: 'https://example.com/image.jpg' },
];

export default function NewCasePage() {
  const router = useRouter();
  const { addCase } = useCaseStore();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<CaseFormData>({
    title: '',
    description: '',
    target: '',
    targetType: 'url',
    searchTerms: '',
    objectives: [],
    platforms: [],
    dateRange: {
      start: '',
      end: '',
    },
  });

  const updateFormData = (updates: Partial<CaseFormData>) => {
    setFormData((prev) => ({ ...prev, ...updates }));
  };

  const toggleObjective = (objectiveId: string) => {
    setFormData((prev) => ({
      ...prev,
      objectives: prev.objectives.includes(objectiveId)
        ? prev.objectives.filter((id) => id !== objectiveId)
        : [...prev.objectives, objectiveId],
    }));
  };

  const togglePlatform = (platformId: string) => {
    setFormData((prev) => ({
      ...prev,
      platforms: prev.platforms.includes(platformId)
        ? prev.platforms.filter((id) => id !== platformId)
        : [...prev.platforms, platformId],
    }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const searchTerms = formData.searchTerms
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);
      const response = await api.post('/cases', {
        title: formData.title,
        description: formData.description,
        // Real search terms only. Objectives are workflow steps and are sent
        // separately; merging them here made every platform query useless.
        keywords: searchTerms,
        metadata: {
          target: formData.target,
          targetType: formData.targetType,
          objectives: formData.objectives,
          platforms: formData.platforms,
          searchTerms,
          dateRange: formData.dateRange,
        },
      });
      addCase(response.data);
      const newId = response.data.id;
      toast.success('Case created successfully');

      // Creating a case only creates the container. Kick off collection so the
      // analyst lands on real data instead of an empty case.
      const sources = buildCollectSources({
        platforms: formData.platforms,
        targets: [formData.target].filter(Boolean),
        keywords: searchTerms,
        caseId: newId,
      });
      if (sources.length > 0) {
        // Hand the work to the Overview page instead of awaiting it here: an
        // authenticated run can take minutes, and blocking the wizard that long
        // looks like a freeze. The Overview shows its own progress + result.
        try {
          sessionStorage.setItem(`autocollect:${newId}`, JSON.stringify(sources));
        } catch {
          /* private mode: Overview will just not auto-start */
        }
        toast('Case created — starting collection');
      } else if (formData.platforms.length > 0 && searchTerms.length === 0) {
        toast.error('No search terms given — add some to collect posts from those platforms');
      }
      router.push(`/cases/${newId}/overview`);
    } catch (error: any) {
      // A generic "failed" hid the real cause here (the case was created but the
      // follow-up blew up), so surface it.
      console.error('Case creation failed:', error);
      toast.error(
        `Failed to create case: ${error?.response?.data?.detail || error?.message || 'unknown error'}`
      );
    } finally {
      setLoading(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1:
        return formData.title.trim().length > 0;
      case 2:
        return formData.target.trim().length > 0;
      case 3:
        return formData.objectives.length > 0;
      case 4:
        return formData.platforms.length > 0;
      case 5:
        return true;
      case 6:
        return true;
      default:
        return false;
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-3xl mx-auto">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-gray-400 hover:text-white mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>

        <h1 className="text-2xl font-bold text-white mb-6">Create New Case</h1>

        <div className="flex items-center justify-between mb-8">
          {steps.map((s, i) => (
            <div key={s.id} className="flex items-center">
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-full border-2 transition-colors ${
                  step === s.id
                    ? 'bg-cyan-600 border-cyan-600 text-white'
                    : step > s.id
                    ? 'bg-green-600 border-green-600 text-white'
                    : 'bg-gray-800 border-gray-700 text-gray-400'
                }`}
              >
                {step > s.id ? <Check className="w-5 h-5" /> : <s.icon className="w-5 h-5" />}
              </div>
              {i < steps.length - 1 && (
                <div
                  className={`w-12 h-0.5 mx-2 ${
                    step > s.id ? 'bg-green-600' : 'bg-gray-700'
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          {step === 1 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white mb-4">Basic Information</h2>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Title *</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => updateFormData({ title: e.target.value })}
                  placeholder="Enter case title"
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => updateFormData({ description: e.target.value })}
                  placeholder="Describe the investigation objectives"
                  rows={4}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 resize-none"
                />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white mb-4">Target Input</h2>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Target Type</label>
                <select
                  value={formData.targetType}
                  onChange={(e) => updateFormData({ targetType: e.target.value })}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                >
                  {targetTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Target *</label>
                <input
                  type="text"
                  value={formData.target}
                  onChange={(e) => updateFormData({ target: e.target.value })}
                  placeholder={targetTypes.find((t) => t.id === formData.targetType)?.placeholder}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white mb-4">Investigation Objectives</h2>
              <p className="text-gray-400 text-sm mb-4">Select what you want to achieve with this investigation</p>
              <div className="grid grid-cols-2 gap-3">
                {objectives.map((objective) => (
                  <button
                    key={objective.id}
                    onClick={() => toggleObjective(objective.id)}
                    className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                      formData.objectives.includes(objective.id)
                        ? 'bg-cyan-900/30 border-cyan-600 text-white'
                        : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-600'
                    }`}
                  >
                    <div
                      className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                        formData.objectives.includes(objective.id)
                          ? 'bg-cyan-600 border-cyan-600'
                          : 'border-gray-600'
                      }`}
                    >
                      {formData.objectives.includes(objective.id) && (
                        <Check className="w-3 h-3 text-white" />
                      )}
                    </div>
                    {objective.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white mb-4">Platform Selection</h2>
              <p className="text-gray-400 text-sm mb-4">Select platforms to monitor</p>

              <div className="bg-gray-800 rounded-lg p-4">
                <label className="block text-sm font-medium text-white mb-1">
                  Search terms
                </label>
                <p className="text-xs text-gray-400 mb-2">
                  These words are what gets typed into each platform&rsquo;s search box.
                  Without them a keyword search collects nothing, so add the names,
                  phrases or handles you actually want to look for.
                </p>
                <input
                  type="text"
                  value={formData.searchTerms}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, searchTerms: e.target.value }))
                  }
                  placeholder="e.g. CJP protest, Jantar Mantar, Gyanesh Kumar"
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
                />
                <div className="flex items-center justify-between mt-2">
                  <p className="text-xs text-gray-500">
                    Separate terms with commas. Not the same as objectives below-left:
                    objectives are workflow steps, these are what we search for.
                  </p>
                  {formData.searchTerms.trim() ? (
                    <span className="text-xs text-cyan-400 whitespace-nowrap ml-3">
                      {formData.searchTerms
                        .split(',')
                        .map((t) => t.trim())
                        .filter(Boolean).length}{' '}
                      term(s)
                    </span>
                  ) : null}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {platforms.map((platform) => (
                  <button
                    key={platform.id}
                    onClick={() => togglePlatform(platform.id)}
                    className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                      formData.platforms.includes(platform.id)
                        ? 'bg-cyan-900/30 border-cyan-600 text-white'
                        : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-600'
                    }`}
                  >
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: platform.color }}
                    />
                    <div
                      className={`w-5 h-5 rounded border-2 flex items-center justify-center ${
                        formData.platforms.includes(platform.id)
                          ? 'bg-cyan-600 border-cyan-600'
                          : 'border-gray-600'
                      }`}
                    >
                      {formData.platforms.includes(platform.id) && (
                        <Check className="w-3 h-3 text-white" />
                      )}
                    </div>
                    {platform.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white mb-4">Date Range</h2>
              <p className="text-gray-400 text-sm mb-4">Optional: Set a date range for data collection</p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Start Date</label>
                  <input
                    type="date"
                    value={formData.dateRange.start}
                    onChange={(e) =>
                      updateFormData({
                        dateRange: { ...formData.dateRange, start: e.target.value },
                      })
                    }
                    className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">End Date</label>
                  <input
                    type="date"
                    value={formData.dateRange.end}
                    onChange={(e) =>
                      updateFormData({
                        dateRange: { ...formData.dateRange, end: e.target.value },
                      })
                    }
                    className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
            </div>
          )}

          {step === 6 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white mb-4">Review & Start</h2>
              <div className="space-y-3">
                <div className="bg-gray-800 rounded-lg p-3">
                  <span className="text-gray-400 text-sm">Title:</span>
                  <p className="text-white">{formData.title}</p>
                </div>
                {formData.description && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <span className="text-gray-400 text-sm">Description:</span>
                    <p className="text-white">{formData.description}</p>
                  </div>
                )}
                <div className="bg-gray-800 rounded-lg p-3">
                  <span className="text-gray-400 text-sm">Target:</span>
                  <p className="text-white">
                    {formData.target} ({formData.targetType})
                  </p>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <span className="text-gray-400 text-sm">Search terms:</span>
                  {formData.searchTerms.trim() ? (
                    <div className="flex flex-wrap gap-2 mt-1">
                      {formData.searchTerms
                        .split(',')
                        .map((t) => t.trim())
                        .filter(Boolean)
                        .map((t) => (
                          <span
                            key={t}
                            className="px-2 py-1 rounded bg-cyan-900/30 text-cyan-300 text-xs"
                          >
                            {t}
                          </span>
                        ))}
                    </div>
                  ) : (
                    <p className="text-amber-400 text-sm mt-1">
                      None set — platform keyword searches will return nothing. You can add
                      them later from the Overview page.
                    </p>
                  )}
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <span className="text-gray-400 text-sm">Objectives:</span>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {formData.objectives.map((obj) => (
                      <span key={obj} className="px-2 py-1 bg-gray-700 rounded text-sm text-white">
                        {objectives.find((o) => o.id === obj)?.label}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="bg-gray-800 rounded-lg p-3">
                  <span className="text-gray-400 text-sm">Platforms:</span>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {formData.platforms.map((plat) => (
                      <span key={plat} className="px-2 py-1 bg-gray-700 rounded text-sm text-white">
                        {platforms.find((p) => p.id === plat)?.label}
                      </span>
                    ))}
                  </div>
                </div>
                {formData.dateRange.start && (
                  <div className="bg-gray-800 rounded-lg p-3">
                    <span className="text-gray-400 text-sm">Date Range:</span>
                    <p className="text-white">
                      {formData.dateRange.start} to {formData.dateRange.end || 'Present'}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between mt-6">
          <button
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 1}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Previous
          </button>

          {step < 6 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={!canProceed()}
              className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              Next
              <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={loading || !canProceed()}
              className="flex items-center gap-2 px-6 py-2 bg-green-600 hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  Start Investigation
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
