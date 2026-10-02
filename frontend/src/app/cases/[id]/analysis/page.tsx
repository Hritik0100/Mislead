'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  BarChart3,
  Play,
  Loader2,
  CheckCircle,
  AlertTriangle,
  MessageSquare,
  Save,
} from 'lucide-react';
import { useInvestigationStore } from '@/lib/store';
import { AIPanel } from '@/components/investigation/ai-panel';
import api from '@/lib/api';

export default function CaseAnalysisPage() {
  const params = useParams();
  const caseId = params.id as string;
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [analystNotes, setAnalystNotes] = useState('');

  useEffect(() => {
    fetchAnalysis();
  }, [caseId]);

  const fetchAnalysis = async () => {
    try {
      const response = await api.get(`/cases/${caseId}/analysis`);
      if (response.data) {
        setAnalysisResult(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch analysis:', error);
    }
  };

  const handleRunAnalysis = async () => {
    setIsAnalyzing(true);
    try {
      const response = await api.post(`/cases/${caseId}/analysis/run`);
      setAnalysisResult(response.data);
    } catch (error) {
      console.error('Failed to run analysis:', error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleApprove = async () => {
    try {
      await api.post(`/cases/${caseId}/analysis/approve`);
      // Show success toast
    } catch (error) {
      console.error('Failed to approve analysis:', error);
    }
  };

  const handleFinalize = async () => {
    try {
      await api.post(`/cases/${caseId}/analysis/finalize`);
      // Show success toast
    } catch (error) {
      console.error('Failed to finalize analysis:', error);
    }
  };

  const handleSaveNotes = async () => {
    try {
      await api.put(`/cases/${caseId}/analysis/notes`, { notes: analystNotes });
      // Show success toast
    } catch (error) {
      console.error('Failed to save notes:', error);
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Analysis</h1>
          <p className="text-gray-400 mt-1">Automated intelligence analysis</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          {isAnalyzing ? (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-8">
              <div className="text-center">
                <Loader2 className="w-16 h-16 text-cyan-400 animate-spin mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-white mb-2">Analyzing...</h3>
                <p className="text-gray-400">This may take a few minutes</p>
                <div className="mt-6 space-y-3">
                  <div className="flex items-center gap-3 text-sm">
                    <CheckCircle className="w-4 h-4 text-green-400" />
                    <span className="text-gray-300">Collecting evidence</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
                    <span className="text-gray-300">Analyzing relationships</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm opacity-50">
                    <div className="w-4 h-4 rounded-full border-2 border-gray-600" />
                    <span className="text-gray-500">Generating assessment</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <AIPanel
              caseId={caseId}
              analysisResult={analysisResult}
              onRunAnalysis={handleRunAnalysis}
              onApprove={handleApprove}
              onFinalize={handleFinalize}
              isAnalyzing={isAnalyzing}
            />
          )}
        </div>

        <div className="lg:col-span-1 space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-white font-medium mb-4">Analyst Notes</h3>
            <textarea
              value={analystNotes}
              onChange={(e) => setAnalystNotes(e.target.value)}
              placeholder="Add your notes and observations..."
              rows={6}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 resize-none text-sm"
            />
            <button
              onClick={handleSaveNotes}
              className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors"
            >
              <Save className="w-4 h-4" />
              Save Notes
            </button>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-white font-medium mb-4">Evidence References</h3>
            <div className="space-y-2">
              {['E001', 'E002', 'E003', 'E004', 'E005'].map((ref) => (
                <div
                  key={ref}
                  className="flex items-center gap-2 px-3 py-2 bg-gray-800 rounded-lg cursor-pointer hover:bg-gray-750 transition-colors"
                >
                  <span className="text-cyan-400 font-mono text-sm">{ref}</span>
                  <span className="text-gray-400 text-sm truncate">Evidence item {ref}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-white font-medium mb-4">Quick Actions</h3>
            <div className="space-y-2">
              <button className="w-full flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors">
                <Play className="w-4 h-4" />
                Re-run Analysis
              </button>
              <button className="w-full flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors">
                <BarChart3 className="w-4 h-4" />
                Export Results
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
