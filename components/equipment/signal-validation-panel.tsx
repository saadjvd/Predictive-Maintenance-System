'use client'

import React, { useState, useEffect, useCallback } from 'react'
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  RefreshCw,
  Plus,
  Trash2,
  Edit2,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Zap,
  Sliders,
  Layers,
  ArrowRight,
  Loader2,
  Info,
} from 'lucide-react'
import apiClient, {
  MachineSignalItem,
  SignalValidationResultItem,
  MappingSummary,
  MachineComponentItem,
  UpdateSignalPayload,
} from '@/lib/api-client'
import SignalMappingWizard from './signal-mapping-wizard'

interface SignalValidationPanelProps {
  machineId: string
  machineName: string
  components: MachineComponentItem[]
}

export default function SignalValidationPanel({
  machineId,
  machineName,
  components,
}: SignalValidationPanelProps) {
  const [signals, setSignals] = useState<MachineSignalItem[]>([])
  const [summary, setSummary] = useState<MappingSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [validating, setValidating] = useState(false)
  const [selectedGroup, setSelectedGroup] = useState<string>('ALL')
  const [expandedSignalId, setExpandedSignalId] = useState<string | null>(null)
  const [showWizard, setShowWizard] = useState(false)

  // Edit Signal Modal State
  const [editingSignal, setEditingSignal] = useState<MachineSignalItem | null>(null)
  const [editFormData, setEditFormData] = useState<UpdateSignalPayload>({})
  const [savingEdit, setSavingEdit] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setActionError(null)
    try {
      const [signalsRes, summaryRes] = await Promise.all([
        apiClient.getMachineSignals(machineId),
        apiClient.getMachineMappingSummary(machineId),
      ])

      if (signalsRes.data?.signals) {
        setSignals(signalsRes.data.signals)
      }
      if (summaryRes.data) {
        setSummary(summaryRes.data)
      }
    } catch (err: any) {
      console.error('Failed to load signal mapping data:', err)
      setActionError('Failed to load signal mappings.')
    } finally {
      setLoading(false)
    }
  }, [machineId])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleRunValidation = async () => {
    setValidating(true)
    setActionError(null)
    setSuccessMessage(null)
    try {
      const res = await apiClient.validateMachineSignals(machineId)
      if (res.data) {
        setSummary(res.data.summary)
        setSuccessMessage(`Validation complete. Verified ${res.data.count} signals.`)
        await loadData()
      } else {
        setActionError(res.message || 'Validation failed.')
      }
    } catch (err: any) {
      setActionError(err?.message || 'Error executing validation engine.')
    } finally {
      setValidating(false)
    }
  }

  const handleDeleteSignal = async (signalId: string, signalName: string) => {
    if (!window.confirm(`Are you sure you want to delete signal mapping "${signalName}"?`)) {
      return
    }
    try {
      const res = await apiClient.deleteMachineSignal(machineId, signalId)
      if (res.error) {
        setActionError(res.message || 'Failed to delete signal.')
      } else {
        setSuccessMessage('Signal mapping deleted.')
        await loadData()
      }
    } catch (err: any) {
      setActionError(err?.message || 'Error deleting signal.')
    }
  }

  const openEditModal = (sig: MachineSignalItem) => {
    setEditingSignal(sig)
    setEditFormData({
      custom_name: sig.signal_name || '',
      component_id: sig.component_id || '',
      source_node_id: sig.source_node_id,
      source_unit: sig.source_unit || '',
      normalized_unit: sig.normalized_unit || '',
      scaling_factor: sig.scaling_factor,
      offset: sig.offset,
      sampling_interval_ms: sig.sampling_interval_ms,
      enabled: sig.enabled,
    })
  }

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingSignal) return
    setSavingEdit(true)
    try {
      const res = await apiClient.updateMachineSignal(machineId, editingSignal.id, editFormData)
      if (res.error) {
        setActionError(res.message || 'Failed to update signal mapping.')
      } else {
        setSuccessMessage('Signal mapping updated. Version incremented; validation status reset to PENDING.')
        setEditingSignal(null)
        await loadData()
      }
    } catch (err: any) {
      setActionError(err?.message || 'Error updating signal mapping.')
    } finally {
      setSavingEdit(false)
    }
  }

  // Filter signals
  const filteredSignals =
    selectedGroup === 'ALL'
      ? signals
      : signals.filter((s) => s.signal_group === selectedGroup)

  return (
    <div className="space-y-6">
      {/* Action Notification Banners */}
      {actionError && (
        <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-4 shrink-0 text-rose-500" />
            <span>{actionError}</span>
          </div>
          <button onClick={() => setActionError(null)} className="text-rose-400 hover:text-rose-600">
            ×
          </button>
        </div>
      )}

      {successMessage && (
        <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-700">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="size-4 shrink-0 text-emerald-500" />
            <span>{successMessage}</span>
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-400 hover:text-emerald-600">
            ×
          </button>
        </div>
      )}

      {/* Summary Metrics Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Mapped</span>
          <p className="mt-2 text-2xl font-black text-[#102c50]">{summary?.total_signals || 0}</p>
          <span className="text-[11px] text-slate-500">Configured telemetry tags</span>
        </div>

        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">Valid</span>
          <p className="mt-2 text-2xl font-black text-emerald-600">{summary?.valid_count || 0}</p>
          <span className="text-[11px] text-emerald-600">Passed 7 industrial checks</span>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-amber-50/40 p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700">Warnings</span>
          <p className="mt-2 text-2xl font-black text-amber-600">{summary?.warning_count || 0}</p>
          <span className="text-[11px] text-amber-600">Non-critical warnings</span>
        </div>

        <div className="rounded-2xl border border-rose-200 bg-rose-50/40 p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-rose-700">Invalid</span>
          <p className="mt-2 text-2xl font-black text-rose-600">{summary?.invalid_count || 0}</p>
          <span className="text-[11px] text-rose-600">Failed validation checks</span>
        </div>

        <div className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50/60 to-indigo-50/40 p-5 shadow-xs">
          <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700">Monitoring Ready</span>
          <div className="mt-2 flex items-center gap-2">
            {summary?.ready_for_monitoring ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500 px-2.5 py-1 text-xs font-bold text-white shadow-xs">
                <CheckCircle2 className="size-3.5" />
                Ready (Step 7)
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700">
                <Clock className="size-3.5" />
                Pending Validation
              </span>
            )}
          </div>
          <p className="mt-1.5 text-[10px] text-slate-500">
            {summary?.ready_for_monitoring
              ? 'All mapped signals verified'
              : 'Requires 0 invalid and 0 pending signals'}
          </p>
        </div>
      </div>

      {/* Main Signal Mapping & Validation Table Container */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-6">
        {/* Table Header & Actions */}
        <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-bold text-[#102c50]">Machine Signal Registry & Live Validation</h3>
            <p className="text-xs text-slate-500">
              Universal translation from OPC UA tags to PharmaPredict standardized signals.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={handleRunValidation}
              disabled={validating || signals.length === 0}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-50"
            >
              {validating ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <ShieldCheck className="size-3.5" />
              )}
              <span>{validating ? 'Executing 7 Checks...' : 'Run Signal Validation'}</span>
            </button>

            <button
              onClick={() => setShowWizard(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-[#1685ff] px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-[#126bd0]"
            >
              <Plus className="size-3.5" />
              <span>Map New Signal</span>
            </button>
          </div>
        </div>

        {/* Group Filter Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 pb-3">
          {['ALL', 'Temperature', 'Vibration', 'Motor Current', 'Speed', 'Pressure', 'Alarms', 'Cycles', 'Other'].map(
            (grp) => (
              <button
                key={grp}
                onClick={() => setSelectedGroup(grp)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  selectedGroup === grp
                    ? 'bg-[#102c50] text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {grp === 'ALL' ? 'All Signals' : grp}
                {summary?.group_breakdown?.[grp] ? (
                  <span className="ml-1.5 rounded-full bg-white/20 px-1.5 py-0.2 text-[10px]">
                    {summary.group_breakdown[grp]}
                  </span>
                ) : null}
              </button>
            )
          )}
        </div>

        {/* Signals List */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <Loader2 className="size-8 animate-spin text-[#1685ff]" />
            <p className="mt-3 text-xs font-medium">Loading signal mappings...</p>
          </div>
        ) : filteredSignals.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 py-16 text-center">
            <div className="flex size-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
              <Sliders className="size-6" />
            </div>
            <h4 className="mt-4 text-sm font-bold text-[#102c50]">No Signals Mapped Yet</h4>
            <p className="mt-1 max-w-sm text-xs text-slate-500">
              Map discovered OPC UA tags to standardized predictive maintenance signals (Temperature, Vibration, Speed, etc.).
            </p>
            <button
              onClick={() => setShowWizard(true)}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-[#1685ff] px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-[#126bd0]"
            >
              <Plus className="size-3.5" />
              <span>Map First Signal</span>
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredSignals.map((sig) => {
              const isExpanded = expandedSignalId === sig.id
              const latestVal = sig.latest_validation

              return (
                <div key={sig.id} className="py-4 transition hover:bg-slate-50/50 rounded-xl px-2">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    {/* Left: Signal info */}
                    <div className="flex items-start gap-3">
                      <button
                        onClick={() => setExpandedSignalId(isExpanded ? null : sig.id)}
                        className="mt-1 text-slate-400 hover:text-slate-600"
                      >
                        {isExpanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                      </button>

                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-bold text-xs text-[#102c50]">
                            {sig.signal_name || sig.signal_code}
                          </span>
                          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                            {sig.signal_group}
                          </span>
                          <span className="rounded-md bg-blue-50 px-2 py-0.5 text-[10px] font-mono text-blue-700 border border-blue-100">
                            v{sig.mapping_version}
                          </span>
                          {sig.component_name && (
                            <span className="flex items-center gap-1 rounded-md bg-slate-50 px-2 py-0.5 text-[10px] text-slate-500">
                              <Layers className="size-2.5" /> {sig.component_name}
                            </span>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                          <span className="font-mono text-[11px] text-slate-600">
                            NodeId: <strong className="text-slate-700">{sig.source_node_id}</strong>
                          </span>
                          <span>•</span>
                          <span>
                            Target Unit: <strong className="text-slate-700">{sig.normalized_unit || 'None'}</strong>
                          </span>
                          <span>•</span>
                          <span>
                            Rate: <strong className="text-slate-700">{sig.sampling_interval_ms}ms</strong>
                          </span>
                          <span>•</span>
                          <span>
                            Scale: <strong className="text-slate-700">×{sig.scaling_factor}</strong> ({sig.offset >= 0 ? `+${sig.offset}` : sig.offset})
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Right: Validation Status & Action Buttons */}
                    <div className="flex items-center gap-3 pl-7 lg:pl-0">
                      {/* Live sample snippet if present */}
                      {latestVal?.sample_reading && (
                        <div className="hidden sm:flex flex-col text-right text-xs">
                          <span className="text-[10px] font-semibold text-slate-400">Live Reading</span>
                          <span className="font-mono font-bold text-slate-800">
                            {typeof latestVal.sample_reading.normalized_value === 'number'
                              ? latestVal.sample_reading.normalized_value.toFixed(2)
                              : String(latestVal.sample_reading.normalized_value)}{' '}
                            {sig.normalized_unit || ''}
                          </span>
                        </div>
                      )}

                      {/* Status Badge */}
                      {sig.validation_status === 'VALID' ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
                          <CheckCircle2 className="size-3.5 text-emerald-600" />
                          VALID
                        </span>
                      ) : sig.validation_status === 'WARNING' ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-800">
                          <AlertTriangle className="size-3.5 text-amber-600" />
                          WARNING
                        </span>
                      ) : sig.validation_status === 'INVALID' ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-3 py-1 text-xs font-bold text-rose-800">
                          <XCircle className="size-3.5 text-rose-600" />
                          INVALID
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
                          <Clock className="size-3.5 text-slate-400" />
                          PENDING
                        </span>
                      )}

                      {/* Actions */}
                      <button
                        onClick={() => openEditModal(sig)}
                        title="Edit mapping (increments version)"
                        className="rounded-lg border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                      >
                        <Edit2 className="size-3.5" />
                      </button>

                      <button
                        onClick={() => handleDeleteSignal(sig.id, sig.signal_name || sig.source_node_id)}
                        title="Delete signal mapping"
                        className="rounded-lg border border-slate-200 p-1.5 text-rose-500 hover:bg-rose-50 hover:text-rose-700"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Expanded Accordion: 7 Validation Checks Breakdown */}
                  {isExpanded && (
                    <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
                      <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                        <span className="text-xs font-bold text-[#102c50] uppercase tracking-wider">
                          Validation Checks Audit Log (Version {sig.mapping_version})
                        </span>
                        {latestVal?.validated_at && (
                          <span className="text-[11px] text-slate-400">
                            Validated at: {new Date(latestVal.validated_at).toLocaleString()}
                          </span>
                        )}
                      </div>

                      {latestVal ? (
                        <div className="space-y-2">
                          {Object.entries(latestVal.validation_checks || {}).map(([checkName, checkData]) => (
                            <div
                              key={checkName}
                              className="flex items-start gap-2 text-xs rounded-lg bg-white p-2.5 border border-slate-200/80"
                            >
                              {checkData.passed ? (
                                checkData.severity === 'WARNING' ? (
                                  <AlertTriangle className="size-4 shrink-0 text-amber-500 mt-0.5" />
                                ) : (
                                  <CheckCircle2 className="size-4 shrink-0 text-emerald-500 mt-0.5" />
                                )
                              ) : (
                                <XCircle className="size-4 shrink-0 text-rose-500 mt-0.5" />
                              )}
                              <div className="space-y-0.5">
                                <span className="font-semibold text-slate-700 capitalize">
                                  {checkName.replace(/_/g, ' ')}:
                                </span>
                                <p className="text-slate-600 text-[11px]">{checkData.message}</p>
                              </div>
                            </div>
                          ))}

                          {/* Live Sample Summary */}
                          {latestVal.sample_reading && (
                            <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-3 text-xs text-blue-900 space-y-1">
                              <span className="font-bold text-[11px] uppercase tracking-wider text-blue-800">
                                Strictly Read-Only Sample Telemetry
                              </span>
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-[11px]">
                                <div>
                                  <span className="text-slate-500 block">Raw Value:</span>
                                  <strong>{String(latestVal.sample_reading.raw_value)}</strong>
                                </div>
                                <div>
                                  <span className="text-slate-500 block">Normalized:</span>
                                  <strong>
                                    {String(latestVal.sample_reading.normalized_value)}{' '}
                                    {latestVal.sample_reading.normalized_unit || ''}
                                  </strong>
                                </div>
                                <div>
                                  <span className="text-slate-500 block">Quality:</span>
                                  <strong className="text-emerald-700">{latestVal.sample_reading.quality}</strong>
                                </div>
                                <div>
                                  <span className="text-slate-500 block">Sample Timestamp:</span>
                                  <span>{latestVal.sample_reading.timestamp ? new Date(latestVal.sample_reading.timestamp).toLocaleTimeString() : 'N/A'}</span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-500 italic">
                          Signal has not been validated yet. Click &quot;Run Signal Validation&quot; above to execute the 7-check inspection engine.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Signal Mapping Wizard Dialog */}
      <SignalMappingWizard
        machineId={machineId}
        machineName={machineName}
        isOpen={showWizard}
        onClose={() => setShowWizard(false)}
        onSuccess={loadData}
        components={components}
      />

      {/* Edit Signal Modal */}
      {editingSignal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl space-y-5">
            <div className="border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold text-[#102c50]">Edit Signal Mapping Configuration</h3>
              <p className="text-xs text-slate-500">
                Updating mapping increments <span className="font-semibold text-slate-700">mapping_version</span> and resets status to <span className="font-semibold text-slate-700">PENDING</span>.
              </p>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-700">Signal Custom Name</label>
                <input
                  type="text"
                  value={editFormData.custom_name || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, custom_name: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs focus:border-[#1685ff] focus:outline-none"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Source OPC UA NodeId</label>
                <input
                  type="text"
                  required
                  value={editFormData.source_node_id || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, source_node_id: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs focus:border-[#1685ff] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700">Normalized Target Unit</label>
                  <input
                    type="text"
                    value={editFormData.normalized_unit || ''}
                    onChange={(e) => setEditFormData({ ...editFormData, normalized_unit: e.target.value })}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Sampling Interval (ms)</label>
                  <input
                    type="number"
                    min="50"
                    max="3600000"
                    step="50"
                    value={editFormData.sampling_interval_ms || 1000}
                    onChange={(e) =>
                      setEditFormData({ ...editFormData, sampling_interval_ms: parseInt(e.target.value) || 1000 })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700">Scaling Factor</label>
                  <input
                    type="number"
                    step="any"
                    value={editFormData.scaling_factor ?? 1.0}
                    onChange={(e) =>
                      setEditFormData({ ...editFormData, scaling_factor: parseFloat(e.target.value) || 1.0 })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Offset</label>
                  <input
                    type="number"
                    step="any"
                    value={editFormData.offset ?? 0.0}
                    onChange={(e) =>
                      setEditFormData({ ...editFormData, offset: parseFloat(e.target.value) || 0.0 })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-slate-100 pt-3">
                <button
                  type="button"
                  onClick={() => setEditingSignal(null)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingEdit}
                  className="rounded-lg bg-[#1685ff] px-5 py-2 text-xs font-bold text-white hover:bg-[#126bd0] disabled:opacity-50"
                >
                  {savingEdit ? 'Updating...' : 'Save & Bump Version'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

