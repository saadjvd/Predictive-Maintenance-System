'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  Bot,
  Brain,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  Search,
  Sparkles,
  RefreshCw,
  Plus,
  Play,
  Lock,
  Wrench,
  Check,
  X,
  ExternalLink,
  Info,
  ChevronRight,
  Database,
  Layers,
  FileCheck,
  Activity,
  TrendingUp,
} from 'lucide-react'
import apiClient, {
  DiagnosticSessionItem,
  AgentExecutionItem,
  MaintenanceRecommendationItem,
  DiagnosticReportItem,
  KnowledgeDocumentItem,
  RetrievedChunkItem,
} from '@/lib/api-client'

interface AiDiagnosticsTabProps {
  machineId: string
  machineName: string
}

export default function AiDiagnosticsTab({ machineId, machineName }: AiDiagnosticsTabProps) {
  const [loading, setLoading] = useState(true)
  const [runningDiagnostic, setRunningDiagnostic] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Data states
  const [sessions, setSessions] = useState<DiagnosticSessionItem[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [executions, setExecutions] = useState<AgentExecutionItem[]>([])
  const [recommendations, setRecommendations] = useState<MaintenanceRecommendationItem[]>([])
  const [report, setReport] = useState<DiagnosticReportItem | null>(null)
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDocumentItem[]>([])

  // Sub-tabs
  const [activeSubTab, setActiveSubTab] = useState<'investigation' | 'recommendations' | 'report' | 'knowledge'>('investigation')

  // Modals
  const [showApproveModal, setShowApproveModal] = useState<MaintenanceRecommendationItem | null>(null)
  const [approveNotes, setApproveNotes] = useState('')
  const [assignedTech, setAssignedTech] = useState('')
  const [scheduledDate, setScheduledDate] = useState('')
  const [approving, setApproving] = useState(false)

  const [showRejectModal, setShowRejectModal] = useState<MaintenanceRecommendationItem | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [rejectNotes, setRejectNotes] = useState('')
  const [rejecting, setRejecting] = useState(false)

  // RAG Search Test Modal
  const [showRagModal, setShowRagModal] = useState(false)
  const [ragQuery, setRagQuery] = useState('')
  const [ragResults, setRagResults] = useState<RetrievedChunkItem[]>([])
  const [ragSearching, setRagSearching] = useState(false)

  // Load diagnostic sessions
  const loadSessions = useCallback(async () => {
    try {
      const res = await apiClient.listDiagnosticSessions({ machine_id: machineId, limit: 20 })
      if (res.data) {
        setSessions(res.data)
        if (res.data.length > 0 && !selectedSessionId) {
          setSelectedSessionId(res.data[0].id)
        }
      }
    } catch (err) {
      console.error('Failed to load diagnostic sessions:', err)
    }
  }, [machineId, selectedSessionId])

  // Load session details
  const loadSessionDetails = useCallback(async (sessionId: string) => {
    try {
      setLoading(true)
      const res = await apiClient.getDiagnosticSession(sessionId)
      if (res.data) {
        setExecutions(res.data.agent_executions || [])
        setRecommendations(res.data.recommendations || [])
        setReport(res.data.report || null)
      }
    } catch (err) {
      console.error('Failed to load session details:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Load knowledge documents
  const loadKnowledge = useCallback(async () => {
    try {
      const res = await apiClient.listKnowledgeDocuments()
      if (res.data) {
        setKnowledgeDocs(res.data)
      }
    } catch (err) {
      console.error('Failed to load knowledge documents:', err)
    }
  }, [])

  useEffect(() => {
    loadSessions()
    loadKnowledge()
  }, [loadSessions, loadKnowledge])

  useEffect(() => {
    if (selectedSessionId) {
      loadSessionDetails(selectedSessionId)
    }
  }, [selectedSessionId, loadSessionDetails])

  // Start new diagnostic run
  const handleStartDiagnostic = async () => {
    try {
      setRunningDiagnostic(true)
      setStatusMessage(null)
      const res = await apiClient.startDiagnosticSession({
        machine_id: machineId,
        trigger_type: 'MANUAL_ENGINEER',
      })
      if (res.data) {
        setStatusMessage({
          type: 'success',
          text: 'LangGraph multi-agent diagnostic investigation completed successfully.',
        })
        await loadSessions()
        if (res.data.session) {
          setSelectedSessionId(res.data.session.id)
          await loadSessionDetails(res.data.session.id)
        }
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Failed to complete diagnostic.' })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error executing diagnostic workflow.'
      setStatusMessage({ type: 'error', text: msg })
    } finally {
      setRunningDiagnostic(false)
    }
  }

  // Approve recommendation
  const handleApproveRecommendation = async () => {
    if (!showApproveModal) return
    try {
      setApproving(true)
      const res = await apiClient.approveRecommendation(showApproveModal.id, {
        notes: approveNotes,
        assigned_technician_id: assignedTech || undefined,
        scheduled_for: scheduledDate || undefined,
      })
      if (res.data) {
        setStatusMessage({
          type: 'success',
          text: `Recommendation authorized. Work Order ${res.data.work_order_reference || 'WO-STAGED'} generated.`,
        })
        setShowApproveModal(null)
        setApproveNotes('')
        setAssignedTech('')
        setScheduledDate('')
        if (selectedSessionId) loadSessionDetails(selectedSessionId)
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Approval failed.' })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error approving recommendation.'
      setStatusMessage({ type: 'error', text: msg })
    } finally {
      setApproving(false)
    }
  }

  // Reject recommendation
  const handleRejectRecommendation = async () => {
    if (!showRejectModal || !rejectReason.trim()) return
    try {
      setRejecting(true)
      const res = await apiClient.rejectRecommendation(showRejectModal.id, {
        reason: rejectReason.trim(),
        notes: rejectNotes || undefined,
      })
      if (res.data) {
        setStatusMessage({
          type: 'success',
          text: 'Recommendation rejected with GMP change control audit trail entry.',
        })
        setShowRejectModal(null)
        setRejectReason('')
        setRejectNotes('')
        if (selectedSessionId) loadSessionDetails(selectedSessionId)
      } else {
        setStatusMessage({ type: 'error', text: res.error || 'Rejection failed.' })
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error rejecting recommendation.'
      setStatusMessage({ type: 'error', text: msg })
    } finally {
      setRejecting(false)
    }
  }

  // Run RAG test retrieval
  const handleRagSearch = async () => {
    if (!ragQuery.trim()) return
    try {
      setRagSearching(true)
      const res = await apiClient.testKnowledgeRetrieval({ query: ragQuery.trim(), top_k: 5 })
      if (res.data) {
        setRagResults(res.data)
      }
    } catch (err) {
      console.error('RAG search error:', err)
    } finally {
      setRagSearching(false)
    }
  }

  // Agents workflow pipeline structure
  const AGENT_PIPELINE = [
    { key: 'DATA_QUALITY_AGENT', label: '1. Data Quality', icon: Database, desc: 'Telemetry trustworthiness & noise check' },
    { key: 'CONDITION_MONITORING_AGENT', label: '2. Condition Monitoring', icon: Activity, desc: 'Health scoring & anomaly synthesis' },
    { key: 'FAILURE_PREDICTION_AGENT', label: '3. Failure Prediction', icon: TrendingUp, desc: 'Weibull RUL & calibrated ML risk' },
    { key: 'ROOT_CAUSE_ANALYSIS_AGENT', label: '4. Root Cause (RAG)', icon: Search, desc: 'Semantic retrieval across SOPs & OEM manuals' },
    { key: 'MAINTENANCE_RECOMMENDATION_AGENT', label: '5. Maintenance Action', icon: Wrench, desc: 'Actionable intervention formulation' },
    { key: 'COMPLIANCE_SAFETY_AGENT', label: '6. Compliance & Safety', icon: ShieldCheck, desc: 'Deterministic LOTO & zero-energy check' },
    { key: 'REPORTING_AGENT', label: '7. Audit Reporting', icon: FileCheck, desc: 'Explainable dossier with observations vs hypotheses' },
  ]

  return (
    <div className="space-y-6">
      {/* Top Banner with Actions */}
      <div className="flex flex-col gap-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-purple-50 text-purple-700">
              <Bot className="size-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">LangGraph Multi-Agent Intelligence & RAG</h2>
              <p className="text-sm text-slate-500">
                Pharmaceutical Maintenance Decision-Support • Air-Gapped Semantic Knowledge • Strict Safety Boundaries
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowRagModal(true)}
            className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <Search className="size-4 text-purple-600" />
            <span>Search SOPs ({knowledgeDocs.length})</span>
          </button>

          <button
            onClick={handleStartDiagnostic}
            disabled={runningDiagnostic}
            className="flex items-center gap-2 rounded-lg bg-[#1685ff] px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-600 disabled:opacity-50"
          >
            {runningDiagnostic ? (
              <>
                <RefreshCw className="size-4 animate-spin" />
                <span>Running Multi-Agent Graph...</span>
              </>
            ) : (
              <>
                <Play className="size-4 fill-white" />
                <span>Run Diagnostic Investigation</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Notifications */}
      {statusMessage && (
        <div
          className={`flex items-center justify-between rounded-lg p-4 text-sm ${
            statusMessage.type === 'success'
              ? 'border border-emerald-200 bg-emerald-50 text-emerald-800'
              : 'border border-rose-200 bg-rose-50 text-rose-800'
          }`}
        >
          <div className="flex items-center gap-2">
            {statusMessage.type === 'success' ? (
              <CheckCircle2 className="size-5 text-emerald-600" />
            ) : (
              <AlertTriangle className="size-5 text-rose-600" />
            )}
            <span>{statusMessage.text}</span>
          </div>
          <button onClick={() => setStatusMessage(null)} className="text-slate-400 hover:text-slate-600">
            <X className="size-4" />
          </button>
        </div>
      )}

      {/* Sub-Tabs Navigation */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveSubTab('investigation')}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-bold transition ${
            activeSubTab === 'investigation'
              ? 'border-[#1685ff] text-[#1685ff]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Bot className="size-4" />
          <span>Multi-Agent Workflow & Hypotheses</span>
        </button>

        <button
          onClick={() => setActiveSubTab('recommendations')}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-bold transition ${
            activeSubTab === 'recommendations'
              ? 'border-[#1685ff] text-[#1685ff]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Wrench className="size-4" />
          <span>Maintenance Actions & Approvals</span>
          {recommendations.length > 0 && (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-[#1685ff]">
              {recommendations.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveSubTab('report')}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-bold transition ${
            activeSubTab === 'report'
              ? 'border-[#1685ff] text-[#1685ff]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <FileText className="size-4" />
          <span>Diagnostic Dossier & Audit</span>
        </button>

        <button
          onClick={() => setActiveSubTab('knowledge')}
          className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-bold transition ${
            activeSubTab === 'knowledge'
              ? 'border-[#1685ff] text-[#1685ff]'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Database className="size-4" />
          <span>SOP & OEM Knowledge Base</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
            {knowledgeDocs.length}
          </span>
        </button>
      </div>

      {/* SUB-TAB 1: INVESTIGATION & AGENT WORKFLOW */}
      {activeSubTab === 'investigation' && (
        <div className="space-y-6">
          {/* Recent Sessions Selector */}
          {sessions.length > 0 && (
            <div className="flex items-center gap-3 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
              <span className="text-xs font-bold text-slate-500 uppercase whitespace-nowrap">Diagnostic Sessions:</span>
              {sessions.map((sess) => (
                <button
                  key={sess.id}
                  onClick={() => setSelectedSessionId(sess.id)}
                  className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition ${
                    selectedSessionId === sess.id
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
                  }`}
                >
                  <Bot className="size-3.5" />
                  <span>{new Date(sess.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                  <span className={`rounded px-1.5 py-0.2 text-[9px] font-bold ${
                    sess.status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'
                  }`}>
                    {sess.status}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* 7-Agent Pipeline Progress Visualizer */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-4 text-sm font-bold text-slate-900 uppercase tracking-wider">
              Autonomous Agent Orchestration Pipeline
            </h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-7">
              {AGENT_PIPELINE.map((ag) => {
                const exec = executions.find((e) => e.agent_name === ag.key)
                const isCompleted = exec && exec.status === 'COMPLETED'
                return (
                  <div
                    key={ag.key}
                    className={`flex flex-col justify-between rounded-lg border p-3 transition ${
                      isCompleted
                        ? 'border-emerald-300 bg-emerald-50/50'
                        : 'border-slate-200 bg-slate-50'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <ag.icon className={`size-5 ${isCompleted ? 'text-emerald-600' : 'text-slate-400'}`} />
                        {isCompleted ? (
                          <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-700">
                            <Check className="size-3" />
                            {exec.execution_time_ms ? `${Math.round(exec.execution_time_ms)}ms` : 'Done'}
                          </span>
                        ) : (
                          <span className="text-[10px] font-semibold text-slate-400">Idle</span>
                        )}
                      </div>
                      <h4 className="mt-2 text-xs font-bold text-slate-900">{ag.label}</h4>
                      <p className="mt-1 text-[11px] text-slate-500 leading-tight">{ag.desc}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Root Cause Hypotheses Section */}
          {report?.root_cause_analysis?.hypotheses && report.root_cause_analysis.hypotheses.length > 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-bold text-slate-900">Ranked Root Cause Hypotheses</h3>
                  <p className="text-xs text-slate-500">
                    Formulated through RAG semantic retrieval over validated technical manuals and SOPs
                  </p>
                </div>
                <span className="rounded-full bg-purple-100 px-2.5 py-1 text-xs font-bold text-purple-700">
                  {report.root_cause_analysis.hypotheses.length} Hypotheses Formed
                </span>
              </div>

              <div className="space-y-3">
                {report.root_cause_analysis.hypotheses.map((hyp, idx) => (
                  <div key={idx} className="rounded-lg border border-slate-200 bg-slate-50 p-4 transition hover:bg-white hover:shadow-xs">
                    <div className="flex items-start gap-3">
                      <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-purple-100 text-xs font-bold text-purple-700">
                        {idx + 1}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-semibold text-slate-900">{hyp}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
              <Bot className="mx-auto size-10 text-slate-300" />
              <h4 className="mt-3 text-sm font-bold text-slate-700">No Active Diagnostic Hypotheses</h4>
              <p className="mt-1 text-xs text-slate-500 max-w-md mx-auto">
                Click &quot;Run Diagnostic Investigation&quot; to execute the multi-agent pipeline and analyze current machine telemetry.
              </p>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 2: RECOMMENDATIONS & HUMAN APPROVAL */}
      {activeSubTab === 'recommendations' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900">Actionable Maintenance Recommendations</h3>
              <p className="text-xs text-slate-500">
                Requires human maintenance engineer review & authorization before physical execution (21 CFR Part 11)
              </p>
            </div>
          </div>

          {recommendations.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {recommendations.map((rec) => (
                <div key={rec.id} className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase ${
                          rec.priority === 'CRITICAL'
                            ? 'bg-rose-100 text-rose-800'
                            : rec.priority === 'HIGH'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-blue-100 text-blue-800'
                        }`}>
                          {rec.priority} Priority
                        </span>
                        <h4 className="mt-2 text-base font-bold text-slate-900">{rec.title}</h4>
                      </div>

                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                        rec.approval_status === 'APPROVED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : rec.approval_status === 'REJECTED'
                          ? 'bg-rose-100 text-rose-800'
                          : 'bg-amber-50 text-amber-800 border border-amber-200'
                      }`}>
                        {rec.approval_status}
                      </span>
                    </div>

                    <p className="mt-2 text-xs font-semibold text-slate-700">
                      <span className="text-slate-400">Suspected Issue: </span>
                      {rec.suspected_issue}
                    </p>

                    <p className="mt-2 text-xs text-slate-600 leading-relaxed">
                      {rec.recommended_action}
                    </p>

                    {/* Safety Badges */}
                    {rec.safety_requirements && rec.safety_requirements.length > 0 && (
                      <div className="mt-4 rounded-lg bg-amber-50/70 p-3 border border-amber-100">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
                          <Lock className="size-3.5 text-amber-700" />
                          <span>Mandatory Safety & Compliance Protocols:</span>
                        </div>
                        <ul className="mt-1.5 space-y-1">
                          {rec.safety_requirements.map((req, i) => (
                            <li key={i} className="text-[11px] text-amber-800 flex items-start gap-1.5">
                              <span className="text-amber-500">•</span>
                              <span>{req}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Work Order Staging Badge if approved */}
                    {rec.work_order_reference && (
                      <div className="mt-3 flex items-center gap-2 rounded bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800 border border-emerald-200">
                        <CheckCircle2 className="size-4 text-emerald-600" />
                        <span>Work Order Ref: <strong>{rec.work_order_reference}</strong></span>
                      </div>
                    )}
                  </div>

                  {/* Action Buttons for Human Engineer */}
                  {rec.approval_status === 'PENDING_REVIEW' && (
                    <div className="mt-5 flex items-center justify-end gap-2 border-t border-slate-100 pt-4">
                      <button
                        onClick={() => setShowRejectModal(rec)}
                        className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
                      >
                        <X className="size-3.5 text-rose-600" />
                        <span>Reject</span>
                      </button>

                      <button
                        onClick={() => setShowApproveModal(rec)}
                        disabled={rec.compliance_state === 'BLOCKED'}
                        className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 transition disabled:opacity-40"
                      >
                        <Check className="size-3.5" />
                        <span>Authorize Work Order</span>
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
              <Wrench className="mx-auto size-10 text-slate-300" />
              <h4 className="mt-3 text-sm font-bold text-slate-700">No Recommendations Available</h4>
              <p className="mt-1 text-xs text-slate-500">
                Run an active diagnostic investigation to generate evidence-backed maintenance recommendations.
              </p>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 3: DIAGNOSTIC REPORT DOSSIER */}
      {activeSubTab === 'report' && (
        <div className="space-y-6">
          {report ? (
            <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm print:p-0">
              <div className="border-b border-slate-200 pb-5">
                <div className="flex items-center justify-between">
                  <span className="rounded bg-purple-100 px-2 py-0.5 text-xs font-bold text-purple-800">
                    GMP Diagnostic Report • PharmaPredict AI
                  </span>
                  <span className="text-xs text-slate-400">
                    Generated: {report.generated_at ? new Date(report.generated_at).toLocaleString() : 'N/A'}
                  </span>
                </div>
                <h2 className="mt-3 text-xl font-bold text-slate-900">{report.title || report.report_title}</h2>
              </div>

              {/* Executive Summary */}
              <div className="mt-6">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Executive Summary</h4>
                <p className="mt-2 text-sm leading-relaxed text-slate-700 bg-slate-50 p-4 rounded-lg border border-slate-200">
                  {report.executive_summary}
                </p>
              </div>

              {/* Observations vs Hypotheses Separation */}
              <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
                <div className="rounded-lg border border-slate-200 p-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                    <Activity className="size-4 text-blue-600" />
                    <span>Empirical Observations (Telemetry & Anomalies)</span>
                  </h4>
                  <pre className="mt-2 text-xs font-mono text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {report.condition_summary?.summary || 'Operational baseline data normal.'}
                  </pre>
                </div>

                <div className="rounded-lg border border-slate-200 p-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                    <TrendingUp className="size-4 text-purple-600" />
                    <span>Validated Model Predictions & RUL</span>
                  </h4>
                  <pre className="mt-2 text-xs font-mono text-slate-700 whitespace-pre-wrap leading-relaxed">
                    {report.predictive_results?.summary || 'Prediction model inactive or data threshold not met.'}
                  </pre>
                </div>
              </div>

              {/* Safety Compliance Notes */}
              {report.safety_compliance_notes && report.safety_compliance_notes.length > 0 && (
                <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50/50 p-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
                    <ShieldCheck className="size-4 text-amber-700" />
                    <span>Safety & Regulatory Isolation Directives</span>
                  </h4>
                  <ul className="mt-2 space-y-1">
                    {report.safety_compliance_notes.map((note, idx) => (
                      <li key={idx} className="text-xs text-amber-800 flex items-start gap-2">
                        <span className="text-amber-500 font-bold">•</span>
                        <span>{note}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Technical Limitations & Disclaimer */}
              {report.technical_limitations && report.technical_limitations.length > 0 && (
                <div className="mt-6 border-t border-slate-100 pt-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Technical Limitations & Legal Notice</h4>
                  <ul className="mt-2 space-y-1">
                    {report.technical_limitations.map((lim, idx) => (
                      <li key={idx} className="text-[11px] text-slate-400 flex items-start gap-1.5">
                        <span>—</span>
                        <span>{lim}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
              <FileText className="mx-auto size-10 text-slate-300" />
              <h4 className="mt-3 text-sm font-bold text-slate-700">No Report Generated Yet</h4>
              <p className="mt-1 text-xs text-slate-500">Run a diagnostic session to produce a full dossier.</p>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 4: TECHNICAL KNOWLEDGE & SOP BROWSER */}
      {activeSubTab === 'knowledge' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-slate-900">Indexed Pharmaceutical Knowledge Base</h3>
              <p className="text-xs text-slate-500">
                Tenant-isolated SOPs, equipment service manuals, and standard pharmaceutical procedures used by Agent 4 (RAG)
              </p>
            </div>
            <button
              onClick={() => setShowRagModal(true)}
              className="flex items-center gap-2 rounded-lg bg-purple-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-purple-700 transition"
            >
              <Search className="size-3.5" />
              <span>Semantic Search Test</span>
            </button>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {knowledgeDocs.map((doc) => (
              <div key={doc.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-700">
                      {doc.document_type}
                    </span>
                    {doc.is_standard && (
                      <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-700">
                        Standard SOP
                      </span>
                    )}
                  </div>
                  <h4 className="mt-2 text-sm font-bold text-slate-900">{doc.title}</h4>
                  <p className="mt-1 text-xs text-slate-500">
                    {doc.component_type ? `Target: ${doc.component_type}` : 'General assembly'}
                  </p>
                </div>
                <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-[11px] text-slate-400">
                  <span>{doc.chunk_count} Vector Chunks</span>
                  <span>v{doc.version}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* APPROVE RECOMMENDATION MODAL */}
      {showApproveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-900">Authorize Maintenance Recommendation</h3>
            <p className="mt-1 text-xs text-slate-500">
              This action stages an authorized industrial work order. Enter execution details for the maintenance logbook.
            </p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-700">Action Summary</label>
                <p className="mt-1 text-xs text-slate-600 bg-slate-50 p-2.5 rounded border border-slate-200">
                  {showApproveModal.title}
                </p>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Assigned Technician ID / Name</label>
                <input
                  type="text"
                  placeholder="e.g. Lead Tech John Doe"
                  value={assignedTech}
                  onChange={(e) => setAssignedTech(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:border-[#1685ff] focus:outline-hidden"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Scheduled Date</label>
                <input
                  type="date"
                  value={scheduledDate}
                  onChange={(e) => setScheduledDate(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:border-[#1685ff] focus:outline-hidden"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Authorization Notes</label>
                <textarea
                  rows={2}
                  placeholder="Optional engineer sign-off comments..."
                  value={approveNotes}
                  onChange={(e) => setApproveNotes(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:border-[#1685ff] focus:outline-hidden"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowApproveModal(null)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleApproveRecommendation}
                disabled={approving}
                className="rounded-lg bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {approving ? 'Authorizing...' : 'Authorize Work Order'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* REJECT RECOMMENDATION MODAL */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-bold text-slate-900">Reject Recommendation</h3>
            <p className="mt-1 text-xs text-slate-500">
              For GMP change control and FDA 21 CFR Part 11 compliance, an engineering justification is required to decline recommendations.
            </p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-700">
                  Justification Reason <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={3}
                  placeholder="e.g. Bearing was replaced during yesterday's changeover; sensor requires recalibration."
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-rose-500 focus:outline-hidden"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700">Additional Notes</label>
                <input
                  type="text"
                  placeholder="Optional log entry reference..."
                  value={rejectNotes}
                  onChange={(e) => setRejectNotes(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:border-slate-400 focus:outline-hidden"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowRejectModal(null)}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRejectRecommendation}
                disabled={rejecting || !rejectReason.trim()}
                className="rounded-lg bg-rose-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-rose-700 disabled:opacity-50"
              >
                {rejecting ? 'Submitting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RAG SEMANTIC RETRIEVAL TEST MODAL */}
      {showRagModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2">
                <Search className="size-5 text-purple-600" />
                <h3 className="text-base font-bold text-slate-900">Semantic SOP & Technical Guide Search</h3>
              </div>
              <button onClick={() => setShowRagModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="size-5" />
              </button>
            </div>

            <div className="mt-4 flex gap-2">
              <input
                type="text"
                placeholder="Ask technical question or symptom (e.g. 'bearing vibration limit' or 'motor overheating SOP')..."
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleRagSearch()}
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-purple-600 focus:outline-hidden"
              />
              <button
                onClick={handleRagSearch}
                disabled={ragSearching || !ragQuery.trim()}
                className="rounded-lg bg-purple-600 px-4 py-2 text-xs font-semibold text-white hover:bg-purple-700 disabled:opacity-50"
              >
                {ragSearching ? 'Searching...' : 'Search'}
              </button>
            </div>

            <div className="mt-4 flex-1 overflow-y-auto space-y-3">
              {ragResults.length > 0 ? (
                ragResults.map((r, i) => (
                  <div key={i} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-900">{r.title}</span>
                      <span className="rounded bg-purple-100 px-2 py-0.5 text-[10px] font-bold text-purple-700">
                        Match: {Math.round(r.relevance_score * 100)}%
                      </span>
                    </div>
                    <p className="mt-1.5 text-xs text-slate-600 leading-relaxed font-mono bg-white p-2.5 rounded border border-slate-100">
                      {r.content_excerpt}
                    </p>
                  </div>
                ))
              ) : (
                <div className="py-12 text-center text-xs text-slate-400">
                  Type a maintenance symptom to test semantic vector retrieval over indexed SOPs.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
