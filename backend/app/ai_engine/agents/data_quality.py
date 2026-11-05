import time
from typing import Dict, Any
from app.ai_engine.schemas.diagnostic_state import DiagnosticState, DataQualityAssessment
from app.modules.data_quality.services import DataQualityService
from app.models.condition import QualityState


class DataQualityAgent:
    """Agent 1: Determines whether machine telemetry is trustworthy enough for diagnosis."""

    NAME = "DATA_QUALITY_AGENT"

    @classmethod
    def execute(cls, state: DiagnosticState) -> DiagnosticState:
        t0 = time.time()
        org_id = state.organization_id
        mach_id = state.machine_id

        # If state already has unreliable data quality specified (e.g. injected or pre-evaluated)
        if state.data_quality and (not state.data_quality.is_reliable or state.data_quality.quality_state in (QualityState.BAD, QualityState.MISSING, QualityState.STALE, "BAD", "MISSING", "STALE")):
            is_blocked = True
            overall_state = state.data_quality.quality_state
            issues = [{"issue_type": i} for i in state.data_quality.issues_detected] if state.data_quality.issues_detected else []
            signals = {}
            affected_signals = state.data_quality.affected_signals
            state.data_quality.can_continue = False
            state.data_quality.is_reliable = False
        else:
            # Query existing Phase 5 Data Quality engine
            dq_eval = DataQualityService.evaluate_machine_quality(
                machine_id=mach_id,
                organization_id=org_id,
                recent_minutes=15,
            )

            overall_state = dq_eval.get("overall_state", QualityState.GOOD)
            issues = dq_eval.get("issues", [])
            signals = dq_eval.get("signal_evaluations", {})

            affected_signals = [sig_name for sig_name, eval_data in signals.items() if eval_data.get("quality_state") != QualityState.GOOD]

            # Decision rule: BAD, MISSING, or STALE halts diagnosis to prevent false alarms
            is_blocked = overall_state in (QualityState.BAD, QualityState.MISSING, QualityState.STALE)

            state.data_quality = DataQualityAssessment(
                quality_state=overall_state,
                can_continue=not is_blocked,
                is_reliable=not is_blocked,
                affected_signals=affected_signals,
                issues_detected=[i.get("issue_type", "Data Quality Issue") for i in issues],
                details=dq_eval,
            )

        execution_record = {
            "agent_name": cls.NAME,
            "status": "SUCCESS" if not is_blocked else "HALTED_DATA_QUALITY",
            "execution_time_ms": (time.time() - t0) * 1000.0,
            "summary": f"Data quality classified as {overall_state}." + (" Diagnostic proceeding." if not is_blocked else " Diagnostic halted to prevent false positive alarms."),
        }
        state.agent_executions.append(execution_record)

        if is_blocked:
            state.should_stop = True
            state.stop_reason = "DATA_QUALITY_UNRELIABLE"
            state.current_stage = "HALTED_DATA_QUALITY"
        else:
            state.current_stage = "DATA_QUALITY_VERIFIED"

        return state

