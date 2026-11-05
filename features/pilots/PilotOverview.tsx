'use client';

import React, { useState } from 'react';
import {
  FactoryPilotItem,
  PilotMetricsItem,
  apiClient,
} from '@/lib/api-client';
import {
  Play,
  Pause,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  FileText,
  Activity,
  Layers,
  Clock,
  UserCheck,
} from 'lucide-react';

interface PilotOverviewProps {
  pilot: FactoryPilotItem;
  metrics: PilotMetricsItem | null;
  onRefresh: () => void;
  onSelectTab: (tab: string) => void;
}

export const PilotOverview: React.FC<PilotOverviewProps> = ({
  pilot,
  metrics,
  onRefresh,
  onSelectTab,
}) => {
  const [loading, setLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const handleActivate = async () => {
    setLoading(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const res = await apiClient.activatePilot(pilot.id);
      if (res.status === 200) {
        setActionSuccess('Pilot activated in strict read-only SHADOW MODE.');
        onRefresh();
      } else {
        setActionError(res.error || 'Failed to activate pilot.');
      }
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Activation error');
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async () => {
    setLoading(true);
    try {
      await apiClient.pausePilot(pilot.id);
      onRefresh();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Pause error');
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = async () => {
    setLoading(true);
    try {
      await apiClient.completePilot(pilot.id);
      onRefresh();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Completion error');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'APPROVED':
      case 'READY':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'AWAITING_APPROVAL':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      case 'READINESS_REVIEW':
        return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      case 'PAUSED':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'COMPLETED':
        return 'bg-teal-500/20 text-teal-400 border-teal-500/30';
      default:
        return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  return (
    <div className="space-y-6">
      {/* Pilot Header Card */}
      <div className="bg-[#102c50]/80 border border-slate-700/60 rounded-xl p-6 shadow-xl backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold text-white tracking-tight">{pilot.pilot_name}</h2>
              <span className={`px-3 py-0.5 rounded-full text-xs font-semibold border ${getStatusBadge(pilot.status)}`}>
                {pilot.status}
              </span>
              <span className="px-2.5 py-0.5 rounded-md text-xs font-mono font-bold bg-blue-900/60 text-blue-300 border border-blue-700/40">
                MODE: {pilot.monitoring_mode}
              </span>
            </div>
            <p className="text-slate-400 text-sm mt-1 max-w-2xl">
              {pilot.description || 'Controlled shadow-mode pharmaceutical factory pilot.'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {pilot.status === 'DRAFT' || pilot.status === 'READINESS_REVIEW' ? (
              <button
                onClick={() => onSelectTab('readiness')}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm flex items-center gap-2 transition-all shadow-md shadow-blue-600/30"
              >
                <CheckCircle2 className="w-4 h-4" />
                Readiness Review
              </button>
            ) : null}

            {pilot.status === 'APPROVED' || pilot.status === 'READY' ? (
              <button
                disabled={loading}
                onClick={handleActivate}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm flex items-center gap-2 transition-all shadow-md shadow-emerald-600/30"
              >
                <Play className="w-4 h-4" />
                Activate Pilot (Shadow)
              </button>
            ) : null}

            {pilot.status === 'ACTIVE' ? (
              <>
                <button
                  disabled={loading}
                  onClick={handlePause}
                  className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium text-sm flex items-center gap-2 transition-all"
                >
                  <Pause className="w-4 h-4" />
                  Pause
                </button>
                <button
                  disabled={loading}
                  onClick={handleComplete}
                  className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-medium text-sm flex items-center gap-2 transition-all"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Complete
                </button>
              </>
            ) : null}

            <button
              onClick={() => onSelectTab('reports')}
              className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-sm flex items-center gap-1.5 transition-all"
            >
              <FileText className="w-4 h-4" />
              Report
            </button>
          </div>
        </div>

        {actionError && (
          <div className="mt-4 p-3 bg-red-950/40 border border-red-800/60 rounded-lg flex items-center gap-2 text-red-300 text-xs">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {actionSuccess && (
          <div className="mt-4 p-3 bg-emerald-950/40 border border-emerald-800/60 rounded-lg flex items-center gap-2 text-emerald-300 text-xs">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{actionSuccess}</span>
          </div>
        )}
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#102c50]/60 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Enrolled Machines</span>
            <Layers className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {pilot.equipment?.length || 0}
          </div>
          <p className="text-xs text-slate-400 mt-1">Operating in strict shadow mode</p>
        </div>

        <div className="bg-[#102c50]/60 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Diagnostic Accuracy</span>
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {metrics?.accuracy_percentage != null ? `${metrics.accuracy_percentage}%` : 'N/A'}
          </div>
          <p className="text-xs text-slate-400 mt-1">Verified by site reliability engineers</p>
        </div>

        <div className="bg-[#102c50]/60 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Safety Adherence</span>
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {metrics?.safety_enforcement_adherence_pct != null ? `${metrics.safety_enforcement_adherence_pct}%` : '100%'}
          </div>
          <p className="text-xs text-slate-400 mt-1">Mandatory OSHA LOTO & PPE</p>
        </div>

        <div className="bg-[#102c50]/60 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
            <span>Feedback Reviews</span>
            <UserCheck className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">
            {metrics?.total_feedback_submissions || 0}
          </div>
          <p className="text-xs text-slate-400 mt-1">Audit log records submitted</p>
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div
          onClick={() => onSelectTab('equipment')}
          className="bg-[#102c50]/40 border border-slate-700/50 hover:border-blue-500/50 rounded-xl p-5 cursor-pointer transition-all hover:bg-[#102c50]/70 group"
        >
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-white group-hover:text-blue-400 transition-colors">Equipment Selection</h3>
            <Layers className="w-5 h-5 text-slate-400 group-hover:text-blue-400" />
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Configure candidate packaging, solid oral dose, or sterile fill machinery for shadow telemetry.
          </p>
        </div>

        <div
          onClick={() => onSelectTab('readiness')}
          className="bg-[#102c50]/40 border border-slate-700/50 hover:border-purple-500/50 rounded-xl p-5 cursor-pointer transition-all hover:bg-[#102c50]/70 group"
        >
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-white group-hover:text-purple-400 transition-colors">Readiness Checklist</h3>
            <CheckCircle2 className="w-5 h-5 text-slate-400 group-hover:text-purple-400" />
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Review 17 GAMP 5 technical criteria across registration, OPC UA connectivity, data quality, and security.
          </p>
        </div>

        <div
          onClick={() => onSelectTab('feedback')}
          className="bg-[#102c50]/40 border border-slate-700/50 hover:border-emerald-500/50 rounded-xl p-5 cursor-pointer transition-all hover:bg-[#102c50]/70 group"
        >
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-white group-hover:text-emerald-400 transition-colors">Engineer Feedback</h3>
            <UserCheck className="w-5 h-5 text-slate-400 group-hover:text-emerald-400" />
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Review AI diagnostic sessions, inspect physical findings, confirm root causes, and submit ground truth labels.
          </p>
        </div>
      </div>
    </div>
  );
};

