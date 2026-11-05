"""Service layer for multi-agent equipment diagnostics."""
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.extensions import db
from app.models.diagnostic import (
    DiagnosticSession,
    AgentExecution,
    MaintenanceRecommendation,
    DiagnosticReport,
    AgentEvaluationResult,
)
from app.models.equipment import Machine
from app.ai_engine.schemas.diagnostic_state import DiagnosticState
from app.ai_engine.graph.builder import run_diagnostic_workflow
from app.ai_engine.evaluation.evaluators import DiagnosticEvaluators

logger = logging.getLogger(__name__)


class DiagnosticService:
    """Orchestrates diagnostic workflows, session tracking, and engineer reviews."""

    @classmethod
    def start_diagnostic_session(
        cls,
        organization_id: str,
        machine_id: str,
        component_id: Optional[str] = None,
        trigger_type: str = "MANUAL_ENGINEER",
        trigger_event_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initiates a multi-agent diagnostic run for an equipment asset."""
        # 1. Validate equipment exists and belongs to organization
        equipment = Machine.query.filter_by(
            id=machine_id, organization_id=organization_id
        ).first()
        if not equipment:
            raise ValueError(f"Equipment with ID {machine_id} was not found in this organization.")

        # 2. Create DiagnosticSession record
        session = DiagnosticSession(
            organization_id=organization_id,
            machine_id=machine_id,
            component_id=component_id,
            trigger_type=trigger_type,
            trigger_event_id=trigger_event_id,
            status="INITIALIZING",
            current_stage="INITIALIZING",
            created_by=user_id,
        )
        db.session.add(session)
        db.session.commit()

        # 3. Build initial diagnostic state
        initial_state = DiagnosticState(
            organization_id=organization_id,
            machine_id=machine_id,
            component_id=component_id,
            diagnostic_session_id=session.id,
            trigger_type=trigger_type,
            trigger_event_id=trigger_event_id,
        )

        # 4. Execute LangGraph workflow
        final_state = run_diagnostic_workflow(initial_state)

        # 5. Run automated compliance & hallucination evaluations
        try:
            DiagnosticEvaluators.run_all_evaluations(final_state, session_id=session.id)
        except Exception as e:
            logger.warning(f"Could not complete automated evaluations: {e}")

        return cls.get_session(session.id, organization_id)

    @classmethod
    def get_session(cls, session_id: str, organization_id: str) -> Dict[str, Any]:
        """Retrieves complete diagnostic session details including report and recommendations."""
        session = DiagnosticSession.query.filter_by(
            id=session_id, organization_id=organization_id
        ).first()
        if not session:
            raise ValueError(f"Diagnostic session {session_id} not found.")

        # Fetch child items
        executions = AgentExecution.query.filter_by(diagnostic_session_id=session.id).order_by(AgentExecution.created_at.asc()).all()
        recommendations = MaintenanceRecommendation.query.filter_by(diagnostic_session_id=session.id).all()
        report = DiagnosticReport.query.filter_by(diagnostic_session_id=session.id).first()
        evaluations = AgentEvaluationResult.query.filter_by(diagnostic_session_id=session.id).all()

        return {
            "session": session.to_dict(),
            "agent_executions": [e.to_dict() for e in executions],
            "recommendations": [r.to_dict() for r in recommendations],
            "report": report.to_dict() if report else None,
            "evaluations": [ev.to_dict() for ev in evaluations],
        }

    @classmethod
    def get_session_status(cls, session_id: str, organization_id: str) -> Dict[str, Any]:
        """Lightweight status check for polling."""
        session = DiagnosticSession.query.filter_by(
            id=session_id, organization_id=organization_id
        ).first()
        if not session:
            raise ValueError(f"Diagnostic session {session_id} not found.")
        return {
            "id": session.id,
            "status": session.status,
            "current_stage": session.current_stage,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "error_message": session.error_message,
        }

    @classmethod
    def get_session_report(cls, session_id: str, organization_id: str) -> Dict[str, Any]:
        """Fetches the synthesized diagnostic report."""
        report = DiagnosticReport.query.filter_by(
            diagnostic_session_id=session_id, organization_id=organization_id
        ).first()
        if not report:
            raise ValueError(f"Diagnostic report for session {session_id} not found.")
        return report.to_dict()

    @classmethod
    def get_agent_executions(cls, session_id: str, organization_id: str) -> List[Dict[str, Any]]:
        """Returns step-by-step logs for all 7 agents in a session."""
        session = DiagnosticSession.query.filter_by(
            id=session_id, organization_id=organization_id
        ).first()
        if not session:
            raise ValueError(f"Diagnostic session {session_id} not found.")
        executions = AgentExecution.query.filter_by(diagnostic_session_id=session.id).order_by(AgentExecution.created_at.asc()).all()
        return [e.to_dict() for e in executions]

    @classmethod
    def review_session(
        cls,
        session_id: str,
        organization_id: str,
        user_id: str,
        review_status: str,
        review_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Human-in-the-loop review of an entire diagnostic investigation."""
        session = DiagnosticSession.query.filter_by(
            id=session_id, organization_id=organization_id
        ).first()
        if not session:
            raise ValueError(f"Diagnostic session {session_id} not found.")

        valid_statuses = {"APPROVED", "REJECTED", "NEEDS_INVESTIGATION", "CLOSED"}
        if review_status not in valid_statuses:
            raise ValueError(f"Invalid review status. Allowed: {list(valid_statuses)}")

        meta = session.checkpoint_state or {}
        meta["human_review"] = {
            "reviewer_user_id": user_id,
            "status": review_status,
            "notes": review_notes or "",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        session.checkpoint_state = meta
        db.session.commit()
        return session.to_dict()

    @classmethod
    def list_sessions(
        cls,
        organization_id: str,
        machine_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Lists recent diagnostic sessions."""
        query = DiagnosticSession.query.filter_by(organization_id=organization_id)
        if machine_id:
            query = query.filter_by(machine_id=machine_id)
        sessions = query.order_by(DiagnosticSession.created_at.desc()).limit(limit).all()
        return [s.to_dict() for s in sessions]
