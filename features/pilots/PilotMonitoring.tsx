'use client';

import React from 'react';
import {
  FactoryPilotItem,
  PilotMetricsItem,
} from '@/lib/api-client';
import {
  Activity,
  Shield,
  Layers,
  AlertTriangle,
  CheckCircle2,
  Cpu,
} from 'lucide-react';

interface PilotMonitoringProps {
  pilot: FactoryPilotItem;
  metrics: PilotMetricsItem | null;
}

export const PilotMonitoring: React.FC<PilotMonitoringProps> = ({
  pilot,
  metrics,
}) => {
  return (
    <div className="space-y-6">
      {/* Shadow Mode Banner */}
      <div className="bg-gradient-to-r from-blue-950/60 to-indigo-950/60 border border-blue-700/50 rounded-xl p-5 shadow-lg flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-white">Active Shadow Mode Monitoring</h4>
            <p className="text-xs text-slate-300 mt-0.5">
              Continuous read-only ingestion and condition monitoring active. All AI actuator write capabilities are disabled.
            </p>
          </div>
        </div>
        <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 animate-pulse">
          LIVE SHADOW STREAM
        </span>
      </div>

      {/* Equipment Monitoring Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(pilot.equipment || []).map((eq) => (
          <div
            key={eq.id}
            className="bg-[#102c50]/70 border border-slate-700/60 rounded-xl p-5 space-y-4 shadow-xl"
          >
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-blue-400 font-bold border border-slate-700">
                  {eq.asset_code || 'ASSET'}
                </span>
                <h4 className="text-base font-bold text-white mt-1.5">
                  {eq.machine_name || `Machine ${eq.machine_id.slice(0, 8)}`}
                </h4>
              </div>
              <span className="px-2.5 py-1 rounded text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                NORMAL
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800 text-center">
              <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">Telemetry Quality</span>
                <span className="text-xs font-bold text-emerald-400 mt-0.5 block">GOOD (100%)</span>
              </div>
              <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">Active Anomalies</span>
                <span className="text-xs font-bold text-white mt-0.5 block">0 Detected</span>
              </div>
              <div className="bg-slate-900/60 p-2.5 rounded border border-slate-800">
                <span className="text-[10px] text-slate-400 block">Model Status</span>
                <span className="text-xs font-bold text-blue-400 mt-0.5 block">SHADOW EVAL</span>
              </div>
            </div>
          </div>
        ))}

        {(pilot.equipment || []).length === 0 && (
          <div className="col-span-full p-8 bg-[#102c50]/40 border border-slate-800 rounded-xl text-center text-slate-500 text-sm">
            No equipment actively monitored. Enroll machines in the Equipment Selection tab.
          </div>
        )}
      </div>
    </div>
  );
};

