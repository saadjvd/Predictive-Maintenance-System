'use client';

import React, { useState, useEffect } from 'react';
import {
  FactoryPilotItem,
  EquipmentItem,
  apiClient,
} from '@/lib/api-client';
import {
  Layers,
  Plus,
  Check,
  Shield,
  Activity,
  AlertCircle,
} from 'lucide-react';

interface EquipmentSelectionProps {
  pilot: FactoryPilotItem;
  onRefresh: () => void;
}

export const EquipmentSelection: React.FC<EquipmentSelectionProps> = ({
  pilot,
  onRefresh,
}) => {
  const [availableMachines, setAvailableMachines] = useState<EquipmentItem[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMachines = async () => {
      setLoading(true);
      try {
        const res = await apiClient.getEquipment({ site_id: pilot.site_id });
        if (res.status === 200 && res.data) {
          const machines = Array.isArray(res.data) ? res.data : [];
          setAvailableMachines(machines);
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to load machines');
      } finally {
        setLoading(false);
      }
    };

    fetchMachines();
  }, [pilot.site_id]);

  const enrolledIds = new Set((pilot.equipment || []).map((e) => e.machine_id));

  const toggleSelection = (machineId: string) => {
    setSelectedIds((prev) =>
      prev.includes(machineId) ? prev.filter((id) => id !== machineId) : [...prev, machineId]
    );
  };

  const handleEnroll = async () => {
    if (selectedIds.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      await apiClient.assignPilotEquipment(pilot.id, selectedIds, 'SHADOW');
      setSelectedIds([]);
      onRefresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to enroll equipment');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Enrolled Equipment Card */}
      <div className="bg-[#102c50]/80 border border-slate-700/60 rounded-xl p-6 shadow-xl">
        <h3 className="text-xl font-bold text-white flex items-center gap-2">
          <Layers className="w-5 h-5 text-blue-400" />
          Enrolled Candidate Production Equipment
        </h3>
        <p className="text-xs text-slate-400 mt-1">
          Machines currently monitored in read-only SHADOW MODE under this pilot program.
        </p>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(pilot.equipment || []).map((eq) => (
            <div
              key={eq.id}
              className="bg-slate-900/60 border border-slate-700/80 rounded-lg p-4 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-bold bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded border border-blue-700/30">
                    {eq.asset_code || 'ASSET'}
                  </span>
                  <span className="text-[10px] font-bold text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded">
                    SHADOW
                  </span>
                </div>
                <h4 className="text-sm font-semibold text-white mt-2">
                  {eq.machine_name || `Machine ${eq.machine_id.slice(0, 8)}`}
                </h4>
                <p className="text-xs text-slate-400 mt-1">
                  Enrolled: {new Date(eq.assigned_at).toLocaleDateString()}
                </p>
              </div>

              <div className="mt-3 pt-2 border-t border-slate-800 flex items-center gap-1.5 text-[11px] text-slate-400">
                <Shield className="w-3.5 h-3.5 text-blue-400" />
                <span>Zero write capability enforced</span>
              </div>
            </div>
          ))}

          {(pilot.equipment || []).length === 0 && (
            <div className="col-span-full p-6 text-center text-slate-500 text-sm">
              No equipment enrolled in this pilot yet. Select from available site equipment below.
            </div>
          )}
        </div>
      </div>

      {/* Available Equipment Picker */}
      <div className="bg-[#102c50]/80 border border-slate-700/60 rounded-xl p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-white">Enroll New Site Equipment</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Select machines from the site equipment hierarchy to add to shadow monitoring.
            </p>
          </div>

          <button
            disabled={saving || selectedIds.length === 0}
            onClick={handleEnroll}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-sm flex items-center gap-2 transition-all shadow-md shadow-blue-600/30"
          >
            <Plus className="w-4 h-4" />
            Enroll Selected ({selectedIds.length})
          </button>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-950/40 border border-red-800/60 rounded-lg text-red-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {availableMachines
            .filter((m) => !enrolledIds.has(m.id))
            .map((m) => {
              const isSelected = selectedIds.includes(m.id);
              return (
                <div
                  key={m.id}
                  onClick={() => toggleSelection(m.id)}
                  className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-blue-900/30 border-blue-500 text-white shadow-md shadow-blue-900/20'
                      : 'bg-slate-900/40 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                      {m.asset_code}
                    </span>
                    <div
                      className={`w-4 h-4 rounded flex items-center justify-center border ${
                        isSelected
                          ? 'bg-blue-600 border-blue-500 text-white'
                          : 'border-slate-700 bg-slate-800'
                      }`}
                    >
                      {isSelected && <Check className="w-3 h-3" />}
                    </div>
                  </div>
                  <h5 className="text-sm font-semibold mt-1.5">{m.equipment_name}</h5>
                  <p className="text-[11px] text-slate-400 mt-0.5">Criticality: {m.criticality || 'Normal'}</p>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
};

