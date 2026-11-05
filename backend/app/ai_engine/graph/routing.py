"""Routing logic and conditional edges for LangGraph multi-agent diagnostic graph."""
from typing import Literal
from app.ai_engine.schemas.diagnostic_state import DiagnosticState


def route_after_data_quality(state: DiagnosticState) -> Literal["condition_monitoring", "reporting"]:
    """Conditional edge: Aborts diagnostic depth if incoming telemetry is invalid/unreliable."""
    if not state.data_quality.is_reliable:
        state.should_stop = True
        state.stop_reason = "DATA_QUALITY_UNRELIABLE"
        return "reporting"
    return "condition_monitoring"


def route_after_condition_monitoring(state: DiagnosticState) -> Literal["failure_prediction", "reporting"]:
    """Conditional edge: If machine is completely normal and healthy, skip failure prediction and jump to baseline reporting."""
    if state.condition.condition_state == "NORMAL" and state.condition.anomaly_score < 0.20:
        state.stop_reason = "EQUIPMENT_HEALTHY"
        return "reporting"
    return "failure_prediction"


def route_after_failure_prediction(state: DiagnosticState) -> Literal["root_cause"]:
    """Always routes from failure prediction to technical RAG root cause analysis."""
    return "root_cause"


def route_after_root_cause(state: DiagnosticState) -> Literal["maintenance_recommendation", "reporting"]:
    """Conditional edge: If no valid hypothesis can be formulated, route to reporting."""
    if not state.hypotheses:
        state.stop_reason = "NO_HYPOTHESIS_FORMULATED"
        return "reporting"
    return "maintenance_recommendation"


def route_after_maintenance_recommendation(state: DiagnosticState) -> Literal["compliance_safety"]:
    """Always routes generated recommendations through deterministic compliance & safety validation."""
    return "compliance_safety"


def route_after_compliance_safety(state: DiagnosticState) -> Literal["reporting"]:
    """Routes validated recommendations to final reporting synthesis."""
    return "reporting"

