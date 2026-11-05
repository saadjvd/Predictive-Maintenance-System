'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api-client';
import { PlusCircle, AlertCircle, X, ShieldCheck } from 'lucide-react';

interface PilotSetupProps {
  siteId: string;
  onSuccess: (newPilotId: string) => void;
  onCancel: () => void;
}

export const PilotSetup: React.FC<PilotSetupProps> = ({
  siteId,
  onSuccess,
  onCancel,
}) => {
  const [pilotName, setPilotName] = useState('');
  const [description, setDescription] = useState('');
  const [objectives, setObjectives] = useState('');
  const [monitoringMode, setMonitoringMode] = useState<'SHADOW' | 'ADVISORY'>('SHADOW');
  const [plannedStartDate, setPlannedStartDate] = useState('');
  const [plannedEndDate, setPlannedEndDate] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pilotName.trim()) {
      setError('Pilot name is required.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.createPilot({
        site_id: siteId,
        pilot_name: pilotName.trim(),
        description: description.trim() || undefined,
        objectives: objectives.trim() || undefined,
        monitoring_mode: monitoringMode,
        planned_start_date: plannedStartDate ? new Date(plannedStartDate).toISOString() : undefined,
        planned_end_date: plannedEndDate ? new Date(plannedEndDate).toISOString() : undefined,
      });

      if (res.status === 201 && res.data) {
        onSuccess(res.data.id);
      } else {
        setError(res.error || 'Failed to create pilot program.');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create pilot.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-[#102c50] border border-slate-700/80 rounded-xl p-6 shadow-2xl max-w-lg w-full space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <PlusCircle className="w-5 h-5 text-blue-400" />
            <h3 className="text-base font-bold text-white">Create Controlled Factory Pilot</h3>
          </div>
          <button
            onClick={onCancel}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3.5">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Pilot Program Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              value={pilotName}
              onChange={(e) => setPilotName(e.target.value)}
              placeholder="e.g. Getz Site 1 Packaging Line Shadow Pilot"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Scope & Description</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Controlled 12-week shadow monitoring pilot on packaging lines."
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Pilot Objectives</label>
            <textarea
              rows={2}
              value={objectives}
              onChange={(e) => setObjectives(e.target.value)}
              placeholder="Verify vibration anomaly detection accuracy; zero batch disruptions."
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Planned Start Date</label>
              <input
                type="date"
                value={plannedStartDate}
                onChange={(e) => setPlannedStartDate(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Planned End Date</label>
              <input
                type="date"
                value={plannedEndDate}
                onChange={(e) => setPlannedEndDate(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div className="p-3 bg-blue-950/30 border border-blue-800/40 rounded-lg text-blue-300 text-xs flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 shrink-0 text-blue-400" />
            <span>Pilot will be initialized in DRAFT with a 17-item GAMP 5 readiness checklist.</span>
          </div>

          {error && (
            <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-lg text-red-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
              <span>{error}</span>
            </div>
          )}

          <div className="pt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 text-xs font-medium transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold transition-all shadow-md shadow-blue-600/30"
            >
              {loading ? 'Creating...' : 'Create Pilot'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

