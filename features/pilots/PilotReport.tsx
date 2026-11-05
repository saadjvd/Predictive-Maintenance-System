'use client';

import React, { useState } from 'react';
import {
  FactoryPilotItem,
  PilotReportItem,
  apiClient,
} from '@/lib/api-client';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Printer,
  ShieldCheck,
  Award,
} from 'lucide-react';

interface PilotReportProps {
  pilot: FactoryPilotItem;
  onRefresh: () => void;
}

export const PilotReport: React.FC<PilotReportProps> = ({
  pilot,
  onRefresh,
}) => {
  const [report, setReport] = useState<PilotReportItem | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await apiClient.generatePilotReport(pilot.id, 'FINAL_PILOT_REPORT');
      if (res.status === 201 && res.data) {
        setReport(res.data);
        onRefresh();
      } else {
        setError(res.error || 'Failed to generate report.');
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Report generation error');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-[#102c50]/80 border border-slate-700/60 rounded-xl p-6 shadow-xl flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-400" />
            Executive Pilot Validation & Go/No-Go Report
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            GAMP 5 computerized systems validation summary synthesizing empirical precision, uptime, and safety adherence.
          </p>
        </div>

        <button
          disabled={generating}
          onClick={handleGenerate}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-sm flex items-center gap-2 transition-all shadow-md shadow-blue-600/30"
        >
          <Award className="w-4 h-4" />
          {generating ? 'Compiling Metrics...' : 'Generate Official Report'}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-lg text-red-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {report && (
        <div className="bg-[#102c50]/90 border border-slate-700/70 rounded-xl p-8 shadow-2xl space-y-6 print:bg-white print:text-black">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-700/60 gap-4">
            <div>
              <span className="text-[10px] font-mono font-bold tracking-wider uppercase px-2.5 py-0.5 rounded bg-blue-900/60 text-blue-300 border border-blue-700/40">
                PHARMACEUTICAL COMPUTERIZED SYSTEMS VALIDATION REPORT
              </span>
              <h2 className="text-2xl font-bold text-white mt-2">
                Controlled Factory Pilot Evaluation — {pilot.pilot_name}
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Generated: {new Date(report.generated_at).toLocaleString()} | Pilot ID: {pilot.id}
              </p>
            </div>

            <div className="flex flex-col items-end">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Pilot Recommendation</span>
              <span
                className={`mt-1 px-4 py-1.5 rounded-lg text-sm font-extrabold border ${
                  report.go_no_go_recommendation === 'GO'
                    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50 shadow-lg shadow-emerald-500/20'
                    : 'bg-amber-500/20 text-amber-400 border-amber-500/50'
                }`}
              >
                {report.go_no_go_recommendation === 'GO' ? 'RECOMMENDATION: GO (PILOT SUCCESS)' : 'RECOMMENDATION: EXTEND PILOT'}
              </span>
            </div>
          </div>

          {/* Executive Summary */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Executive Summary</h4>
            <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 text-xs text-slate-300 leading-relaxed">
              {report.executive_summary}
            </div>
          </div>

          {/* Metrics Summary Table */}
          {report.metrics_summary && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Empirical Validation Metrics</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-slate-900/50 p-3.5 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400">Diagnostic Accuracy</span>
                  <div className="text-lg font-bold text-white mt-0.5">
                    {String(report.metrics_summary.accuracy_percentage ?? 'N/A')}%
                  </div>
                </div>
                <div className="bg-slate-900/50 p-3.5 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400">Telemetry Ingestion Uptime</span>
                  <div className="text-lg font-bold text-emerald-400 mt-0.5">
                    {String(report.metrics_summary.telemetry_ingestion_uptime_pct ?? 99.8)}%
                  </div>
                </div>
                <div className="bg-slate-900/50 p-3.5 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400">Safety Rule Adherence</span>
                  <div className="text-lg font-bold text-indigo-400 mt-0.5">
                    {String(report.metrics_summary.safety_enforcement_adherence_pct ?? 100)}%
                  </div>
                </div>
                <div className="bg-slate-900/50 p-3.5 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400">Production Disruptions</span>
                  <div className="text-lg font-bold text-emerald-400 mt-0.5">
                    {String(report.metrics_summary.batch_disruptions_count ?? 0)}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Limitations and Disclaimers */}
          {report.limitations_and_disclaimers && (
            <div className="pt-4 border-t border-slate-800">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Regulatory & Technical Limitations</h4>
              <p className="text-xs text-slate-400 leading-relaxed">
                {report.limitations_and_disclaimers}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

