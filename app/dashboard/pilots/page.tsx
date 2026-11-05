'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  FactoryPilotItem,
  PilotMetricsItem,
  SiteDetails,
  apiClient,
} from '@/lib/api-client';
import { PilotOverview } from '@/features/pilots/PilotOverview';
import { EquipmentSelection } from '@/features/pilots/EquipmentSelection';
import { ReadinessChecklist } from '@/features/pilots/ReadinessChecklist';
import { PilotMonitoring } from '@/features/pilots/PilotMonitoring';
import { FeedbackForm } from '@/features/pilots/FeedbackForm';
import { PilotReport } from '@/features/pilots/PilotReport';
import { PilotSetup } from '@/features/pilots/PilotSetup';
import {
  Compass,
  Plus,
  RefreshCw,
  Layers,
  ShieldCheck,
  Activity,
  UserCheck,
  FileText,
  AlertCircle,
} from 'lucide-react';

export default function PilotsDashboardPage() {
  const [pilots, setPilots] = useState<FactoryPilotItem[]>([]);
  const [selectedPilotId, setSelectedPilotId] = useState<string | null>(null);
  const [activePilot, setActivePilot] = useState<FactoryPilotItem | null>(null);
  const [metrics, setMetrics] = useState<PilotMetricsItem | null>(null);
  const [sites, setSites] = useState<SiteDetails[]>([]);

  const [activeTab, setActiveTab] = useState<string>('overview');
  const [loading, setLoading] = useState(true);
  const [showSetup, setShowSetup] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPilots = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.listPilots();
      if (res.status === 200 && res.data) {
        const list = Array.isArray(res.data) ? res.data : [];
        setPilots(list);
        if (list.length > 0 && !selectedPilotId) {
          setSelectedPilotId(list[0].id);
        }
      }

      // Fetch sites for setup modal
      const siteRes = await apiClient.getSites();
      if (siteRes.status === 200 && siteRes.data) {
        setSites(Array.isArray(siteRes.data) ? siteRes.data : []);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load pilots');
    } finally {
      setLoading(false);
    }
  }, [selectedPilotId]);

  useEffect(() => {
    fetchPilots();
  }, [fetchPilots]);

  const fetchPilotDetails = useCallback(async (id: string) => {
    try {
      const res = await apiClient.getPilot(id);
      if (res.status === 200 && res.data) {
        setActivePilot(res.data);
      }
      const mRes = await apiClient.getPilotMetrics(id);
      if (mRes.status === 200 && mRes.data) {
        setMetrics(mRes.data);
      }
    } catch (e: unknown) {
      console.error('Error fetching pilot details:', e);
    }
  }, []);

  useEffect(() => {
    if (selectedPilotId) {
      fetchPilotDetails(selectedPilotId);
    }
  }, [selectedPilotId, fetchPilotDetails]);

  const handleSetupSuccess = (newPilotId: string) => {
    setShowSetup(false);
    setSelectedPilotId(newPilotId);
    fetchPilots();
  };

  const tabs = [
    { id: 'overview', label: 'Pilot Overview', icon: Compass },
    { id: 'equipment', label: 'Equipment Selection', icon: Layers },
    { id: 'readiness', label: 'Readiness Checklist', icon: ShieldCheck },
    { id: 'monitoring', label: 'Shadow Monitoring', icon: Activity },
    { id: 'feedback', label: 'Engineer Feedback', icon: UserCheck },
    { id: 'reports', label: 'Pilot Reports', icon: FileText },
  ];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white tracking-tight">Controlled Factory Pilots</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
              PHASE 9
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            GAMP 5 controlled shadow-mode pilot management, multi-sign-off authorization, and engineer feedback loops.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {pilots.length > 0 && (
            <select
              value={selectedPilotId || ''}
              onChange={(e) => setSelectedPilotId(e.target.value)}
              className="bg-[#102c50] border border-slate-700 rounded-lg px-3 py-2 text-xs font-semibold text-white focus:outline-none focus:border-blue-500"
            >
              {pilots.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.pilot_name} ({p.status})
                </option>
              ))}
            </select>
          )}

          <button
            onClick={() => setShowSetup(true)}
            className="px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs flex items-center gap-1.5 transition-all shadow-md shadow-blue-600/30"
          >
            <Plus className="w-4 h-4" />
            New Pilot
          </button>

          <button
            onClick={() => {
              if (selectedPilotId) fetchPilotDetails(selectedPilotId);
              fetchPilots();
            }}
            className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white border border-slate-700 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-xl text-red-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Tabs Navigation */}
      {activePilot && (
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-[#102c50] text-blue-400 border border-blue-500/40 shadow-md shadow-blue-900/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Tab Content */}
      {activePilot ? (
        <div>
          {activeTab === 'overview' && (
            <PilotOverview
              pilot={activePilot}
              metrics={metrics}
              onRefresh={() => fetchPilotDetails(activePilot.id)}
              onSelectTab={(tab) => setActiveTab(tab)}
            />
          )}

          {activeTab === 'equipment' && (
            <EquipmentSelection
              pilot={activePilot}
              onRefresh={() => fetchPilotDetails(activePilot.id)}
            />
          )}

          {activeTab === 'readiness' && (
            <ReadinessChecklist
              pilot={activePilot}
              onRefresh={() => fetchPilotDetails(activePilot.id)}
            />
          )}

          {activeTab === 'monitoring' && (
            <PilotMonitoring
              pilot={activePilot}
              metrics={metrics}
            />
          )}

          {activeTab === 'feedback' && (
            <FeedbackForm
              pilot={activePilot}
              onRefresh={() => fetchPilotDetails(activePilot.id)}
            />
          )}

          {activeTab === 'reports' && (
            <PilotReport
              pilot={activePilot}
              onRefresh={() => fetchPilotDetails(activePilot.id)}
            />
          )}
        </div>
      ) : !loading ? (
        <div className="bg-[#102c50]/60 border border-slate-700/60 rounded-xl p-12 text-center space-y-3">
          <Compass className="w-10 h-10 text-slate-500 mx-auto" />
          <h3 className="text-base font-bold text-white">No Active Pilot Programs</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Create your first controlled factory pilot to begin shadow monitoring candidate equipment.
          </p>
          <button
            onClick={() => setShowSetup(true)}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs inline-flex items-center gap-1.5 transition-all shadow-md shadow-blue-600/30"
          >
            <Plus className="w-4 h-4" />
            Create Pilot Program
          </button>
        </div>
      ) : null}

      {/* Setup Modal */}
      {showSetup && (
        <PilotSetup
          siteId={sites[0]?.id || ''}
          onSuccess={handleSetupSuccess}
          onCancel={() => setShowSetup(false)}
        />
      )}
    </div>
  );
}

