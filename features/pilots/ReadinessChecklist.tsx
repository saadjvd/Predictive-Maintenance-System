'use client';

import React, { useState } from 'react';
import {
  FactoryPilotItem,
  PilotReadinessCheckItem,
  apiClient,
} from '@/lib/api-client';
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  FileCheck,
  Filter,
  Save,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';

interface ReadinessChecklistProps {
  pilot: FactoryPilotItem;
  onRefresh: () => void;
}

export const ReadinessChecklist: React.FC<ReadinessChecklistProps> = ({
  pilot,
  onRefresh,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [evidenceInputs, setEvidenceInputs] = useState<Record<string, string>>({});
  const [reviewResult, setReviewResult] = useState<Record<string, unknown> | null>(null);
  const [loadingReview, setLoadingReview] = useState(false);

  const checks = pilot.readiness_checks || [];
  const categories = ['ALL', 'REGISTRATION', 'CONNECTIVITY', 'DATA_QUALITY', 'BASELINES', 'SOP', 'SECURITY', 'QA'];

  const filteredChecks = selectedCategory === 'ALL'
    ? checks
    : checks.filter((c) => c.check_category === selectedCategory);

  const satisfiedCount = checks.filter((c) => c.status === 'SATISFIED' || c.status === 'WAIVED').length;
  const progressPct = checks.length > 0 ? Math.round((satisfiedCount / checks.length) * 100) : 0;

  const handleStatusChange = async (checkId: string, newStatus: string) => {
    setUpdatingId(checkId);
    try {
      const evidence = evidenceInputs[checkId];
      await apiClient.updateReadinessCheck(pilot.id, checkId, newStatus, evidence);
      onRefresh();
    } catch (e: unknown) {
      console.error('Failed to update readiness check:', e);
    } finally {
      setUpdatingId(null);
    }
  };

  const handlePerformReview = async () => {
    setLoadingReview(true);
    try {
      const res = await apiClient.performReadinessReview(pilot.id);
      if (res.status === 200) {
        setReviewResult(res.data || null);
        onRefresh();
      }
    } catch (e: unknown) {
      console.error('Failed to perform readiness review:', e);
    } finally {
      setLoadingReview(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'SATISFIED':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
      case 'IN_PROGRESS':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/40';
      case 'FAILED':
        return 'bg-red-500/20 text-red-400 border-red-500/40';
      case 'WAIVED':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
      default:
        return 'bg-slate-500/20 text-slate-400 border-slate-500/40';
    }
  };

  return (
    <div className="space-y-6">
      {/* Progress & Evaluation Header */}
      <div className="bg-[#102c50]/80 border border-slate-700/60 rounded-xl p-6 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-purple-400" />
              GAMP 5 Equipment & Site Readiness Checklist
            </h3>
            <p className="text-xs text-slate-400 mt-1 max-w-xl">
              17 mandatory engineering, industrial cybersecurity, and pharmaceutical computerized systems validation criteria.
            </p>
          </div>

          <button
            disabled={loadingReview}
            onClick={handlePerformReview}
            className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-medium text-sm flex items-center gap-2 transition-all shadow-md shadow-purple-600/30"
          >
            <RefreshCw className={`w-4 h-4 ${loadingReview ? 'animate-spin' : ''}`} />
            Evaluate Readiness
          </button>
        </div>

        {/* Progress Bar */}
        <div className="mt-5">
          <div className="flex items-center justify-between text-xs mb-1.5 font-medium">
            <span className="text-slate-300">Readiness Completion: {satisfiedCount} of {checks.length} criteria satisfied</span>
            <span className="text-purple-400 font-bold">{progressPct}%</span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
            <div
              className="bg-gradient-to-r from-purple-500 to-emerald-400 h-2.5 rounded-full transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {reviewResult && (
          <div className="mt-4 p-3 bg-purple-950/40 border border-purple-800/60 rounded-lg text-purple-200 text-xs flex items-center justify-between">
            <span>
              Status evaluated to: <strong>{String(reviewResult.status)}</strong> ({String(reviewResult.readiness_percentage)}% ready).
              {reviewResult.is_ready_for_approval ? ' Pilot is now READY for multi-department authorization.' : ' Additional criteria must be satisfied.'}
            </span>
          </div>
        )}
      </div>

      {/* Category Filter Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all shrink-0 ${
              selectedCategory === cat
                ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30'
                : 'bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Checklist Items Table */}
      <div className="bg-[#102c50]/60 border border-slate-700/60 rounded-xl overflow-hidden shadow-xl">
        <div className="divide-y divide-slate-800">
          {filteredChecks.map((check) => (
            <div key={check.id} className="p-4 hover:bg-slate-800/40 transition-colors">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                <div className="space-y-1 max-w-2xl">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      {check.check_category}
                    </span>
                    <h4 className="text-sm font-semibold text-white">{check.check_name}</h4>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">{check.description}</p>
                  {check.evidence_summary && (
                    <div className="mt-1 text-xs text-slate-300 bg-slate-900/60 p-2 rounded border border-slate-800">
                      <strong>Audit Evidence:</strong> {check.evidence_summary}
                    </div>
                  )}
                  {check.reviewer_name && (
                    <p className="text-[11px] text-slate-400">
                      Reviewed by {check.reviewer_name} on {check.reviewed_at ? new Date(check.reviewed_at).toLocaleDateString() : ''}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <select
                    disabled={updatingId === check.id}
                    value={check.status}
                    onChange={(e) => handleStatusChange(check.id, e.target.value)}
                    className={`text-xs font-semibold px-2.5 py-1 rounded-lg border bg-[#0d223d] transition-all cursor-pointer ${getStatusBadge(
                      check.status
                    )}`}
                  >
                    <option value="PENDING">PENDING</option>
                    <option value="IN_PROGRESS">IN_PROGRESS</option>
                    <option value="SATISFIED">SATISFIED</option>
                    <option value="WAIVED">WAIVED</option>
                    <option value="FAILED">FAILED</option>
                  </select>
                </div>
              </div>
            </div>
          ))}

          {filteredChecks.length === 0 && (
            <div className="p-8 text-center text-slate-500 text-sm">
              No checklist items found in this category.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

