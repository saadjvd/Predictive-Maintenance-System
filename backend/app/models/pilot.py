"""PharmaPredict AI — Phase 9 Factory Pilot Models.

Manages the lifecycle, equipment readiness checklists, multi-sign-off approvals,
shadow-mode telemetry monitoring, engineer diagnostic feedback, model offline evaluation,
and go/no-go pilot reporting for pharmaceutical facilities.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Float,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.extensions import db


def generate_uuid() -> str:
    return str(uuid.uuid4())


class PilotLifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    READINESS_REVIEW = "READINESS_REVIEW"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MonitoringMode(str, Enum):
    SHADOW = "SHADOW"
    ADVISORY = "ADVISORY"


class PilotApprovalType(str, Enum):
    ENGINEERING = "ENGINEERING"
    IT_OT_SECURITY = "IT_OT_SECURITY"
    QUALITY_ASSURANCE = "QUALITY_ASSURANCE"
    PLANT_DIRECTOR = "PLANT_DIRECTOR"


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class ReadinessCheckStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    WAIVED = "WAIVED"


class EngineerFeedbackAssessment(str, Enum):
    ACCURATE = "ACCURATE"
    PARTIALLY_ACCURATE = "PARTIALLY_ACCURATE"
    INACCURATE = "INACCURATE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class GoNoGoRecommendation(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"
    EXTEND_SHADOW_PILOT = "EXTEND_SHADOW_PILOT"


class FactoryPilot(db.Model):
    """Represents a controlled pharmaceutical factory pilot program."""
    __tablename__ = "factory_pilots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id = Column(String(36), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)

    pilot_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    objectives = Column(Text, nullable=True)

    status = Column(String(50), default=PilotLifecycleStatus.DRAFT.value, nullable=False, index=True)
    monitoring_mode = Column(String(50), default=MonitoringMode.SHADOW.value, nullable=False)

    evaluation_criteria = Column(JSON, default=dict, nullable=False)
    target_kpis = Column(JSON, default=dict, nullable=False)

    responsible_engineer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    engineering_approver_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    security_approver_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    qa_approver_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    planned_start_date = Column(DateTime, nullable=True)
    planned_end_date = Column(DateTime, nullable=True)
    actual_start_date = Column(DateTime, nullable=True)
    actual_end_date = Column(DateTime, nullable=True)

    created_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    equipment_links = relationship("PilotEquipment", back_populates="pilot", cascade="all, delete-orphan", lazy="dynamic")
    approvals = relationship("PilotApproval", back_populates="pilot", cascade="all, delete-orphan", lazy="dynamic")
    readiness_checks = relationship("PilotReadinessCheck", back_populates="pilot", cascade="all, delete-orphan", lazy="dynamic")
    feedbacks = relationship("PilotEngineerFeedback", back_populates="pilot", cascade="all, delete-orphan", lazy="dynamic")
    model_evaluations = relationship("PilotModelEvaluation", back_populates="pilot", cascade="all, delete-orphan", lazy="dynamic")
    agent_evaluations = relationship("PilotAgentEvaluation", back_populates="pilot", cascade="all, delete-orphan", lazy="dynamic")
    reports = relationship("PilotReport", back_populates="pilot", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "site_id": self.site_id,
            "pilot_name": self.pilot_name,
            "description": self.description,
            "objectives": self.objectives,
            "status": self.status,
            "monitoring_mode": self.monitoring_mode,
            "evaluation_criteria": self.evaluation_criteria,
            "target_kpis": self.target_kpis,
            "responsible_engineer_id": self.responsible_engineer_id,
            "planned_start_date": self.planned_start_date.isoformat() if self.planned_start_date else None,
            "planned_end_date": self.planned_end_date.isoformat() if self.planned_end_date else None,
            "actual_start_date": self.actual_start_date.isoformat() if self.actual_start_date else None,
            "actual_end_date": self.actual_end_date.isoformat() if self.actual_end_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class PilotEquipment(db.Model):
    """Candidate equipment enrolled in a controlled factory pilot."""
    __tablename__ = "pilot_equipment"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pilot_id = Column(String(36), ForeignKey("factory_pilots.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)

    monitoring_mode = Column(String(50), default=MonitoringMode.SHADOW.value, nullable=False)
    readiness_status = Column(String(50), default="NOT_EVALUATED", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    pilot = relationship("FactoryPilot", back_populates="equipment_links")
    machine = relationship("Machine", lazy="joined")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pilot_id": self.pilot_id,
            "machine_id": self.machine_id,
            "machine_name": self.machine.equipment_name if self.machine else None,
            "asset_code": self.machine.asset_code if self.machine else None,
            "monitoring_mode": self.monitoring_mode,
            "readiness_status": self.readiness_status,
            "is_active": self.is_active,
            "assigned_at": self.assigned_at.isoformat(),
        }


class PilotApproval(db.Model):
    """Site-level multi-department authorization record for factory pilot activation."""
    __tablename__ = "pilot_approvals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pilot_id = Column(String(36), ForeignKey("factory_pilots.id", ondelete="CASCADE"), nullable=False, index=True)
    approver_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    approval_type = Column(String(50), nullable=False)  # ENGINEERING, IT_OT_SECURITY, QUALITY_ASSURANCE, PLANT_DIRECTOR
    decision = Column(String(50), default=ApprovalDecision.APPROVED.value, nullable=False)
    comments = Column(Text, nullable=True)

    signature_hash = Column(String(128), nullable=False)  # 21 CFR Part 11 cryptographic token
    signed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    pilot = relationship("FactoryPilot", back_populates="approvals")
    approver = relationship("User", lazy="joined")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pilot_id": self.pilot_id,
            "approver_id": self.approver_id,
            "approver_name": self.approver.full_name if self.approver else None,
            "approval_type": self.approval_type,
            "decision": self.decision,
            "comments": self.comments,
            "signature_hash": self.signature_hash,
            "signed_at": self.signed_at.isoformat(),
        }


class PilotReadinessCheck(db.Model):
    """Specific technical/operational readiness criterion for equipment in a pilot."""
    __tablename__ = "pilot_readiness_checks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pilot_id = Column(String(36), ForeignKey("factory_pilots.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=True, index=True)

    check_category = Column(String(64), nullable=False)  # REGISTRATION, CONNECTIVITY, DATA_QUALITY, BASELINES, SOP, SECURITY, QA
    check_name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(String(50), default=ReadinessCheckStatus.PENDING.value, nullable=False)
    evidence_summary = Column(Text, nullable=True)

    reviewer_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    pilot = relationship("FactoryPilot", back_populates="readiness_checks")
    reviewer = relationship("User", lazy="joined")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pilot_id": self.pilot_id,
            "machine_id": self.machine_id,
            "check_category": self.check_category,
            "check_name": self.check_name,
            "description": self.description,
            "status": self.status,
            "evidence_summary": self.evidence_summary,
            "reviewer_id": self.reviewer_id,
            "reviewer_name": self.reviewer.full_name if self.reviewer else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class PilotEngineerFeedback(db.Model):
    """Feedback from plant maintenance engineers on AI diagnostic and anomaly sessions."""
    __tablename__ = "pilot_engineer_feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pilot_id = Column(String(36), ForeignKey("factory_pilots.id", ondelete="CASCADE"), nullable=False, index=True)
    diagnostic_session_id = Column(String(36), ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    anomaly_event_id = Column(String(36), ForeignKey("anomaly_events.id", ondelete="SET NULL"), nullable=True)
    engineer_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    assessment = Column(String(50), nullable=False)  # ACCURATE, PARTIALLY_ACCURATE, INACCURATE, INSUFFICIENT_EVIDENCE, NOT_APPLICABLE
    verified_root_cause = Column(String(255), nullable=True)
    inspection_findings = Column(Text, nullable=True)
    action_taken = Column(String(255), nullable=True)
    actual_outcome = Column(String(255), nullable=True)
    comments = Column(Text, nullable=True)

    false_alarm_flag = Column(Boolean, default=False, nullable=False)
    reference_label = Column(String(50), default="UNVERIFIED", nullable=False)  # TRUE_POSITIVE, FALSE_POSITIVE, FALSE_NEGATIVE, TRUE_NEGATIVE, UNVERIFIED

    feedback_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    pilot = relationship("FactoryPilot", back_populates="feedbacks")
    engineer = relationship("User", lazy="joined")
    diagnostic_session = relationship("DiagnosticSession", lazy="joined")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pilot_id": self.pilot_id,
            "diagnostic_session_id": self.diagnostic_session_id,
            "anomaly_event_id": self.anomaly_event_id,
            "engineer_id": self.engineer_id,
            "engineer_name": self.engineer.full_name if self.engineer else None,
            "assessment": self.assessment,
            "verified_root_cause": self.verified_root_cause,
            "inspection_findings": self.inspection_findings,
            "action_taken": self.action_taken,
            "actual_outcome": self.actual_outcome,
            "comments": self.comments,
            "false_alarm_flag": self.false_alarm_flag,
            "reference_label": self.reference_label,
            "feedback_timestamp": self.feedback_timestamp.isoformat(),
        }


class PilotModelEvaluation(db.Model):
    """Offline validation, candidate benchmark, and rollback tracking for predictive models."""
    __tablename__ = "pilot_model_evaluations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pilot_id = Column(String(36), ForeignKey("factory_pilots.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)

    model_name = Column(String(150), nullable=False)
    model_version = Column(String(64), nullable=False)
    evaluation_type = Column(String(64), default="OFFLINE_VALIDATION", nullable=False)

    metrics = Column(JSON, default=dict, nullable=False)
    status = Column(String(50), default="CANDIDATE", nullable=False)  # CANDIDATE, APPROVED, REJECTED, ROLLED_BACK
    previous_model_version = Column(String(64), nullable=True)

    evaluated_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    pilot = relationship("FactoryPilot", back_populates="model_evaluations")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pilot_id": self.pilot_id,
            "machine_id": self.machine_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "evaluation_type": self.evaluation_type,
            "metrics": self.metrics,
            "status": self.status,
            "previous_model_version": self.previous_model_version,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class PilotAgentEvaluation(db.Model):
    """Empirical diagnostic accuracy evaluation metrics for LangGraph agents."""
    __tablename__ = "pilot_agent_evaluations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pilot_id = Column(String(36), ForeignKey("factory_pilots.id", ondelete="CASCADE"), nullable=False, index=True)
    diagnostic_session_id = Column(String(36), ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False)

    agent_name = Column(String(64), nullable=False)
    routing_correctness = Column(Float, default=1.0, nullable=False)
    tool_selection_accuracy = Column(Float, default=1.0, nullable=False)
    evidence_completeness = Column(Float, default=1.0, nullable=False)
    hypothesis_relevance = Column(Float, default=1.0, nullable=False)
    safety_compliance_score = Column(Float, default=1.0, nullable=False)

    evaluation_notes = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    pilot = relationship("FactoryPilot", back_populates="agent_evaluations")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pilot_id": self.pilot_id,
            "diagnostic_session_id": self.diagnostic_session_id,
            "agent_name": self.agent_name,
            "routing_correctness": self.routing_correctness,
            "tool_selection_accuracy": self.tool_selection_accuracy,
            "evidence_completeness": self.evidence_completeness,
            "hypothesis_relevance": self.hypothesis_relevance,
            "safety_compliance_score": self.safety_compliance_score,
            "evaluation_notes": self.evaluation_notes,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


class PilotReport(db.Model):
    """Formal audit report and executive go/no-go determination for a factory pilot."""
    __tablename__ = "pilot_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pilot_id = Column(String(36), ForeignKey("factory_pilots.id", ondelete="CASCADE"), nullable=False, index=True)

    report_type = Column(String(64), default="FINAL_PILOT_REPORT", nullable=False)
    executive_summary = Column(Text, nullable=False)
    metrics_summary = Column(JSON, default=dict, nullable=False)
    findings_and_deviations = Column(Text, nullable=True)

    go_no_go_recommendation = Column(String(50), default=GoNoGoRecommendation.GO.value, nullable=False)
    limitations_and_disclaimers = Column(Text, nullable=True)

    generated_by_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    pilot = relationship("FactoryPilot", back_populates="reports")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pilot_id": self.pilot_id,
            "report_type": self.report_type,
            "executive_summary": self.executive_summary,
            "metrics_summary": self.metrics_summary,
            "findings_and_deviations": self.findings_and_deviations,
            "go_no_go_recommendation": self.go_no_go_recommendation,
            "limitations_and_disclaimers": self.limitations_and_disclaimers,
            "generated_at": self.generated_at.isoformat(),
        }
