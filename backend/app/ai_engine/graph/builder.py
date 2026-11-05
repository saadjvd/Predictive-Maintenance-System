"""LangGraph multi-agent diagnostic graph construction and execution runner."""
import logging
import time
from typing import Optional, Dict, Any

from langgraph.graph import StateGraph, START, END
from app.ai_engine.schemas.diagnostic_state import DiagnosticState
from app.ai_engine.agents import (
    DataQualityAgent,
    ConditionMonitoringAgent,
    FailurePredictionAgent,
    RootCauseAnalysisAgent,
    MaintenanceRecommendationAgent,
    ComplianceSafetyAgent,
    ReportingAgent,
)
from app.ai_engine.graph.routing import (
    route_after_data_quality,
    route_after_condition_monitoring,
    route_after_failure_prediction,
    route_after_root_cause,
    route_after_maintenance_recommendation,
    route_after_compliance_safety,
)
from app.ai_engine.graph.checkpoints import get_memory_saver, persist_diagnostic_checkpoint
from app.extensions import db
from app.models.diagnostic import (
    DiagnosticSession,
    AgentExecution,
    MaintenanceRecommendation,
    DiagnosticReport,
)

logger = logging.getLogger(__name__)


def build_diagnostic_graph():
    """Builds and compiles the complete LangGraph diagnostic workflow."""
    workflow = StateGraph(DiagnosticState)

    # 1. Add all 7 agent nodes
    workflow.add_node("data_quality", DataQualityAgent.execute)
    workflow.add_node("condition_monitoring", ConditionMonitoringAgent.execute)
    workflow.add_node("failure_prediction", FailurePredictionAgent.execute)
    workflow.add_node("root_cause", RootCauseAnalysisAgent.execute)
    workflow.add_node("maintenance_recommendation", MaintenanceRecommendationAgent.execute)
    workflow.add_node("compliance_safety", ComplianceSafetyAgent.execute)
    workflow.add_node("reporting", ReportingAgent.execute)

    # 2. Add edges & conditional routing
    workflow.add_edge(START, "data_quality")

    workflow.add_conditional_edges(
        "data_quality",
        route_after_data_quality,
        {
            "condition_monitoring": "condition_monitoring",
            "reporting": "reporting",
        },
    )

    workflow.add_conditional_edges(
        "condition_monitoring",
        route_after_condition_monitoring,
        {
            "failure_prediction": "failure_prediction",
            "reporting": "reporting",
        },
    )

    workflow.add_edge("failure_prediction", "root_cause")

    workflow.add_conditional_edges(
        "root_cause",
        route_after_root_cause,
        {
            "maintenance_recommendation": "maintenance_recommendation",
            "reporting": "reporting",
        },
    )

    workflow.add_edge("maintenance_recommendation", "compliance_safety")
    workflow.add_edge("compliance_safety", "reporting")
    workflow.add_edge("reporting", END)

    # 3. Compile with memory checkpointer
    app_graph = workflow.compile(checkpointer=get_memory_saver())
    return app_graph


# Pre-compiled application graph instance
diagnostic_graph = build_diagnostic_graph()


def run_diagnostic_workflow(
    initial_state: DiagnosticState,
    thread_id: Optional[str] = None,
) -> DiagnosticState:
    """Executes the full multi-agent diagnostic graph and synchronizes results into database tables."""
    session_id = initial_state.diagnostic_session_id
    config = {"configurable": {"thread_id": thread_id or session_id}}

    # Update session status to RUNNING in database
    try:
        session = DiagnosticSession.query.filter_by(id=session_id).first()
        if session:
            session.status = "RUNNING"
            session.current_stage = "DATA_QUALITY_ASSESSMENT"
            db.session.commit()
    except Exception as e:
        logger.warning(f"Could not update session initial status: {e}")

    try:
        # Invoke LangGraph
        result = diagnostic_graph.invoke(initial_state, config=config)

        # Ensure result is a DiagnosticState
        final_state = result if isinstance(result, DiagnosticState) else DiagnosticState(**result)

        # Synchronize database records
        _sync_database_records(final_state)
        return final_state

    except Exception as e:
        logger.error(f"Error during diagnostic graph execution: {e}", exc_info=True)
        try:
            session = DiagnosticSession.query.filter_by(id=session_id).first()
            if session:
                session.status = "FAILED"
                session.error_message = str(e)
                db.session.commit()
        except Exception:
            pass
        raise e


def _sync_database_records(state: DiagnosticState) -> None:
    """Persists all agent execution metrics, recommendations, and diagnostic reports to PostgreSQL."""
    try:
        session = DiagnosticSession.query.filter_by(id=state.diagnostic_session_id).first()
        if session:
            session.status = "COMPLETED"
            session.current_stage = "COMPLETED"
            session.completed_at = db.func.now()
            if state.report:
                session.summary_headline = state.report.executive_summary[:250]

        # 1. Persist Agent Executions
        for exec_info in state.agent_executions:
            agent_exec = AgentExecution(
                diagnostic_session_id=state.diagnostic_session_id,
                agent_name=exec_info.get("agent_name", "UNKNOWN_AGENT"),
                status=exec_info.get("status", "SUCCESS"),
                execution_time_ms=exec_info.get("duration_ms", 0.0),
                output_payload=exec_info.get("details", {}),
            )
            db.session.add(agent_exec)

        # 2. Persist Recommendations
        for rec in state.recommendations:
            rec_record = MaintenanceRecommendation(
                organization_id=state.organization_id,
                diagnostic_session_id=state.diagnostic_session_id,
                machine_id=state.machine_id,
                component_id=state.component_id,
                title=rec.title,
                suspected_issue=rec.suspected_issue,
                recommended_action=rec.recommended_action,
                priority=rec.priority,
                safety_requirements=rec.safety_requirements,
                supporting_evidence=rec.supporting_evidence,
                compliance_state=rec.compliance_state,
                approval_status="PENDING_REVIEW",
            )
            db.session.add(rec_record)

        # 3. Persist Diagnostic Report
        if state.report:
            rep = state.report
            report_record = DiagnosticReport(
                organization_id=state.organization_id,
                diagnostic_session_id=state.diagnostic_session_id,
                machine_id=state.machine_id,
                report_title=rep.title,
                executive_summary=rep.executive_summary,
                data_quality_assessment={"is_reliable": state.data_quality.is_reliable, "score": state.data_quality.overall_quality_score},
                condition_summary={"summary": rep.condition_summary},
                predictive_results={"summary": rep.prediction_summary},
                root_cause_analysis={"hypotheses": rep.root_cause_analysis},
                maintenance_recommendations=rep.maintenance_recommendations,
                safety_compliance_notes=rep.safety_compliance_notes,
                technical_limitations=rep.technical_limitations,
            )
            db.session.add(report_record)

        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to synchronize database records for session {state.diagnostic_session_id}: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass

