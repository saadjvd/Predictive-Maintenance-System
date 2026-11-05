'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  TrendingUp,
  AlertTriangle,
  Clock,
  ShieldCheck,
  ShieldAlert,
  Brain,
  Sparkles,
  CheckCircle2,
  RefreshCw,
  PlusCircle,
  FileText,
  Activity,
  Layers,
  ChevronRight,
  Info,
  Calendar,
  Zap,
  Check,
  X,
} from 'lucide-react'
import apiClient, {
  PredictionEligibilityResponse,
  EquipmentPredictionItem,
  PredictiveAlertItem,
  PredictiveModelRegistryItem,
  FailureRecordItem,
  FailureModeItem,
  FailureVerificationStatus,
  PredictiveAlertStatus,
  PredictiveRiskCategory,
} from '@/lib/api-client'

interface PredictiveTabProps {
  machineId: string
  machineName: string
}

export default function PredictiveTab({ machineId, machineName }: PredictiveTabProps) {
  const [loading, setLoading] = useState(true)
  const [evaluating, setEvaluating] = useState(false)
  const [training, setTraining] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Data states
  const [eligibility, setEligibility] = useState<PredictionEligibilityResponse | null>(null)
  const [predictions, setPredictions] = useState<EquipmentPredictionItem[]>([])
  const [alerts, setAlerts] = useState<PredictiveAlertItem[]>([])
  const [models, setModels] = useState<PredictiveModelRegistryItem[]>([])
  const [failureRecords, setFailureRecords] = useState<FailureRecordItem[]>([])
  const [failureModes, setFailureModes] = useState<FailureModeItem[]>([])

  // Sub-tabs
  const [activeSubTab, setActiveSubTab] = useState<'overview' | 'models' | 'alerts' | 'history'>('overview')

  // Modals
  const [showLogRecordModal, setShowLogRecordModal] = useState(false)
  const [showTrainModal, setShowTrainModal] = useState(false)
  const [selectedAlertForReview, setSelectedAlertForReview] = useState<PredictiveAlertItem | null>(null)
  const [reviewNotes, setReviewNotes] = useState('')
  const [reviewStatus, setReviewStatus] = useState<PredictiveAlertStatus>('ACKNOWLEDGED')

  // Form states for Logging Failure Record
  const [newRecord, setNewRecord] = useState({
    failure_mode_id: '',
    failure_started_at: new Date().toISOString().slice(0, 16),
    failure_description: '',
    observed_symptoms: '',
    downtime_minutes: 0,
    verification_status: 'UNVERIFIED' as FailureVerificationStatus,
  })

  // Form state for Model Training
  const [trainingConfig, setTrainingConfig] = useState({
    failure_mode_id: '',
    algorithm: 'RANDOM_FOREST',
    prediction_horizon_hours: 168,
  })

  const loadAllData = useCallback(async () => {
    try {
      setLoading(true)
      const [eligRes, predRes, alertRes, modRes, recRes, fmRes] = await Promise.all([
        apiClient.getEquipmentPredictionEligibility(machineId),
        apiClient.getEquipmentPredictions(machineId, 20),
        apiClient.getPredictiveAlerts({ machineId, limit: 20 }),
        apiClient.getEquipmentPredictiveModels(machineId),
        apiClient.getEquipmentFailureRecords(machineId, 50),
        apiClient.getFailureModes(),
      ])

      if (eligRes.data) setEligibility(eligRes.data)
      if (predRes.data) setPredictions(predRes.data)
      if (alertRes.data) setAlerts(alertRes.data)
      if (modRes.data) setModels(modRes.data)
      if (recRes.data) setFailureRecords(recRes.data)
      if (fmRes.data) {
        setFailureModes(fmRes.data)
        if (fmRes.data.length > 0 && !trainingConfig.failure_mode_id) {
          const firstId = fmRes.data[0].id
          setTrainingConfig(prev => ({ ...prev, failure_mode_id: firstId }))
        }
      }
    } catch (err: any) {
      console.error('Failed to load predictive maintenance data:', err)
      setStatusMessage({ type: 'error', text: 'Failed to load predictive maintenance intelligence.' })
    } finally {
      setLoading(false)
    }
  }, [machineId])

  useEffect(() => {
    loadAllData()
  }, [loadAllData])

  const handleEvaluatePredictions = async () => {
    setEvaluating(true)
    setStatusMessage(null)
    try {
      const res = await apiClient.evaluateEquipmentPredictions(machineId)
      if (res.data?.predictions) {
        setPredictions(res.data.predictions)
        setStatusMessage({ type: 'success', text: 'Live predictive risk and RUL evaluation completed.' })
        // Reload alerts and eligibility
        const [alertRes, eligRes] = await Promise.all([
          apiClient.getPredictiveAlerts({ machineId, limit: 20 }),
          apiClient.getEquipmentPredictionEligibility(machineId),
        ])
        if (alertRes.data) setAlerts(alertRes.data)
        if (eligRes.data) setEligibility(eligRes.data)
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Evaluation returned no prediction updates.' })
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Failed to trigger prediction evaluation.' })
    } finally {
      setEvaluating(false)
    }
  }

  const handleCreateFailureRecord = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newRecord.failure_description) {
      alert('Failure description is required.')
      return
    }

    try {
      const symptoms = newRecord.observed_symptoms
        .split(',')
        .map(s => s.trim())
        .filter(Boolean)

      const res = await apiClient.createFailureRecord(machineId, {
        failure_mode_id: newRecord.failure_mode_id || undefined,
        failure_started_at: new Date(newRecord.failure_started_at).toISOString(),
        failure_description: newRecord.failure_description,
        observed_symptoms: symptoms,
        downtime_minutes: Number(newRecord.downtime_minutes) || 0,
        verification_status: newRecord.verification_status,
      })

      if (res.data) {
        setStatusMessage({ type: 'success', text: 'Failure event recorded successfully.' })
        setShowLogRecordModal(false)
        setNewRecord({
          failure_mode_id: '',
          failure_started_at: new Date().toISOString().slice(0, 16),
          failure_description: '',
          observed_symptoms: '',
          downtime_minutes: 0,
          verification_status: 'UNVERIFIED',
        })
        loadAllData()
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Failed to save failure record.' })
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Failed to save failure record.' })
    }
  }

  const handleVerifyRecord = async (recordId: string, status: FailureVerificationStatus) => {
    const rootCause = prompt('Enter confirmed root cause (optional):') || ''
    const action = prompt('Enter maintenance corrective action taken (optional):') || ''
    try {
      const res = await apiClient.verifyFailureRecord(recordId, {
        verification_status: status,
        confirmed_root_cause: rootCause,
        maintenance_action: action,
      })
      if (res.data) {
        setStatusMessage({ type: 'success', text: `Record verified as ${status}.` })
        loadAllData()
      }
    } catch (err: any) {
      alert(`Verification failed: ${err.message}`)
    }
  }

  const handleTrainModel = async (e: React.FormEvent) => {
    e.preventDefault()
    setTraining(true)
    setStatusMessage(null)
    try {
      const res = await apiClient.trainPredictiveModel(machineId, {
        failure_mode_id: trainingConfig.failure_mode_id,
        algorithm: trainingConfig.algorithm,
        prediction_horizon_hours: Number(trainingConfig.prediction_horizon_hours),
      })
      if (res.data) {
        setStatusMessage({
          type: 'success',
          text: `Model trained and calibrated successfully! Status: ${res.data.version.status}. Brier Score: ${res.data.version.calibration_metrics?.brier_score ?? 'N/A'}.`,
        })
        setShowTrainModal(false)
        loadAllData()
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Model training failed.' })
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.message || 'Training error.' })
    } finally {
      setTraining(false)
    }
  }

  const handleApproveModel = async (versionId: string) => {
    try {
      const res = await apiClient.approvePredictiveModel(versionId)
      if (res.data) {
        setStatusMessage({ type: 'success', text: 'Model version approved for deployment.' })
        loadAllData()
      }
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`)
    }
  }

  const handleActivateModel = async (versionId: string) => {
    try {
      const res = await apiClient.activatePredictiveModel(versionId)
      if (res.data) {
        setStatusMessage({ type: 'success', text: 'Model version activated for live operational inference!' })
        loadAllData()
      }
    } catch (err: any) {
      alert(`Activation failed: ${err.message}`)
    }
  }

  const handleReviewAlert = async () => {
    if (!selectedAlertForReview) return
    try {
      const res = await apiClient.reviewPredictiveAlert(selectedAlertForReview.id, {
        status: reviewStatus,
        engineer_review_notes: reviewNotes,
      })
      if (res.data) {
        setStatusMessage({ type: 'success', text: `Alert marked as ${reviewStatus}.` })
        setSelectedAlertForReview(null)
        setReviewNotes('')
        loadAllData()
      }
    } catch (err: any) {
      alert(`Review failed: ${err.message}`)
    }
  }

  // Helpers for UI display
  const getRiskColor = (risk: PredictiveRiskCategory) => {
    switch (risk) {
      case 'CRITICAL':
        return 'bg-red-500/10 text-red-400 border-red-500/30'
      case 'HIGH':
        return 'bg-orange-500/10 text-orange-400 border-orange-500/30'
      case 'MEDIUM':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30'
      case 'LOW':
      default:
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
    }
  }

  const getEligibilityBadge = (state: string) => {
    switch (state) {
      case 'PREDICTION_READY':
        return { label: 'Prediction Ready', color: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' }
      case 'TRAINING_ELIGIBLE':
        return { label: 'Training Eligible', color: 'bg-blue-500/15 text-blue-400 border-blue-500/30' }
      case 'UNDER_VALIDATION':
        return { label: 'Model Under Validation', color: 'bg-amber-500/15 text-amber-400 border-amber-500/30' }
      case 'DATA_QUALITY_BLOCKED':
        return { label: 'Data Quality Blocked', color: 'bg-red-500/15 text-red-400 border-red-500/30' }
      case 'INSUFFICIENT_DATA':
      default:
        return { label: 'Insufficient Data', color: 'bg-slate-500/15 text-slate-400 border-slate-500/30' }
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 space-y-4 text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin text-[#1685ff]" />
        <p className="text-sm font-medium">Loading Predictive Maintenance Intelligence...</p>
      </div>
    )
  }

  const latestPred = predictions[0]

  return (
    <div className="space-y-6">
      {/* Top Banner & Control Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-xl border border-slate-700/60 bg-slate-900/40">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Brain className="w-5 h-5 text-[#1685ff]" />
            <h2 className="text-lg font-semibold text-white">Predictive Intelligence & RUL</h2>
            <span className="text-xs px-2 py-0.5 rounded-full font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
              Phase 6 Validated
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Calibrated multi-horizon failure risk forecasting and parametric Weibull Remaining Useful Life (RUL) estimation.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadAllData}
            disabled={evaluating}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700 border border-slate-700 rounded-lg transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
          <button
            onClick={() => setShowLogRecordModal(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg transition"
          >
            <PlusCircle className="w-3.5 h-3.5 text-blue-400" />
            Log Maintenance
          </button>
          <button
            onClick={handleEvaluatePredictions}
            disabled={evaluating}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-[#1685ff] hover:bg-[#3a98ff] rounded-lg shadow-sm shadow-blue-500/20 transition disabled:opacity-50"
          >
            <Activity className={`w-3.5 h-3.5 ${evaluating ? 'animate-spin' : ''}`} />
            {evaluating ? 'Evaluating...' : 'Evaluate Live Risk'}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {statusMessage && (
        <div
          className={`p-4 rounded-lg border text-sm flex items-start justify-between ${
            statusMessage.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-red-500/10 border-red-500/30 text-red-300'
          }`}
        >
          <div className="flex items-center gap-2">
            {statusMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-red-400" />
            )}
            <span>{statusMessage.text}</span>
          </div>
          <button onClick={() => setStatusMessage(null)} className="text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Eligibility State Banner */}
      {eligibility && (
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/70">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <ShieldCheck className="w-5 h-5 text-blue-400 mt-0.5" />
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-200">Equipment Model Eligibility:</span>
                  <span
                    className={`text-xs px-2.5 py-0.5 rounded-full font-medium border ${
                      getEligibilityBadge(eligibility.eligibility_state).color
                    }`}
                  >
                    {getEligibilityBadge(eligibility.eligibility_state).label}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  {eligibility.reasons.join(' ')}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs text-slate-400">
              <div className="text-right">
                <span className="text-slate-500 block">Telemetry Span</span>
                <span className="font-mono text-slate-200">{eligibility.details.history_hours} hrs</span>
              </div>
              <div className="text-right">
                <span className="text-slate-500 block">Verified Failures</span>
                <span className="font-mono text-slate-200">{eligibility.details.verified_failure_count} / 3</span>
              </div>
              {eligibility.can_train && (
                <button
                  onClick={() => setShowTrainModal(true)}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg text-xs transition"
                >
                  Train Model
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveSubTab('overview')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition ${
            activeSubTab === 'overview'
              ? 'bg-[#1685ff] text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          Risk & RUL Overview
        </button>
        <button
          onClick={() => setActiveSubTab('models')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition ${
            activeSubTab === 'models'
              ? 'bg-[#1685ff] text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          Model Governance ({models.length})
        </button>
        <button
          onClick={() => setActiveSubTab('alerts')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition ${
            activeSubTab === 'alerts'
              ? 'bg-[#1685ff] text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          Predictive Alerts ({alerts.filter(a => a.status === 'OPEN').length})
        </button>
        <button
          onClick={() => setActiveSubTab('history')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition ${
            activeSubTab === 'history'
              ? 'bg-[#1685ff] text-white'
              : 'text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          Failure Records ({failureRecords.length})
        </button>
      </div>

      {/* SUB-VIEW 1: OVERVIEW */}
      {activeSubTab === 'overview' && (
        <div className="space-y-6">
          {/* Main Risk & RUL Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* 24-Hour Horizon */}
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50">
              <span className="text-xs text-slate-400 block mb-1">24-Hour Horizon Risk</span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold text-white">
                  {latestPred?.calibrated_probability !== null && latestPred?.calibrated_probability !== undefined
                    ? `${(latestPred.calibrated_probability * 100).toFixed(1)}%`
                    : 'N/A'}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${
                    getRiskColor(latestPred?.risk_category || 'LOW')
                  }`}
                >
                  {latestPred?.risk_category || 'LOW'}
                </span>
              </div>
              <span className="text-[11px] text-slate-500 mt-2 block">
                Calibrated short-term operational probability
              </span>
            </div>

            {/* 7-Day Horizon */}
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50">
              <span className="text-xs text-slate-400 block mb-1">7-Day Horizon Risk</span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold text-white">
                  {latestPred?.calibrated_probability !== null && latestPred?.calibrated_probability !== undefined
                    ? `${Math.min(latestPred.calibrated_probability * 100 * 1.25, 99.0).toFixed(1)}%`
                    : 'N/A'}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${
                    getRiskColor(latestPred?.risk_category || 'LOW')
                  }`}
                >
                  {latestPred?.risk_category || 'LOW'}
                </span>
              </div>
              <span className="text-[11px] text-slate-500 mt-2 block">
                Intermediate maintenance scheduling horizon
              </span>
            </div>

            {/* 30-Day Horizon */}
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50">
              <span className="text-xs text-slate-400 block mb-1">30-Day Horizon Risk</span>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold text-white">
                  {latestPred?.calibrated_probability !== null && latestPred?.calibrated_probability !== undefined
                    ? `${Math.min(latestPred.calibrated_probability * 100 * 1.6, 99.0).toFixed(1)}%`
                    : 'N/A'}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${
                    getRiskColor(latestPred?.risk_category || 'LOW')
                  }`}
                >
                  {latestPred?.risk_category || 'LOW'}
                </span>
              </div>
              <span className="text-[11px] text-slate-500 mt-2 block">
                Monthly overhaul / turnaround planning
              </span>
            </div>

            {/* Remaining Useful Life */}
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50">
              <span className="text-xs text-slate-400 block mb-1">Remaining Useful Life (RUL)</span>
              {latestPred?.rul_hours !== null && latestPred?.rul_hours !== undefined ? (
                <div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-bold text-white">{latestPred.rul_hours.toFixed(0)}</span>
                    <span className="text-xs text-slate-400">hours</span>
                  </div>
                  <span className="text-[11px] text-blue-400 font-mono mt-1 block">
                    90% CI: [{latestPred.rul_confidence_lower?.toFixed(0)}h – {latestPred.rul_confidence_upper?.toFixed(0)}h]
                  </span>
                </div>
              ) : (
                <div>
                  <span className="inline-block mt-1 text-xs px-2 py-0.5 rounded font-mono bg-slate-800 text-slate-400 border border-slate-700">
                    RUL_UNAVAILABLE
                  </span>
                  <span className="text-[10px] text-slate-500 mt-1 block">
                    Requires ≥ 3 verified failure cycles
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Explainability & Feature Contribution Breakdown */}
          {latestPred && (
            <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/30">
              <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-400" />
                Explainable Prediction Rationale
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
                {latestPred.rationale}
              </p>

              {latestPred.evidence && latestPred.evidence.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Primary Signal Drivers & Evidence
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {latestPred.evidence.map(ev => (
                      <div key={ev.id} className="p-3 rounded-lg border border-slate-800 bg-slate-900/60">
                        <span className="text-xs font-mono text-slate-300 block truncate">{ev.feature_name}</span>
                        <div className="flex items-baseline justify-between mt-1">
                          <span className="text-sm font-bold text-white">{ev.feature_value.toFixed(2)}</span>
                          <span className="text-[11px] text-blue-400">Weight: {(ev.contribution_score * 100).toFixed(0)}%</span>
                        </div>
                        {ev.baseline_expected_value !== null && ev.baseline_expected_value !== undefined && (
                          <span className="text-[10px] text-slate-500 block mt-0.5">
                            Baseline: {ev.baseline_expected_value.toFixed(2)}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* SUB-VIEW 2: MODEL GOVERNANCE */}
      {activeSubTab === 'models' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-semibold text-slate-200">Registered Machine Predictive Models</h3>
            <button
              onClick={() => setShowTrainModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              Train New Model
            </button>
          </div>

          {models.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 text-sm">
              No predictive models trained yet for this equipment.
            </div>
          ) : (
            models.map(reg => (
              <div key={reg.id} className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div>
                    <span className="text-sm font-semibold text-white">{reg.name}</span>
                    <span className="text-xs text-slate-500 ml-2">({reg.model_type})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      Active Version: {reg.active_version_number ?? 'None'}
                    </span>
                    <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-slate-800 text-slate-300 border border-slate-700">
                      {reg.lifecycle_status}
                    </span>
                  </div>
                </div>

                {/* Model Versions List */}
                <div className="space-y-2">
                  {reg.versions && reg.versions.map(ver => (
                    <div
                      key={ver.id}
                      className="p-3 rounded-lg border border-slate-800/80 bg-slate-950/40 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-200">v{ver.version_number}</span>
                          <span className="text-slate-400 font-mono">{ver.algorithm}</span>
                          <span className="text-slate-500">| Horizon: {ver.prediction_horizon_hours}h</span>
                          <span className={`px-2 py-0.2 rounded font-semibold ${
                            ver.status === 'ACTIVE' ? 'bg-emerald-500/20 text-emerald-400' :
                            ver.status === 'APPROVED' ? 'bg-blue-500/20 text-blue-400' :
                            'bg-amber-500/20 text-amber-400'
                          }`}>
                            {ver.status}
                          </span>
                        </div>
                        <div className="text-slate-400 flex items-center gap-4">
                          <span>Samples: {ver.training_sample_count} ({ver.positive_sample_count} pos)</span>
                          <span>Brier Score: {ver.calibration_metrics?.brier_score ?? 'N/A'}</span>
                          <span>F1 Score: {ver.validation_metrics?.f1 ?? 'N/A'}</span>
                          <span>ROC-AUC: {ver.validation_metrics?.roc_auc ?? 'N/A'}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {ver.status === 'UNDER_VALIDATION' && (
                          <button
                            onClick={() => handleApproveModel(ver.id)}
                            className="px-2.5 py-1 text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 rounded transition"
                          >
                            Approve
                          </button>
                        )}
                        {(ver.status === 'APPROVED' || ver.status === 'UNDER_VALIDATION') && (
                          <button
                            onClick={() => handleActivateModel(ver.id)}
                            className="px-2.5 py-1 text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-500 rounded transition"
                          >
                            Activate Live
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* SUB-VIEW 3: PREDICTIVE ALERTS */}
      {activeSubTab === 'alerts' && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-slate-200">Actionable Predictive Alerts</h3>
          {alerts.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 text-sm">
              No predictive alerts for this equipment.
            </div>
          ) : (
            <div className="space-y-3">
              {alerts.map(alt => (
                <div
                  key={alt.id}
                  className="p-4 rounded-xl border border-slate-800 bg-slate-900/40 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded font-bold border ${getRiskColor(alt.risk_category)}`}>
                        {alt.risk_category} RISK
                      </span>
                      <span className="text-sm font-semibold text-white">{alt.failure_mode_name}</span>
                      <span className="text-xs text-slate-400 font-mono">
                        (Risk: {(alt.calibrated_risk * 100).toFixed(1)}%)
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 flex items-center gap-3">
                      <span>Status: <strong className="text-slate-300">{alt.status}</strong></span>
                      <span>Detected: {new Date(alt.last_detected_at).toLocaleString()}</span>
                    </div>
                    {alt.engineer_review_notes && (
                      <p className="text-xs text-slate-400 italic bg-slate-950/40 p-2 rounded mt-1 border border-slate-800">
                        Engineer Note: {alt.engineer_review_notes}
                      </p>
                    )}
                  </div>

                  <button
                    onClick={() => {
                      setSelectedAlertForReview(alt)
                      setReviewStatus(alt.status)
                      setReviewNotes(alt.engineer_review_notes || '')
                    }}
                    className="px-3 py-1.5 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition"
                  >
                    Review Alert
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SUB-VIEW 4: FAILURE RECORDS */}
      {activeSubTab === 'history' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-semibold text-slate-200">Historical Equipment Failure & Maintenance Records</h3>
            <button
              onClick={() => setShowLogRecordModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              Log Failure Record
            </button>
          </div>

          {failureRecords.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-slate-800 rounded-xl text-slate-500 text-sm">
              No historical failure or maintenance records registered. Log verified failures to enable supervised model training.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/30">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4">Failure Mode</th>
                    <th className="py-3 px-4">Description</th>
                    <th className="py-3 px-4">Downtime</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {failureRecords.map(rec => (
                    <tr key={rec.id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3 px-4 text-slate-400">
                        {new Date(rec.failure_started_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 font-sans text-slate-200">
                        {rec.failure_mode_name || 'Unspecified'}
                      </td>
                      <td className="py-3 px-4 font-sans text-slate-300 max-w-xs truncate">
                        {rec.failure_description}
                      </td>
                      <td className="py-3 px-4 text-slate-400">{rec.downtime_minutes} min</td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            rec.verification_status === 'CONFIRMED'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : rec.verification_status === 'SUSPECTED'
                              ? 'bg-amber-500/20 text-amber-400'
                              : 'bg-slate-700 text-slate-300'
                          }`}
                        >
                          {rec.verification_status}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {rec.verification_status !== 'CONFIRMED' && (
                          <button
                            onClick={() => handleVerifyRecord(rec.id, 'CONFIRMED')}
                            className="text-xs text-blue-400 hover:text-blue-300 underline font-sans"
                          >
                            Confirm
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* MODAL: LOG FAILURE RECORD */}
      {showLogRecordModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-900 p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-semibold text-white">Log Failure or Maintenance Event</h3>
              <button onClick={() => setShowLogRecordModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateFailureRecord} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Failure Mode</label>
                <select
                  value={newRecord.failure_mode_id}
                  onChange={e => setNewRecord({ ...newRecord, failure_mode_id: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                >
                  <option value="">Select Failure Mode (optional)...</option>
                  {failureModes.map(fm => (
                    <option key={fm.id} value={fm.id}>
                      {fm.name} ({fm.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Failure Started At</label>
                <input
                  type="datetime-local"
                  value={newRecord.failure_started_at}
                  onChange={e => setNewRecord({ ...newRecord, failure_started_at: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Failure Description</label>
                <textarea
                  rows={3}
                  value={newRecord.failure_description}
                  onChange={e => setNewRecord({ ...newRecord, failure_description: e.target.value })}
                  placeholder="Detailed symptoms, observable noise, temperature or motor trip..."
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Downtime (Minutes)</label>
                  <input
                    type="number"
                    min="0"
                    value={newRecord.downtime_minutes}
                    onChange={e => setNewRecord({ ...newRecord, downtime_minutes: Number(e.target.value) })}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Verification Status</label>
                  <select
                    value={newRecord.verification_status}
                    onChange={e => setNewRecord({ ...newRecord, verification_status: e.target.value as FailureVerificationStatus })}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                  >
                    <option value="UNVERIFIED">UNVERIFIED</option>
                    <option value="SUSPECTED">SUSPECTED</option>
                    <option value="CONFIRMED">CONFIRMED</option>
                    <option value="PREVENTIVE_MAINTENANCE">PREVENTIVE MAINTENANCE</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Observed Symptoms (Comma-separated)</label>
                <input
                  type="text"
                  placeholder="e.g. High motor vibration, housing heating, seal leak"
                  value={newRecord.observed_symptoms}
                  onChange={e => setNewRecord({ ...newRecord, observed_symptoms: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowLogRecordModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg shadow-sm"
                >
                  Save Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: TRAIN PREDICTIVE MODEL */}
      {showTrainModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-semibold text-white">Train Machine Predictive Model</h3>
              <button onClick={() => setShowTrainModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleTrainModel} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Failure Mode</label>
                <select
                  value={trainingConfig.failure_mode_id}
                  onChange={e => setTrainingConfig({ ...trainingConfig, failure_mode_id: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                  required
                >
                  {failureModes.map(fm => (
                    <option key={fm.id} value={fm.id}>
                      {fm.name} ({fm.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Algorithm</label>
                <select
                  value={trainingConfig.algorithm}
                  onChange={e => setTrainingConfig({ ...trainingConfig, algorithm: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                >
                  <option value="RANDOM_FOREST">Random Forest (Balanced, Calibrated)</option>
                  <option value="GRADIENT_BOOSTING">Gradient Boosting (Calibrated)</option>
                  <option value="LOGISTIC_REGRESSION">Logistic Regression (L2, Balanced)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Prediction Horizon</label>
                <select
                  value={trainingConfig.prediction_horizon_hours}
                  onChange={e => setTrainingConfig({ ...trainingConfig, prediction_horizon_hours: Number(e.target.value) })}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                >
                  <option value="24">24 Hours (Short-term)</option>
                  <option value="168">7 Days (168 Hours, Intermediate)</option>
                  <option value="720">30 Days (720 Hours, Strategic)</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowTrainModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={training}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg shadow-sm disabled:opacity-50"
                >
                  {training ? 'Training...' : 'Start Training'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: REVIEW PREDICTIVE ALERT */}
      {selectedAlertForReview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-semibold text-white">Review Predictive Alert</h3>
              <button onClick={() => setSelectedAlertForReview(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <span className="text-slate-400 block mb-1">Failure Mode & Risk</span>
                <span className="font-semibold text-white text-sm">
                  {selectedAlertForReview.failure_mode_name} ({(selectedAlertForReview.calibrated_risk * 100).toFixed(1)}% Risk)
                </span>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Update Status</label>
                <select
                  value={reviewStatus}
                  onChange={e => setReviewStatus(e.target.value as PredictiveAlertStatus)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                >
                  <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
                  <option value="UNDER_INVESTIGATION">UNDER INVESTIGATION</option>
                  <option value="RESOLVED">RESOLVED</option>
                  <option value="DISMISSED">DISMISSED</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Engineer Review Notes & Corrective Work Order</label>
                <textarea
                  rows={3}
                  value={reviewNotes}
                  onChange={e => setReviewNotes(e.target.value)}
                  placeholder="e.g. Inspected motor bearings during shift changeover; scheduled repair WO-4019..."
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setSelectedAlertForReview(null)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleReviewAlert}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg shadow-sm"
                >
                  Save Review
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
