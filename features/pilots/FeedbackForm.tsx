'use client';

import React, { useState } from 'react';
import {
  FactoryPilotItem,
  apiClient,
} from '@/lib/api-client';
import {
  UserCheck,
  Send,
  AlertTriangle,
  CheckCircle2,
  FileQuestion,
} from 'lucide-react';

interface FeedbackFormProps {
  pilot: FactoryPilotItem;
  diagnosticSessionId?: string;
  onRefresh: () => void;
}

export const FeedbackForm: React.FC<FeedbackFormProps> = ({
  pilot,
  diagnosticSessionId,
  onRefresh,
}) => {
  const [sessionId, setSessionId] = useState(diagnosticSessionId || '');
  const [assessment, setAssessment] = useState<string>('ACCURATE');
  const [referenceLabel, setReferenceLabel] = useState<string>('TRUE_POSITIVE');
  const [verifiedRootCause, setVerifiedRootCause] = useState('');
  const [inspectionFindings, setInspectionFindings] = useState('');
  const [actionTaken, setActionTaken] = useState('');
  const [actualOutcome, setActualOutcome] = useState('');
  const [comments, setComments] = useState('');
  const [falseAlarmFlag, setFalseAlarmFlag] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sessionId) {
      setErrorMsg('Diagnostic Session ID is required.');
      return;
    }

    setSubmitting(true);
    setSuccessMsg(null);
    setErrorMsg(null);

    try {
      const res = await apiClient.submitEngineerFeedback(pilot.id, {
        diagnostic_session_id: sessionId,
        assessment,
        reference_label: referenceLabel,
        verified_root_cause: verifiedRootCause,
        inspection_findings: inspectionFindings,
        action_taken: actionTaken,
        actual_outcome: actualOutcome,
        comments,
        false_alarm_flag: falseAlarmFlag,
      });

      if (res.status === 201) {
        setSuccessMsg('Engineer feedback recorded successfully into 21 CFR Part 11 audit log.');
        setVerifiedRootCause('');
        setInspectionFindings('');
        setActionTaken('');
        setActualOutcome('');
        setComments('');
        onRefresh();
      } else {
        setErrorMsg(res.error || 'Failed to submit feedback.');
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-[#102c50]/80 border border-slate-700/60 rounded-xl p-6 shadow-xl max-w-3xl">
      <div className="flex items-center gap-3 pb-4 border-b border-slate-700/60">
        <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
          <UserCheck className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-white">Maintenance Engineer Diagnostic Feedback</h3>
          <p className="text-xs text-slate-400">
            Submit verified ground truth on AI anomaly diagnoses, mechanical inspection observations, and confirmed root causes.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-5 space-y-4">
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">
            Diagnostic Session ID <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            required
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
            className="w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">AI Diagnostic Assessment</label>
            <select
              value={assessment}
              onChange={(e) => setAssessment(e.target.value)}
              className="w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500"
            >
              <option value="ACCURATE">ACCURATE (Diagnosis & actions correct)</option>
              <option value="PARTIALLY_ACCURATE">PARTIALLY_ACCURATE (Some findings valid)</option>
              <option value="INACCURATE">INACCURATE (Diagnosis incorrect)</option>
              <option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT_EVIDENCE (Cannot confirm)</option>
              <option value="NOT_APPLICABLE">NOT_APPLICABLE (Non-failure transient)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Ground Truth Reference Label</label>
            <select
              value={referenceLabel}
              onChange={(e) => setReferenceLabel(e.target.value)}
              className="w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500"
            >
              <option value="TRUE_POSITIVE">TRUE_POSITIVE (Actual equipment anomaly/fault)</option>
              <option value="FALSE_POSITIVE">FALSE_POSITIVE (Spurious false alarm)</option>
              <option value="FALSE_NEGATIVE">FALSE_NEGATIVE (AI missed degradation)</option>
              <option value="TRUE_NEGATIVE">TRUE_NEGATIVE (Confirmed healthy machine)</option>
              <option value="UNVERIFIED">UNVERIFIED (Pending physical inspection)</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Physically Verified Root Cause</label>
          <input
            type="text"
            value={verifiedRootCause}
            onChange={(e) => setVerifiedRootCause(e.target.value)}
            placeholder="e.g. Drive motor bearing outer raceway spalling and lubricant dry-out"
            className="w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">Inspection Findings & Tool Measurements</label>
          <textarea
            rows={2}
            value={inspectionFindings}
            onChange={(e) => setInspectionFindings(e.target.value)}
            placeholder="e.g. Ultrasound acoustic probe measured 36 dBµV; dial indicator showed 0.08 mm radial play."
            className="w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Action Taken</label>
            <input
              type="text"
              value={actionTaken}
              onChange={(e) => setActionTaken(e.target.value)}
              placeholder="e.g. Replenished synthetic grease; scheduled replacement"
              className="w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Actual Outcome</label>
            <input
              type="text"
              value={actualOutcome}
              onChange={(e) => setActualOutcome(e.target.value)}
              placeholder="e.g. Vibration dropped from 4.8 mm/s to 1.9 mm/s"
              className="w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <input
            type="checkbox"
            id="falseAlarm"
            checked={falseAlarmFlag}
            onChange={(e) => setFalseAlarmFlag(e.target.checked)}
            className="w-4 h-4 rounded text-emerald-600 bg-slate-900 border-slate-700 focus:ring-0"
          />
          <label htmlFor="falseAlarm" className="text-xs text-slate-300 font-medium cursor-pointer">
            Flag this event as a False Alarm (Transient operating mode or sensor drift)
          </label>
        </div>

        {errorMsg && (
          <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-lg text-red-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="p-3 bg-emerald-950/40 border border-emerald-800/60 rounded-lg text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        <div className="pt-2 flex justify-end">
          <button
            type="submit"
            disabled={submitting}
            className="px-5 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 shadow-lg shadow-emerald-600/30 transition-all"
          >
            <Send className="w-3.5 h-3.5" />
            {submitting ? 'Submitting...' : 'Submit Certified Feedback'}
          </button>
        </div>
      </form>
    </div>
  );
};

