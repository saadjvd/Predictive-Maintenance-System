import time
from typing import Dict, Any
from app.ai_engine.schemas.diagnostic_state import DiagnosticState, PredictionAssessment
from app.ai_engine.tools.prediction_tools import PredictionTools


class FailurePredictionAgent:
    """Agent 3: Retrieves validated ML failure risk and parametric Weibull RUL without fabricating scores."""

    NAME = "FAILURE_PREDICTION_AGENT"

    @classmethod
    def execute(cls, state: DiagnosticState) -> DiagnosticState:
        t0 = time.time()
        org_id = state.organization_id
        mach_id = state.machine_id

        # Query existing Phase 6 failure prediction engine
        predictions = PredictionTools.get_latest_validated_predictions(org_id, mach_id)

        if not predictions or predictions[0].get("status") == "PREDICTION_UNAVAILABLE":
            rationale = predictions[0].get("rationale") if predictions else "No validated prediction model configured for this equipment."
            state.prediction = PredictionAssessment(
                model_status="PREDICTION_UNAVAILABLE",
                is_available=False,
                calibrated_probability=None,
                risk_category="LOW",
                rul_hours=None,
                rationale=rationale,
            )
            summary_msg = f"Prediction unavailable: {rationale}"
        else:
            latest = predictions[0]
            cal_prob = latest.get("calibrated_probability")
            risk_cat = latest.get("risk_category", "LOW")
            rul_h = latest.get("rul_hours")

            state.prediction = PredictionAssessment(
                model_status="PREDICTION_READY",
                is_available=True,
                calibrated_probability=cal_prob,
                risk_category=risk_cat,
                rul_hours=rul_h,
                rul_confidence_lower=latest.get("rul_confidence_lower"),
                rul_confidence_upper=latest.get("rul_confidence_upper"),
                rul_method=latest.get("rul_method"),
                rationale=latest.get("rationale", ""),
                evidence_items=latest.get("evidence", []),
            )
            prob_pct = f"{cal_prob*100:.1f}%" if cal_prob is not None else "N/A"
            summary_msg = f"Validated model risk: {prob_pct} ({risk_cat}). RUL: {rul_h if rul_h is not None else 'UNAVAILABLE'}h."

        state.agent_executions.append({
            "agent_name": cls.NAME,
            "status": "SUCCESS",
            "execution_time_ms": (time.time() - t0) * 1000.0,
            "summary": summary_msg,
        })

        state.current_stage = "PREDICTION_VERIFIED"
        return state

