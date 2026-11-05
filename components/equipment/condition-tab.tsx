'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  RefreshCw,
  Sliders,
  Sparkles,
  Layers,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Flame,
  Check,
  Zap,
  Info,
  Brain,
  BellRing,
  CheckCircle,
  FileText,
} from 'lucide-react'
import apiClient, {
  ConditionSummaryResponse,
  AnomalyEventItem,
  BaselineProfileItem,
  EquipmentAlertItem,
  MLModelRegistryItem,
  OperatingContextResponse,
  DataQualityReport,
} from '@/lib/api-client'

interface ConditionTabProps {
  machineId: string
  machineName: string
}

export default function ConditionTab({ machineId, machineName }: ConditionTabProps) {
  const [loading, setLoading] = useState(true)
  const [evaluating, setEvaluating] = useState(false)
  const [trainingML, setTrainingML] = useState(false)
  const [buildingBaselines, setBuildingBaselines] = useState(false)
  const [approvingBaselineId, setApprovingBaselineId] = useState<string | null>(null)
  const [acknowledgingAlertId, setAcknowledgingAlertId] = useState<string | null>(null)
  const [alertNotes, setAlertNotes] = useState('')
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Data states
  const [condition, setCondition] = useState<ConditionSummaryResponse | null>(null)
  const [anomalies, setAnomalies] = useState<AnomalyEventItem[]>([])
  const [baselines, setBaselines] = useState<BaselineProfileItem[]>([])
  const [alerts, setAlerts] = useState<EquipmentAlertItem[]>([])
  const [mlModels, setMLModels] = useState<MLModelRegistryItem | null>(null)
  const [expandedAnomalyId, setExpandedAnomalyId] = useState<string | null>(null)
  const [activeSubView, setActiveSubView] = useState<'anomalies' | 'baselines' | 'alerts' | 'ml'>('anomalies')

  const fetchAllData = useCallback(async () => {
    try {
      const [condRes, anomRes, baseRes, alertRes, mlRes] = await Promise.all([
        apiClient.getConditionSummary(machineId),
        apiClient.getAnomalies(machineId, { limit: 25 }),
        apiClient.getBaselines(machineId),
        apiClient.getAlerts({ machine_id: machineId, limit: 25 }),
        apiClient.getMLModels(machineId),
      ])

      if (condRes.data) setCondition(condRes.data)
      if (anomRes.data?.anomalies) setAnomalies(anomRes.data.anomalies)
      if (baseRes.data?.profiles) setBaselines(baseRes.data.profiles)
      if (alertRes.data?.alerts) setAlerts(alertRes.data.alerts)
      if (mlRes.data) setMLModels(mlRes.data)
    } catch (err: any) {
      console.error('Failed to load condition data:', err)
    } finally {
      setLoading(false)
    }
  }, [machineId])

  useEffect(() => {
    fetchAllData()
    const interval = setInterval(fetchAllData, 10000)
    return () => clearInterval(interval)
  }, [fetchAllData])

  const handleEvaluateNow = async () => {
    setEvaluating(true)
    setStatusMessage(null)
    try {
      const res = await apiClient.evaluateCondition(machineId, 15)
      if (res.data) {
        setStatusMessage({ type: 'success', text: 'Condition and anomaly evaluation completed successfully.' })
        await fetchAllData()
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Evaluation failed.' })
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Evaluation error.' })
    } finally {
      setEvaluating(false)
    }
  }

  const handleTrainML = async () => {
    setTrainingML(true)
    setStatusMessage(null)
    try {
      const res = await apiClient.trainMLModel(machineId, 7)
      if (res.data) {
        setStatusMessage({ type: 'success', text: 'Multivariate Isolation Forest model trained and deployed.' })
        await fetchAllData()
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Training failed.' })
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Model training error.' })
    } finally {
      setTrainingML(false)
    }
  }

  const handleBuildBaselines = async () => {
    setBuildingBaselines(true)
    setStatusMessage(null)
    try {
      const res = await apiClient.buildBaselines(machineId, { lookback_days: 7, operating_state: 'RUNNING' })
      if (res.data) {
        setStatusMessage({ type: 'success', text: 'Candidate baselines computed from clean historical data.' })
        await fetchAllData()
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Baseline building failed.' })
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Baseline error.' })
    } finally {
      setBuildingBaselines(false)
    }
  }

  const handleApproveBaseline = async (versionId: string) => {
    setApprovingBaselineId(versionId)
    setStatusMessage(null)
    try {
      const res = await apiClient.approveBaseline(versionId, 'Approved for production monitoring.')
      if (res.data) {
        setStatusMessage({ type: 'success', text: 'Baseline envelope approved and activated.' })
        await fetchAllData()
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Approval failed.' })
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Approval error.' })
    } finally {
      setApprovingBaselineId(null)
    }
  }

  const handleAcknowledgeAlert = async (alertId: string) => {
    setStatusMessage(null)
    try {
      const res = await apiClient.acknowledgeAlert(alertId, alertNotes || 'Alert acknowledged by maintenance engineer.')
      if (res.data) {
        setStatusMessage({ type: 'success', text: 'Alert acknowledged.' })
        setAcknowledgingAlertId(null)
        setAlertNotes('')
        await fetchAllData()
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Failed to acknowledge alert.' })
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Acknowledgment error.' })
    }
  }

  const handleUpdateAlertStatus = async (alertId: string, newStatus: any) => {
    setStatusMessage(null)
    try {
      const res = await apiClient.updateAlertStatus(alertId, newStatus, `Status transitioned to ${newStatus}`)
      if (res.data) {
        setStatusMessage({ type: 'success', text: `Alert marked as ${newStatus}.` })
        await fetchAllData()
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Status update error.' })
    }
  }

  if (loading && !condition) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="size-6 animate-spin text-[#1685ff]" />
          <p className="text-sm font-medium text-slate-500">Loading equipment condition and AI baselines...</p>
        </div>
      </div>
    )
  }

  const condState = condition?.condition_state || 'NORMAL'
  const isNormal = condState === 'NORMAL'
  const isAttention = condState === 'ATTENTION'
  const isCritical = condState === 'CRITICAL'
  const isDataIssue = condState === 'MONITORING_UNAVAILABLE' || condState === 'INSUFFICIENT_DATA'

  return (
    <div className="space-y-6">
      {/* Status Alert Banner if any */}
      {statusMessage && (
        <div
          className={`flex items-center justify-between rounded-lg p-3 text-sm font-medium ${
            statusMessage.type === 'success'
              ? 'border border-emerald-200 bg-emerald-50 text-emerald-800'
              : 'border border-rose-200 bg-rose-50 text-rose-800'
          }`}
        >
          <span>{statusMessage.text}</span>
          <button onClick={() => setStatusMessage(null)} className="text-xs underline hover:opacity-80">
            Dismiss
          </button>
        </div>
      )}

      {/* Header Actions */}
      <div className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">Equipment Condition & AI Anomaly Detection</h2>
            <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-[#1685ff]">
              Phase 5
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Multivariate Isolation Forest, statistical Z-score/MAD baseline envelopes, data quality verification, and operating context classification.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleEvaluateNow}
            disabled={evaluating}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-60"
          >
            <RefreshCw className={`size-3.5 ${evaluating ? 'animate-spin text-[#1685ff]' : ''}`} />
            <span>{evaluating ? 'Evaluating...' : 'Evaluate Now'}</span>
          </button>

          <button
            onClick={handleTrainML}
            disabled={trainingML}
            className="flex items-center gap-1.5 rounded-lg bg-[#1685ff] px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-600 disabled:opacity-60"
          >
            <Brain className="size-3.5" />
            <span>{trainingML ? 'Training...' : 'Train Isolation Forest'}</span>
          </button>

          <button
            onClick={handleBuildBaselines}
            disabled={buildingBaselines}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-100 disabled:opacity-60"
          >
            <Sliders className="size-3.5" />
            <span>{buildingBaselines ? 'Building...' : 'Build Baselines'}</span>
          </button>
        </div>
      </div>

      {/* 4 Condition Overview Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: Overall Condition State */}
        <div
          className={`rounded-xl border p-5 shadow-sm transition ${
            isCritical
              ? 'border-rose-300 bg-rose-50/50'
              : isAttention
              ? 'border-amber-300 bg-amber-50/50'
              : isDataIssue
              ? 'border-slate-300 bg-slate-50'
              : 'border-emerald-200 bg-emerald-50/40'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Condition State</span>
            {isCritical ? (
              <Flame className="size-5 text-rose-600" />
            ) : isAttention ? (
              <AlertTriangle className="size-5 text-amber-600" />
            ) : (
              <CheckCircle2 className="size-5 text-emerald-600" />
            )}
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span
              className={`text-2xl font-black ${
                isCritical
                  ? 'text-rose-700'
                  : isAttention
                  ? 'text-amber-700'
                  : isDataIssue
                  ? 'text-slate-700'
                  : 'text-emerald-700'
              }`}
            >
              {condState}
            </span>
          </div>
          <p className="mt-2 line-clamp-2 text-xs text-slate-600">
            {condition?.summary_reason || 'Operating within normal validated limits.'}
          </p>
        </div>

        {/* Card 2: Operating Context */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Operating Context</span>
            <Zap className="size-5 text-[#1685ff]" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900">{condition?.operating_state || 'UNKNOWN'}</span>
            <span className="text-xs font-bold text-slate-500">
              {Math.round((condition?.operating_confidence || 0) * 100)}% conf
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Determined by live speed, current, vibration, and temperature states.
          </p>
        </div>

        {/* Card 3: Data Quality Gate */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Data Quality</span>
            <ShieldAlert
              className={`size-5 ${
                condition?.data_quality_state === 'GOOD' ? 'text-emerald-500' : 'text-amber-500'
              }`}
            />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span
              className={`text-2xl font-black ${
                condition?.data_quality_state === 'GOOD' ? 'text-emerald-600' : 'text-amber-600'
              }`}
            >
              {condition?.data_quality_state || 'GOOD'}
            </span>
            <span className="text-xs text-slate-500">
              {condition?.data_quality_issues?.length || 0} issue(s)
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Sensor telemetry validated across 13 industrial data quality criteria.
          </p>
        </div>

        {/* Card 4: Anomaly & Alert Score */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Anomaly & Alerts</span>
            <BellRing className="size-5 text-indigo-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-black text-slate-900">
              {condition?.active_anomaly_count || 0}
            </span>
            <span className="text-xs text-slate-500">anomalies / {condition?.open_alerts_count || 0} open alerts</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Baselines: {condition?.baseline_coverage?.signals_with_active_baseline || 0}/
            {condition?.baseline_coverage?.total_signals || 0} signals covered.
          </p>
        </div>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200">
        <button
          onClick={() => setActiveSubView('anomalies')}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-bold transition ${
            activeSubView === 'anomalies'
              ? 'border-[#1685ff] text-[#1685ff]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Flame className="size-4" />
          <span>Active & Historical Anomalies ({anomalies.length})</span>
        </button>

        <button
          onClick={() => setActiveSubView('alerts')}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-bold transition ${
            activeSubView === 'alerts'
              ? 'border-[#1685ff] text-[#1685ff]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <BellRing className="size-4" />
          <span>Operational Alerts ({alerts.length})</span>
        </button>

        <button
          onClick={() => setActiveSubView('baselines')}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-bold transition ${
            activeSubView === 'baselines'
              ? 'border-[#1685ff] text-[#1685ff]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Sliders className="size-4" />
          <span>Equipment Baselines ({baselines.length})</span>
        </button>

        <button
          onClick={() => setActiveSubView('ml')}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-bold transition ${
            activeSubView === 'ml'
              ? 'border-[#1685ff] text-[#1685ff]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Brain className="size-4" />
          <span>ML Models (Isolation Forest)</span>
        </button>
      </div>

      {/* SUBVIEW 1: ANOMALIES FEED WITH EXPLAINABLE EVIDENCE */}
      {activeSubView === 'anomalies' && (
        <div className="space-y-4">
          {anomalies.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
              <CheckCircle2 className="size-10 text-emerald-500" />
              <h3 className="mt-3 text-base font-bold text-slate-800">No Anomalies Detected</h3>
              <p className="mt-1 max-w-md text-xs text-slate-500">
                All industrial telemetry signals are within normal baseline statistical envelopes and multivariate Isolation Forest scores are nominal.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="divide-y divide-slate-200">
                {anomalies.map((anom) => {
                  const isExpanded = expandedAnomalyId === anom.id
                  const isCrit = anom.severity === 'CRITICAL'
                  const isWarn = anom.severity === 'WARNING'

                  return (
                    <div key={anom.id} className="p-4 transition hover:bg-slate-50/60">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5">
                            {isCrit ? (
                              <div className="rounded-lg bg-rose-100 p-2 text-rose-600">
                                <Flame className="size-4" />
                              </div>
                            ) : isWarn ? (
                              <div className="rounded-lg bg-amber-100 p-2 text-amber-600">
                                <AlertTriangle className="size-4" />
                              </div>
                            ) : (
                              <div className="rounded-lg bg-blue-100 p-2 text-blue-600">
                                <Info className="size-4" />
                              </div>
                            )}
                          </div>

                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`rounded px-2 py-0.5 text-[11px] font-black uppercase ${
                                  isCrit
                                    ? 'bg-rose-100 text-rose-800'
                                    : isWarn
                                    ? 'bg-amber-100 text-amber-800'
                                    : 'bg-blue-100 text-blue-800'
                                }`}
                              >
                                {anom.severity}
                              </span>
                              <span className="text-xs font-semibold text-slate-800">{anom.detection_method}</span>
                              <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                                State: {anom.operating_state}
                              </span>
                              <span className="text-[11px] text-slate-400">
                                Count: {anom.occurrence_count}x
                              </span>
                            </div>

                            <p className="mt-1 text-sm font-medium text-slate-800">{anom.summary}</p>

                            <div className="mt-2 flex flex-wrap items-center gap-1.5">
                              <span className="text-[11px] font-medium text-slate-400">Affected Signals:</span>
                              {anom.affected_signals?.map((sig) => (
                                <span
                                  key={sig}
                                  className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold text-slate-700"
                                >
                                  {sig}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-4 sm:flex-col sm:items-end">
                          <div className="text-right">
                            <span className="block text-xs font-bold text-slate-700">
                              Score: {anom.anomaly_score.toFixed(3)}
                            </span>
                            <span className="text-[11px] text-slate-400">
                              {new Date(anom.latest_detected_at).toLocaleTimeString()}
                            </span>
                          </div>

                          <button
                            onClick={() => setExpandedAnomalyId(isExpanded ? null : anom.id)}
                            className="flex items-center gap-1 text-xs font-semibold text-[#1685ff] hover:underline"
                          >
                            <span>{isExpanded ? 'Hide Evidence' : 'View Evidence'}</span>
                            {isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
                          </button>
                        </div>
                      </div>

                      {/* Expandable Evidence Trail */}
                      {isExpanded && (
                        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                          <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                            Explainable Evidence & Measurement Deviations
                          </h4>
                          <p className="mt-0.5 text-xs text-slate-500">
                            Transparent audit trace detailing why this event was classified as anomalous.
                          </p>

                          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                            <div className="rounded border border-slate-200 bg-white p-3">
                              <span className="text-[10px] font-bold uppercase text-slate-400">Detection Method</span>
                              <p className="text-xs font-semibold text-slate-800">{anom.detection_method}</p>
                              <span className="mt-2 block text-[10px] font-bold uppercase text-slate-400">Operating Context</span>
                              <p className="text-xs text-slate-700">{anom.operating_state}</p>
                            </div>

                            <div className="rounded border border-slate-200 bg-white p-3">
                              <span className="text-[10px] font-bold uppercase text-slate-400">First Detected</span>
                              <p className="text-xs text-slate-700">{new Date(anom.first_detected_at).toLocaleString()}</p>
                              <span className="mt-2 block text-[10px] font-bold uppercase text-slate-400">Latest Occurrence</span>
                              <p className="text-xs text-slate-700">{new Date(anom.latest_detected_at).toLocaleString()}</p>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* SUBVIEW 2: OPERATIONAL ALERTS & ACKNOWLEDGMENT WORKFLOW */}
      {activeSubView === 'alerts' && (
        <div className="space-y-4">
          {alerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
              <CheckCircle className="size-10 text-emerald-500" />
              <h3 className="mt-3 text-base font-bold text-slate-800">No Open Operational Alerts</h3>
              <p className="mt-1 max-w-md text-xs text-slate-500">
                All previous alerts have been resolved or closed. Operational status is nominal.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="divide-y divide-slate-200">
                {alerts.map((alt) => {
                  const isOpen = alt.status === 'OPEN'
                  const isAck = alt.status === 'ACKNOWLEDGED'

                  return (
                    <div key={alt.id} className="p-4 transition hover:bg-slate-50/60">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={`rounded px-2 py-0.5 text-[10px] font-black uppercase ${
                                alt.severity === 'CRITICAL'
                                  ? 'bg-rose-100 text-rose-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {alt.severity}
                            </span>
                            <span
                              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                isOpen
                                  ? 'bg-red-50 text-red-700 border border-red-200'
                                  : isAck
                                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              }`}
                            >
                              {alt.status}
                            </span>
                            <span className="text-xs text-slate-400">
                              Detected: {new Date(alt.first_detected_at).toLocaleString()}
                            </span>
                          </div>

                          <p className="mt-2 text-sm font-semibold text-slate-800">
                            {alt.anomaly_summary || 'Operational deviation alert triggered by condition monitoring.'}
                          </p>

                          {alt.resolution_notes && (
                            <p className="mt-1 text-xs text-slate-500 bg-slate-50 p-2 rounded border border-slate-100">
                              {alt.resolution_notes}
                            </p>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          {isOpen && (
                            <button
                              onClick={() => setAcknowledgingAlertId(alt.id)}
                              className="rounded-lg bg-[#1685ff] px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-600"
                            >
                              Acknowledge
                            </button>
                          )}

                          {isAck && (
                            <button
                              onClick={() => handleUpdateAlertStatus(alt.id, 'RESOLVED')}
                              className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-700"
                            >
                              Mark Resolved
                            </button>
                          )}

                          <button
                            onClick={() => handleUpdateAlertStatus(alt.id, 'CLOSED')}
                            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                          >
                            Close
                          </button>
                        </div>
                      </div>

                      {/* Inline Acknowledgment Dialog */}
                      {acknowledgingAlertId === alt.id && (
                        <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50/50 p-3">
                          <label className="block text-xs font-bold text-slate-700">
                            Acknowledgment Notes / Actions Taken:
                          </label>
                          <textarea
                            value={alertNotes}
                            onChange={(e) => setAlertNotes(e.target.value)}
                            placeholder="Enter engineer inspection notes, actions initiated, or verification..."
                            className="mt-1 w-full rounded border border-slate-300 bg-white p-2 text-xs text-slate-800 placeholder-slate-400 focus:border-[#1685ff] focus:outline-none"
                            rows={2}
                          />
                          <div className="mt-2 flex justify-end gap-2">
                            <button
                              onClick={() => {
                                setAcknowledgingAlertId(null)
                                setAlertNotes('')
                              }}
                              className="rounded px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleAcknowledgeAlert(alt.id)}
                              className="rounded bg-[#1685ff] px-3 py-1 text-xs font-semibold text-white hover:bg-blue-600"
                            >
                              Confirm Acknowledgment
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* SUBVIEW 3: BASELINE OPERATING ENVELOPES */}
      {activeSubView === 'baselines' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-800">Signal Baseline Operating Envelopes</h3>
              <p className="text-xs text-slate-500">
                Statistical tolerance envelopes (Mean, Std, Median, MAD, p5–p95) per signal during verified operating states.
              </p>
            </div>
            <button
              onClick={handleBuildBaselines}
              disabled={buildingBaselines}
              className="rounded-lg bg-[#1685ff] px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-600 disabled:opacity-60"
            >
              {buildingBaselines ? 'Rebuilding...' : 'Compute Candidate Baselines'}
            </button>
          </div>

          {baselines.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-12 text-center shadow-sm">
              <Sliders className="size-10 text-slate-400" />
              <h3 className="mt-3 text-base font-bold text-slate-800">No Baselines Established</h3>
              <p className="mt-1 max-w-md text-xs text-slate-500">
                Click &quot;Compute Candidate Baselines&quot; to calculate normal statistical profiles from verified clean historical telemetry.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {baselines.map((prof) => {
                const ver = prof.active_version
                const stats = ver?.statistics
                const isCandidate = prof.lifecycle_status === 'CANDIDATE'

                return (
                  <div key={prof.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold text-slate-900">{prof.name}</h4>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          prof.lifecycle_status === 'ACTIVE'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {prof.lifecycle_status}
                      </span>
                    </div>

                    <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-500">
                      <span>State: {prof.operating_state}</span>
                      <span>•</span>
                      <span>v{prof.active_version_number || 1}</span>
                    </div>

                    {stats ? (
                      <div className="mt-3 grid grid-cols-2 gap-2 rounded-lg bg-slate-50 p-2 text-xs">
                        <div>
                          <span className="text-[10px] text-slate-400 uppercase">Mean / Median</span>
                          <p className="font-semibold text-slate-800">
                            {stats.mean?.toFixed(2)} / {stats.median?.toFixed(2)}
                          </p>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-400 uppercase">Std / MAD</span>
                          <p className="font-semibold text-slate-800">
                            {stats.std?.toFixed(2)} / {stats.mad?.toFixed(2)}
                          </p>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-400 uppercase">Min / Max</span>
                          <p className="font-semibold text-slate-800">
                            {stats.min?.toFixed(2)} - {stats.max?.toFixed(2)}
                          </p>
                        </div>
                        <div>
                          <span className="text-[10px] text-slate-400 uppercase">p5 - p95 Envelope</span>
                          <p className="font-semibold text-slate-800">
                            {stats.p5?.toFixed(2)} - {stats.p95?.toFixed(2)}
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="mt-3 rounded-lg bg-slate-50 p-3 text-center text-xs text-slate-400">
                        No active envelope version calculated.
                      </div>
                    )}

                    {isCandidate && ver && (
                      <button
                        onClick={() => handleApproveBaseline(ver.id)}
                        disabled={approvingBaselineId === ver.id}
                        className="mt-3 w-full rounded-lg bg-emerald-600 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                      >
                        {approvingBaselineId === ver.id ? 'Approving...' : 'Approve Envelope'}
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* SUBVIEW 4: ML MODEL REGISTRY (ISOLATION FOREST) */}
      {activeSubView === 'ml' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Multivariate Isolation Forest Registry</h3>
                <p className="text-xs text-slate-500">
                  Unsupervised machine learning model detecting subtle multivariate anomalies across interrelated signals.
                </p>
              </div>

              <button
                onClick={handleTrainML}
                disabled={trainingML}
                className="rounded-lg bg-[#1685ff] px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-600 disabled:opacity-60"
              >
                {trainingML ? 'Training...' : 'Retrain Isolation Forest'}
              </button>
            </div>

            {mlModels?.registry ? (
              <div className="mt-4 space-y-3">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 rounded-lg bg-slate-50 p-3 text-xs">
                  <div>
                    <span className="text-[10px] font-bold uppercase text-slate-400">Model Name</span>
                    <p className="font-bold text-slate-800">{mlModels.registry.name}</p>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold uppercase text-slate-400">Lifecycle Status</span>
                    <p className="font-bold text-emerald-600">{mlModels.registry.lifecycle_status}</p>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold uppercase text-slate-400">Active Version</span>
                    <p className="font-bold text-slate-800">v{mlModels.registry.active_version_number}</p>
                  </div>
                </div>

                <h4 className="text-xs font-bold text-slate-700 mt-4">Model Versions</h4>
                <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
                  {mlModels.versions?.map((v) => (
                    <div key={v.id} className="p-3 text-xs flex items-center justify-between">
                      <div>
                        <span className="font-bold text-slate-800">Version {v.version_number}</span>
                        <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">
                          {v.training_sample_count} training samples
                        </span>
                        <p className="text-[11px] text-slate-400 mt-0.5">
                          Trained: {new Date(v.created_at).toLocaleString()}
                        </p>
                      </div>
                      <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-bold text-emerald-800">
                        {v.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-lg bg-slate-50 p-8 text-center">
                <Brain className="mx-auto size-8 text-slate-400" />
                <p className="mt-2 text-xs font-medium text-slate-600">
                  No Isolation Forest model has been trained for this machine yet.
                </p>
                <button
                  onClick={handleTrainML}
                  disabled={trainingML}
                  className="mt-3 rounded-lg bg-[#1685ff] px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-600"
                >
                  Train Initial Model
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

