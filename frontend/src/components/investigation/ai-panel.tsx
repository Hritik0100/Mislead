'use client';

import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Brain, Send, Loader2, User, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  type?: 'analysis' | 'question' | 'error';
}

interface AIPanelProps {
  caseId: string;
  analysisResult?: {
    assessment: string;
    confidence: number;
    reasoning: string[];
    limitations: string[];
    alternativeExplanations: string[];
  };
  onRunAnalysis?: () => void;
  onApprove?: () => void;
  onFinalize?: () => void;
  isAnalyzing?: boolean;
}

export function AIPanel({
  caseId,
  analysisResult,
  onRunAnalysis,
  onApprove,
  onFinalize,
  isAnalyzing = false,
}: AIPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    // Simulate AI response
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'I\'ll analyze your request and provide insights based on the available evidence.',
        timestamp: new Date(),
        type: 'analysis',
      };
      setMessages((prev) => [...prev, aiMessage]);
    }, 1000);
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 border border-gray-800 rounded-lg">
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-cyan-400" />
          <h3 className="text-white font-medium">AI Analysis</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onRunAnalysis}
            disabled={isAnalyzing}
            className={cn(
              'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
              isAnalyzing
                ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                : 'bg-cyan-600 hover:bg-cyan-500 text-white'
            )}
          >
            {isAnalyzing ? (
              <span className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Analyzing...
              </span>
            ) : (
              'Run Analysis'
            )}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {analysisResult && (
          <div className="space-y-4 mb-6">
            <div className="bg-gray-800 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-400 mb-2">Assessment</h4>
              <div className="flex items-center gap-3">
                <span className="text-xl font-bold text-white">{analysisResult.assessment}</span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full',
                        analysisResult.confidence >= 0.8
                          ? 'bg-green-500'
                          : analysisResult.confidence >= 0.6
                          ? 'bg-amber-500'
                          : 'bg-red-500'
                      )}
                      style={{ width: `${analysisResult.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-mono text-gray-400">
                    {(analysisResult.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-gray-800 rounded-lg p-4">
              <h4 className="text-sm font-medium text-gray-400 mb-2">Reasoning Chain</h4>
              <ol className="space-y-2">
                {analysisResult.reasoning.map((step, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-gray-700 flex items-center justify-center text-xs text-gray-400">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>

            {analysisResult.limitations.length > 0 && (
              <div className="bg-amber-900/20 border border-amber-800 rounded-lg p-4">
                <h4 className="text-sm font-medium text-amber-400 mb-2 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  Limitations
                </h4>
                <ul className="space-y-1">
                  {analysisResult.limitations.map((limitation, i) => (
                    <li key={i} className="text-sm text-amber-200/80">
                      • {limitation}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {analysisResult.alternativeExplanations.length > 0 && (
              <div className="bg-gray-800 rounded-lg p-4">
                <h4 className="text-sm font-medium text-gray-400 mb-2">Alternative Explanations</h4>
                <ul className="space-y-1">
                  {analysisResult.alternativeExplanations.map((alt, i) => (
                    <li key={i} className="text-sm text-gray-300">
                      • {alt}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex items-center gap-2">
              <button
                onClick={onApprove}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-green-600 hover:bg-green-500 text-white transition-colors"
              >
                <CheckCircle className="w-4 h-4" />
                Approve
              </button>
              <button
                onClick={onFinalize}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-purple-600 hover:bg-purple-500 text-white transition-colors"
              >
                <XCircle className="w-4 h-4" />
                Finalize
              </button>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              'flex gap-3',
              message.role === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            {message.role === 'assistant' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-cyan-900/30 flex items-center justify-center">
                <Brain className="w-4 h-4 text-cyan-400" />
              </div>
            )}
            <div
              className={cn(
                'max-w-[80%] rounded-lg px-4 py-2',
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-300'
              )}
            >
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              <p className="text-xs opacity-50 mt-1">
                {message.timestamp.toLocaleTimeString()}
              </p>
            </div>
            {message.role === 'user' && (
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-900/30 flex items-center justify-center">
                <User className="w-4 h-4 text-blue-400" />
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-gray-800">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask about the analysis..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            className="p-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg transition-colors"
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </div>
      </div>
    </div>
  );
}
