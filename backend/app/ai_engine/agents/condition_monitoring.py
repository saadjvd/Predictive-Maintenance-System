import time
from typing import Dict, Any
from app.ai_engine.schemas.diagnostic_state import DiagnosticState, ConditionAssessment
from app.ai_engine.tools.anomaly_tools import AnomalyTools


class ConditionMonitoringAgent:
    """Agent 2: Summarizes observed equipment abnormalities, baseline deviations, and anomaly severity."""

    NAME = "CONDITION_MONITORING_AGENT"

    @classmethod
    def execute(cls, state: DiagnosticState) -> DiagnosticState:
        t0 = time.time()
        org_id = state.organization_id
        mach_id = state.machine_id

        # Query existing Phase 5 Condition Monitoring & Anomaly services
        cond_summary = AnomalyTools.get_condition_summary(org_id, mach_id)
        db_anomalies = AnomalyTools.get_active_anomalies(org_id, mach_id, lookback_hours=24)
        baseline_deviations = AnomalyTools.get_baseline_deviations(org_id, mach_id)

        # Merge pre-populated condition (e.g. from test simulation or streaming trigger)
        pre_anomalies = []
        if state.condition:
            pre_anomalies = list(state.condition.active_anomalies or state.condition.anomalies)

        combined_anomalies = list(pre_anomalies)
        for a in db_anomalies:
            if a not in combined_anomalies:
                combined_anomalies.append(a)

        db_cond_state = cond_summary.get("condition_state", "NORMAL")
        if state.condition and state.condition.condition_state != "NORMAL":
            cond_state = state.condition.condition_state
        elif combined_anomalies:
            cond_state = "WARNING" if db_cond_state == "NORMAL" else db_cond_state
        else:
            cond_state = db_cond_state

        has_anomaly = len(combined_anomalies) > 0 or cond_state in ("ATTENTION", "WARNING", "CRITICAL")
        
        if state.condition and state.condition.severity != "INFO":
            severity = state.condition.severity
        else:
            severity = "CRITICAL" if cond_state == "CRITICAL" else ("WARNING" if cond_state in ("ATTENTION", "WARNING") else "INFO")

        anomaly_score = state.condition.anomaly_score if (state.condition and state.condition.anomaly_score > 0) else (0.65 if has_anomaly else 0.0)
        health_score = state.condition.health_score if (state.condition and state.condition.health_score < 100.0) else (65.0 if has_anomaly else 100.0)

        affected_signals = list(state.condition.affected_signals) if state.condition else []
        for anom in combined_anomalies:
            if anom.get("signal_name"):
                affected_signals.append(anom.get("signal_name"))
            affected_signals.extend(anom.get("affected_signals", []))
        affected_signals = list(set(affected_signals))

        summary_text = (
            f"Condition classified as {cond_state} (Severity: {severity}). "
            f"Found {len(combined_anomalies)} active anomaly event(s). "
            f"Deviations observed on {len(baseline_deviations)} baseline-mapped signal(s)."
        )

        state.condition = ConditionAssessment(
            condition_state=cond_state,
            severity=severity,
            has_anomaly=has_anomaly,
            anomaly_score=anomaly_score,
            health_score=health_score,
            affected_signals=affected_signals,
            anomalies=combined_anomalies,
            active_anomalies=combined_anomalies,
            baseline_deviations={k: v.get("baseline_mean", 0.0) for k, v in baseline_deviations.items()},
            summary=summary_text,
        )

        # Baseline check: If equipment is healthy with no anomalies, set stop reason for audit trail
        if cond_state == "NORMAL" and anomaly_score < 0.20 and not has_anomaly:
            state.stop_reason = "EQUIPMENT_HEALTHY"

        state.agent_executions.append({
            "agent_name": cls.NAME,
            "status": "SUCCESS",
            "execution_time_ms": (time.time() - t0) * 1000.0,
            "summary": summary_text,
        })

        state.current_stage = "CONDITION_ANALYZED"
        return state

