import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from app.ai_engine.schemas.diagnostic_state import (
    DiagnosticState,
    DiagnosticReportSchema,
)


class ReportingAgent:
    """Agent 7: Reporting Agent.
    
    Synthesizes the diagnostic session into an auditable, GMP-compliant diagnostic report
    strictly separating empirical telemetry observations from diagnostic hypotheses.
    """

    NAME = "REPORTING_AGENT"

    @classmethod
    def execute(cls, state: DiagnosticState) -> DiagnosticState:
        t0 = time.time()
        report_id = str(uuid.uuid4())[:12]

        machine_id = state.machine_id
        session_id = state.diagnostic_session_id

        # Executive Summary
        if state.condition.condition_state == "NORMAL":
            exec_summary = (
                f"Diagnostic assessment completed for Machine {machine_id}. All active operational signals "
                f"and condition indicators are within normal pharmaceutical baseline parameters. No urgent intervention required."
            )
        else:
            hyp_summary = f"Top suspected cause: {state.hypotheses[0].suspected_cause}." if state.hypotheses else "No definitive hypothesis formed."
            exec_summary = (
                f"Diagnostic investigation conducted for Machine {machine_id} following {state.condition.severity} severity anomaly detection. "
                f"Overall condition state is {state.condition.condition_state} (Anomaly Score: {state.condition.anomaly_score:.2f}). "
                f"{hyp_summary} Recommended {len(state.recommendations)} targeted maintenance actions under strict safety controls."
            )

        # Condition Summary
        cond_lines = [
            f"Operating State: {state.condition.operating_state}",
            f"Condition State: {state.condition.condition_state} (Severity: {state.condition.severity})",
            f"Health Score: {state.condition.health_score:.1f}% | Anomaly Score: {state.condition.anomaly_score:.2f}",
        ]
        if state.condition.active_anomalies:
            cond_lines.append(f"Active Anomalies ({len(state.condition.active_anomalies)}):")
            for anom in state.condition.active_anomalies[:5]:
                cond_lines.append(f" - [{anom.get('signal_name', 'Signal')}] {anom.get('description', 'Abnormal reading')} (Severity: {anom.get('severity', 'UNKNOWN')})")
        condition_summary = "\n".join(cond_lines)

        # Prediction Summary
        pred_lines = [
            f"Model Status: {state.prediction.model_status}",
            f"Prediction Eligibility: {'Eligible' if state.prediction.is_eligible else 'Ineligible - ' + state.prediction.model_status}",
            f"Risk Category: {state.prediction.risk_category}",
        ]
        if state.prediction.calibrated_probability is not None:
            pred_lines.append(f"Calibrated Failure Probability: {state.prediction.calibrated_probability:.2%}")
        if state.prediction.estimated_rul_hours is not None:
            pred_lines.append(f"Estimated Remaining Useful Life (RUL): {state.prediction.estimated_rul_hours:.1f} Operating Hours")
            if state.prediction.rul_confidence_interval:
                pred_lines.append(
                    f"RUL 90% Confidence Interval: [{state.prediction.rul_confidence_interval[0]:.1f}h - {state.prediction.rul_confidence_interval[1]:.1f}h]"
                )
        if state.prediction.model_version:
            pred_lines.append(f"Validated Model Version: {state.prediction.model_version}")
        prediction_summary = "\n".join(pred_lines)

        # Root Cause Analysis
        rca_list: List[str] = []
        for i, hyp in enumerate(state.hypotheses, 1):
            doc_cites = f" [Cited: {', '.join(hyp.cited_documents)}]" if hyp.cited_documents else ""
            rca_list.append(
                f"{i}. [{hyp.hypothesis_status} | Confidence: {hyp.confidence_level}] {hyp.suspected_cause}{doc_cites}. "
                f"Observed: {'; '.join(hyp.supporting_observations[:3])}. "
                f"Verification: {'; '.join(hyp.recommended_verification_steps[:2])}"
            )
        if not rca_list:
            rca_list.append("Baseline operational telemetry did not indicate significant physical root cause mechanisms.")

        # Maintenance Recommendations formatted
        recs_list: List[Dict[str, Any]] = []
        for rec in state.recommendations:
            recs_list.append({
                "recommendation_id": rec.recommendation_id,
                "title": rec.title,
                "priority": rec.priority,
                "component_type": rec.component_type,
                "recommended_action": rec.recommended_action,
                "safety_requirements": rec.safety_requirements,
                "compliance_state": rec.compliance_state,
                "requires_engineer_approval": rec.requires_engineer_approval,
            })

        # Safety & Compliance Notes
        safety_notes: List[str] = list(state.compliance.safety_notes)
        if state.compliance.loto_required:
            safety_notes.append("CRITICAL: Zero-energy state verification mandatory before opening guard panels.")
        if state.compliance.cleanroom_ppe_required:
            safety_notes.append("Cleanroom protocol: Tool decontamination and particle swab required post-maintenance.")

        # Technical Limitations & Disclaimers
        limitations = [
            "All recommendations are generated as decision-support guidance for qualified pharmaceutical maintenance personnel.",
            "PharmaPredict AI does not possess autonomous machine control capability; work orders and physical interventions require manual authorization.",
            "Statistical anomaly indicators and RUL estimates are probabilistic and subject to operating mode variability and historical dataset quality.",
            "Adherence to plant-specific SOPs, OSHA LOTO guidelines, and GMP 21 CFR Part 211 remains the sole responsibility of the certified technician."
        ]
        if not state.data_quality.is_reliable:
            limitations.append("WARNING: Telemetry data quality is compromised. Physical sensor verification is required prior to acting on findings.")

        report = DiagnosticReportSchema(
            report_id=report_id,
            title=f"Equipment Diagnostic Report — Machine {machine_id} [{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}]",
            executive_summary=exec_summary,
            condition_summary=condition_summary,
            prediction_summary=prediction_summary,
            root_cause_analysis=rca_list,
            maintenance_recommendations=recs_list,
            safety_compliance_notes=safety_notes,
            technical_limitations=limitations,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        state.report = report
        state.current_stage = "COMPLETED"

        duration = time.time() - t0
        state.agent_executions.append({
            "agent_name": cls.NAME,
            "status": "COMPLETED",
            "duration_ms": round(duration * 1000, 2),
            "summary": f"Generated Diagnostic Report {report_id} with {len(recs_list)} recommendations.",
            "details": {
                "report_id": report_id,
                "recommendations_count": len(recs_list),
                "hypotheses_count": len(rca_list),
            }
        })
        return state

