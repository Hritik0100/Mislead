'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  FileBarChart,
  Download,
  Printer,
  Copy,
  Check,
  Loader2,
} from 'lucide-react';
import { useCaseStore } from '@/lib/store';
import { ReportPreview } from '@/components/investigation/report-preview';
import api from '@/lib/api';

interface ReportSection {
  id: string;
  title: string;
  included: boolean;
}

const defaultSections: ReportSection[] = [
  { id: 'executive-summary', title: 'Executive Summary', included: true },
  { id: 'objective', title: 'Objective', included: true },
  { id: 'target', title: 'Target', included: true },
  { id: 'methodology', title: 'Methodology', included: true },
  { id: 'sources', title: 'Sources', included: true },
  { id: 'account-findings', title: 'Account Findings', included: true },
  { id: 'claim-analysis', title: 'Claim Analysis', included: true },
  { id: 'earliest-source', title: 'Earliest Source', included: true },
  { id: 'propagation', title: 'Propagation', included: true },
  { id: 'coordination', title: 'Coordination', included: true },
  { id: 'media', title: 'Media', included: true },
  { id: 'evidence', title: 'Evidence', included: true },
  { id: 'assessment', title: 'Assessment', included: true },
  { id: 'confidence', title: 'Confidence', included: true },
  { id: 'limitations', title: 'Limitations', included: true },
  { id: 'notes', title: 'Analyst Notes', included: true },
  { id: 'appendix', title: 'Appendix', included: false },
];

export default function CaseReportPage() {
  const params = useParams();
  const caseId = params.id as string;
  const { currentCase, setCurrentCase } = useCaseStore();
  const [sections, setSections] = useState<ReportSection[]>(defaultSections);
  const [reportContent, setReportContent] = useState<string>('');
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);

  useEffect(() => {
    fetchCase();
  }, [caseId]);

  const fetchCase = async () => {
    try {
      const response = await api.get(`/cases/${caseId}`);
      setCurrentCase(response.data);
    } catch (error) {
      console.error('Failed to fetch case:', error);
    }
  };

  const toggleSection = (sectionId: string) => {
    setSections((prev) =>
      prev.map((s) => (s.id === sectionId ? { ...s, included: !s.included } : s))
    );
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const response = await api.post(`/cases/${caseId}/report/generate`, {
        sections: sections.filter((s) => s.included).map((s) => s.id),
      });
      setReportContent(response.data.content);
      setGenerated(true);
    } catch (error) {
      console.error('Failed to generate report:', error);
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = async (format: 'pdf' | 'json' | 'csv') => {
    try {
      const response = await api.get(`/cases/${caseId}/report/export`, {
        params: { format },
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `report.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Failed to export report:', error);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(reportContent);
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Report</h1>
          <p className="text-gray-400 mt-1">Generate investigation report</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
        >
          {generating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <FileBarChart className="w-4 h-4" />
              Generate Report
            </>
          )}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-white font-medium mb-4">Report Sections</h3>
            <div className="space-y-2">
              {sections.map((section) => (
                <button
                  key={section.id}
                  onClick={() => toggleSection(section.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                    section.included
                      ? 'bg-gray-800 text-white'
                      : 'bg-gray-900 text-gray-500 hover:bg-gray-800/50'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded border-2 flex items-center justify-center ${
                      section.included
                        ? 'bg-cyan-600 border-cyan-600'
                        : 'border-gray-600'
                    }`}
                  >
                    {section.included && <Check className="w-3 h-3 text-white" />}
                  </div>
                  {section.title}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          <ReportPreview
            title={currentCase?.title || 'Investigation Report'}
            sections={sections}
            content={reportContent}
            onExport={handleExport}
            onPrint={handlePrint}
            onCopy={handleCopy}
          />
        </div>
      </div>
    </div>
  );
}
