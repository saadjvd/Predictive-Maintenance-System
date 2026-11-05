'use client'

import React, { useState, useEffect } from 'react'
import {
  X,
  Layers,
  Activity,
  Plus,
  AlertCircle,
  CheckCircle2,
  Sliders,
  Clock,
  Sparkles,
  Info,
  Loader2,
  Cpu,
} from 'lucide-react'
import apiClient, {
  SignalDefinitionItem,
  MachineComponentItem,
  CreateSignalPayload,
  DiscoveredTag,
} from '@/lib/api-client'

interface SignalMappingWizardProps {
  machineId: string
  machineName: string
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  initialTag?: DiscoveredTag | null
  components: MachineComponentItem[]
}

const SIGNAL_GROUPS = [
  'Temperature',
  'Vibration',
  'Motor Current',
  'Speed',
  'Pressure',
  'Alarms',
  'Cycles',
  'Other',
]

export default function SignalMappingWizard({
  machineId,
  machineName,
  isOpen,
  onClose,
  onSuccess,
  initialTag,
  components,
}: SignalMappingWizardProps) {
  const [definitions, setDefinitions] = useState<SignalDefinitionItem[]>([])
  const [loadingDefs, setLoadingDefs] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form State
  const [selectedGroup, setSelectedGroup] = useState<string>('Temperature')
  const [selectedDefinitionId, setSelectedDefinitionId] = useState<string>('')
  const [customName, setCustomName] = useState<string>('')
  const [componentId, setComponentId] = useState<string>('')
  const [sourceNodeId, setSourceNodeId] = useState<string>('')
  const [sourceBrowseName, setSourceBrowseName] = useState<string>('')
  const [sourceDataType, setSourceDataType] = useState<string>('')
  const [sourceUnit, setSourceUnit] = useState<string>('')
  const [normalizedUnit, setNormalizedUnit] = useState<string>('')
  const [scalingFactor, setScalingFactor] = useState<number>(1.0)
  const [offset, setOffset] = useState<number>(0.0)
  const [samplingIntervalMs, setSamplingIntervalMs] = useState<number>(1000)

  // Custom Definition Creator Inline Modal
  const [showCustomDefModal, setShowCustomDefModal] = useState(false)
  const [customDefData, setCustomDefData] = useState({
    signal_code: '',
    name: '',
    signal_group: 'Temperature',
    expected_data_type: 'Double',
    standard_unit: '°C',
    measurement_dimension: 'temperature',
    description: '',
  })
  const [creatingCustomDef, setCreatingCustomDef] = useState(false)

  // Load definitions
  useEffect(() => {
    if (!isOpen) return
    const fetchDefinitions = async () => {
      setLoadingDefs(true)
      try {
        const res = await apiClient.getSignalDefinitions()
        if (res.data?.definitions) {
          setDefinitions(res.data.definitions)
        }
      } catch (err: any) {
        console.error('Failed to load signal definitions:', err)
      } finally {
        setLoadingDefs(false)
      }
    }
    fetchDefinitions()
  }, [isOpen])

  // Populate from initial tag when available
  useEffect(() => {
    if (initialTag) {
      setSourceNodeId(initialTag.node_id)
      setSourceBrowseName(initialTag.browse_name || '')
      setSourceDataType(initialTag.data_type || 'Double')
      setSourceUnit(initialTag.engineering_unit || '')
      setCustomName(initialTag.display_name || initialTag.browse_name || '')

      // Auto-suggest group and unit based on tag name or unit
      const nameLower = (initialTag.browse_name || '').toLowerCase()
      const unitLower = (initialTag.engineering_unit || '').toLowerCase()

      if (nameLower.includes('temp') || unitLower.includes('°c') || unitLower.includes('celsius')) {
        setSelectedGroup('Temperature')
        setNormalizedUnit('°C')
      } else if (nameLower.includes('vib') || unitLower.includes('mm/s')) {
        setSelectedGroup('Vibration')
        setNormalizedUnit('mm/s')
      } else if (unitLower.includes('g') || unitLower.includes('m/s2')) {
        setSelectedGroup('Vibration')
        setNormalizedUnit('g')
      } else if (nameLower.includes('curr') || unitLower.includes('a') || unitLower.includes('amp')) {
        setSelectedGroup('Motor Current')
        setNormalizedUnit('A')
      } else if (nameLower.includes('rpm') || nameLower.includes('speed') || unitLower.includes('rpm')) {
        setSelectedGroup('Speed')
        setNormalizedUnit('RPM')
      } else if (nameLower.includes('press') || nameLower.includes('vac') || unitLower.includes('bar')) {
        setSelectedGroup('Pressure')
        setNormalizedUnit('bar')
      } else if (nameLower.includes('alarm') || nameLower.includes('trip') || initialTag.data_type === 'Boolean') {
        setSelectedGroup('Alarms')
        setNormalizedUnit('Boolean')
      } else if (nameLower.includes('count') || nameLower.includes('cycle')) {
        setSelectedGroup('Cycles')
        setNormalizedUnit('Count')
      }
    }
  }, [initialTag])

  // Filter definitions for selected group
  const groupDefinitions = definitions.filter((d) => d.signal_group === selectedGroup)

  // Auto-select definition if none selected
  useEffect(() => {
    if (groupDefinitions.length > 0 && !groupDefinitions.some((d) => d.id === selectedDefinitionId)) {
      setSelectedDefinitionId(groupDefinitions[0].id)
      if (!normalizedUnit && groupDefinitions[0].standard_unit) {
        setNormalizedUnit(groupDefinitions[0].standard_unit)
      }
    }
  }, [selectedGroup, groupDefinitions, selectedDefinitionId, normalizedUnit])

  // Selected definition object
  const activeDef = definitions.find((d) => d.id === selectedDefinitionId)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedDefinitionId) {
      setError('Please select a target signal definition.')
      return
    }
    if (!sourceNodeId.trim()) {
      setError('Source OPC UA NodeId is required.')
      return
    }
    if (scalingFactor === 0) {
      setError('Scaling factor cannot be zero.')
      return
    }

    setSaving(true)
    setError(null)

    const payload: CreateSignalPayload = {
      signal_definition_id: selectedDefinitionId,
      source_node_id: sourceNodeId.trim(),
      source_browse_name: sourceBrowseName.trim() || undefined,
      source_data_type: sourceDataType.trim() || undefined,
      source_unit: sourceUnit.trim() || undefined,
      normalized_unit: normalizedUnit.trim() || activeDef?.standard_unit || undefined,
      custom_name: customName.trim() || undefined,
      component_id: componentId || undefined,
      scaling_factor: Number(scalingFactor),
      offset: Number(offset),
      sampling_interval_ms: Number(samplingIntervalMs),
      enabled: true,
    }

    try {
      const res = await apiClient.createMachineSignals(machineId, payload)
      if (res.error) {
        setError(res.message || 'Failed to create signal mapping.')
      } else {
        onSuccess()
        onClose()
      }
    } catch (err: any) {
      setError(err?.message || 'Network error mapping signal.')
    } finally {
      setSaving(false)
    }
  }

  const handleCreateCustomDef = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!customDefData.signal_code.trim() || !customDefData.name.trim()) {
      return
    }
    setCreatingCustomDef(true)
    try {
      const res = await apiClient.createCustomSignalDefinition(customDefData)
      if (res.data?.definition) {
        setDefinitions((prev) => [...prev, res.data!.definition])
        setSelectedGroup(res.data.definition.signal_group)
        setSelectedDefinitionId(res.data.definition.id)
        setShowCustomDefModal(false)
      } else {
        setError(res.message || 'Failed to create custom signal definition.')
      }
    } catch (err: any) {
      setError(err?.message || 'Error creating custom definition.')
    } finally {
      setCreatingCustomDef(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/80 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-[#1685ff]/10 text-[#1685ff]">
              <Sliders className="size-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#102c50]">Map OPC UA Tag to Industrial Signal</h2>
              <p className="text-xs text-slate-500">
                Equipment: <span className="font-semibold text-slate-700">{machineName}</span> • Standardized Pharma Taxonomy
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-200 hover:text-slate-700"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
              <AlertCircle className="size-4 shrink-0 mt-0.5 text-rose-500" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid gap-6 md:grid-cols-2">
            {/* Left Column: Source OPC UA Tag Details */}
            <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50/50 p-4">
              <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
                <Cpu className="size-4 text-[#1685ff]" />
                <h3 className="text-xs font-bold text-[#102c50] uppercase tracking-wider">
                  Source OPC UA Tag
                </h3>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">OPC UA NodeId *</label>
                <input
                  type="text"
                  required
                  value={sourceNodeId}
                  onChange={(e) => setSourceNodeId(e.target.value)}
                  placeholder="ns=2;s=Machine.Sensor.Temperature"
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700">Browse Name</label>
                  <input
                    type="text"
                    value={sourceBrowseName}
                    onChange={(e) => setSourceBrowseName(e.target.value)}
                    placeholder="Temperature"
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Source Data Type</label>
                  <input
                    type="text"
                    value={sourceDataType}
                    onChange={(e) => setSourceDataType(e.target.value)}
                    placeholder="Double / Float"
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Source Engineering Unit</label>
                <input
                  type="text"
                  value={sourceUnit}
                  onChange={(e) => setSourceUnit(e.target.value)}
                  placeholder="°C, bar, mm/s, RPM, etc."
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                />
                <span className="text-[11px] text-slate-400">
                  Leave empty if not provided by OPC UA server metadata.
                </span>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Attach to Component</label>
                <select
                  value={componentId}
                  onChange={(e) => setComponentId(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                >
                  <option value="">Whole Machine (Asset Level)</option>
                  {components.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.component_name} ({c.component_type || 'Subsystem'})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Right Column: Standardized Signal Definition */}
            <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50/50 p-4">
              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                <div className="flex items-center gap-2">
                  <Activity className="size-4 text-[#1685ff]" />
                  <h3 className="text-xs font-bold text-[#102c50] uppercase tracking-wider">
                    Standardized Signal Mapping
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setShowCustomDefModal(true)}
                  className="inline-flex items-center gap-1 text-[11px] font-bold text-[#1685ff] hover:underline"
                >
                  <Plus className="size-3" /> Custom Def
                </button>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Signal Group</label>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {SIGNAL_GROUPS.map((grp) => (
                    <button
                      key={grp}
                      type="button"
                      onClick={() => setSelectedGroup(grp)}
                      className={`rounded-lg px-2.5 py-1 text-[11px] font-semibold transition ${
                        selectedGroup === grp
                          ? 'bg-[#102c50] text-white shadow-sm'
                          : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {grp}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Signal Definition *</label>
                {loadingDefs ? (
                  <div className="flex items-center gap-2 py-2 text-xs text-slate-400">
                    <Loader2 className="size-3.5 animate-spin" /> Loading catalog...
                  </div>
                ) : (
                  <select
                    value={selectedDefinitionId}
                    onChange={(e) => setSelectedDefinitionId(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                  >
                    {groupDefinitions.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} ({d.signal_code}) {d.standard_unit ? `[${d.standard_unit}]` : ''}
                      </option>
                    ))}
                  </select>
                )}
                {activeDef?.description && (
                  <p className="mt-1 text-[11px] text-slate-500 italic">{activeDef.description}</p>
                )}
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Custom Signal Name / Alias</label>
                <input
                  type="text"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  placeholder="e.g. Station 1 Drive Motor Temp"
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                />
                <span className="text-[11px] text-slate-400">
                  Multi-sensor support: specify custom names to map multiple sensors to the same group.
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700">Normalized Target Unit</label>
                  <input
                    type="text"
                    value={normalizedUnit}
                    onChange={(e) => setNormalizedUnit(e.target.value)}
                    placeholder={activeDef?.standard_unit || '°C'}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Sampling Interval (ms)</label>
                  <input
                    type="number"
                    min="50"
                    max="3600000"
                    step="50"
                    value={samplingIntervalMs}
                    onChange={(e) => setSamplingIntervalMs(parseInt(e.target.value) || 1000)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
              </div>

              {/* Calibration / Linear Scaling */}
              <div className="grid grid-cols-2 gap-3 border-t border-slate-200 pt-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700">Scaling Factor (Multiplier)</label>
                  <input
                    type="number"
                    step="any"
                    value={scalingFactor}
                    onChange={(e) => setScalingFactor(parseFloat(e.target.value) || 1.0)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                  />
                  <span className="text-[10px] text-slate-400">raw × factor</span>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Offset (Addition)</label>
                  <input
                    type="number"
                    step="any"
                    value={offset}
                    onChange={(e) => setOffset(parseFloat(e.target.value) || 0.0)}
                    className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 shadow-sm focus:border-[#1685ff] focus:outline-none"
                  />
                  <span className="text-[10px] text-slate-400">+ offset</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-xl bg-blue-50/70 p-3 text-[11px] text-blue-900 border border-blue-100">
            <Info className="size-4 shrink-0 text-[#1685ff]" />
            <span>
              New mappings start in <strong className="font-semibold text-slate-700">PENDING</strong> state with version 1.
              Running validation will execute all 7 data-integrity and read-only live checks.
            </span>
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-100"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-lg bg-[#1685ff] px-5 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-[#126bd0] disabled:opacity-50"
            >
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />}
              <span>Save Signal Mapping</span>
            </button>
          </div>
        </form>

        {/* Inline Modal: Create Custom Definition */}
        {showCustomDefModal && (
          <div className="absolute inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-xs">
            <div className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-xl space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <h4 className="text-sm font-bold text-[#102c50]">Add Custom Signal Definition</h4>
                <button
                  type="button"
                  onClick={() => setShowCustomDefModal(false)}
                  className="rounded p-1 text-slate-400 hover:bg-slate-100"
                >
                  <X className="size-4" />
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700">Signal Code *</label>
                  <input
                    type="text"
                    placeholder="e.g. CHUTE_JAM_SENSOR"
                    value={customDefData.signal_code}
                    onChange={(e) =>
                      setCustomDefData({ ...customDefData, signal_code: e.target.value.toUpperCase() })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-1.5 font-mono text-xs focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Display Name *</label>
                  <input
                    type="text"
                    placeholder="Chute Optical Jam Sensor"
                    value={customDefData.name}
                    onChange={(e) => setCustomDefData({ ...customDefData, name: e.target.value })}
                    className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs focus:border-[#1685ff] focus:outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-slate-700">Group</label>
                    <select
                      value={customDefData.signal_group}
                      onChange={(e) =>
                        setCustomDefData({ ...customDefData, signal_group: e.target.value })
                      }
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs focus:border-[#1685ff] focus:outline-none"
                    >
                      {SIGNAL_GROUPS.map((g) => (
                        <option key={g} value={g}>
                          {g}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-700">Standard Unit</label>
                    <input
                      type="text"
                      placeholder="e.g. °C, bar, Boolean"
                      value={customDefData.standard_unit}
                      onChange={(e) =>
                        setCustomDefData({ ...customDefData, standard_unit: e.target.value })
                      }
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs focus:border-[#1685ff] focus:outline-none"
                    >
                    </input>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-2 border-t border-slate-100 pt-3">
                <button
                  type="button"
                  onClick={() => setShowCustomDefModal(false)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCreateCustomDef}
                  disabled={creatingCustomDef}
                  className="rounded-lg bg-[#1685ff] px-4 py-1.5 text-xs font-bold text-white hover:bg-[#126bd0]"
                >
                  {creatingCustomDef ? 'Creating...' : 'Save Definition'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

