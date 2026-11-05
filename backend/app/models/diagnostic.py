import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    Index,
)
from sqlalchemy.orm import relationship
from app.extensions import db


def generate_uuid() -> str:
    return str(uuid.uuid4())


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class DiagnosticTriggerType:
    ANOMALY_ALARM = "ANOMALY_ALARM"
    MANUAL_ENGINEER = "MANUAL_ENGINEER"
    PREDICTIVE_RISK = "PREDICTIVE_RISK"
    SCHEDULED = "SCHEDULED"


class DiagnosticSessionStatus:
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    HALTED_DATA_QUALITY = "HALTED_DATA_QUALITY"
    CONCLUDED_NORMAL = "CONCLUDED_NORMAL"


class AgentName:
    DATA_QUALITY = "DATA_QUALITY_AGENT"
    CONDITION_MONITORING = "CONDITION_MONITORING_AGENT"
    FAILURE_PREDICTION = "FAILURE_PREDICTION_AGENT"
    ROOT_CAUSE = "ROOT_CAUSE_ANALYSIS_AGENT"
    MAINTENANCE_RECOMMENDATION = "MAINTENANCE_RECOMMENDATION_AGENT"
    COMPLIANCE_SAFETY = "COMPLIANCE_SAFETY_AGENT"
    REPORTING = "REPORTING_AGENT"


class RecommendationPriority:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SafetyComplianceState:
    ALLOWED_FOR_REVIEW = "ALLOWED_FOR_REVIEW"
    REQUIRES_ADDITIONAL_APPROVAL = "REQUIRES_ADDITIONAL_APPROVAL"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class RecommendationApprovalStatus:
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_INVESTIGATION = "NEEDS_INVESTIGATION"
    CLOSED = "CLOSED"


# =============================================================================
# 1. DIAGNOSTIC SESSIONS & AGENT EXECUTIONS
# =============================================================================

class DiagnosticSession(db.Model):
    """End-to-end multi-agent diagnostic run for an equipment asset."""
    __tablename__ = "diagnostic_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String(36), ForeignKey("machine_components.id", ondelete="SET NULL"), nullable=True)

    trigger_type = Column(String(50), default=DiagnosticTriggerType.MANUAL_ENGINEER, nullable=False)
    trigger_event_id = Column(String(100), nullable=True)  # Anomaly ID or Alert ID if triggered automatically
    status = Column(String(50), default=DiagnosticSessionStatus.INITIALIZING, nullable=False, index=True)
    current_stage = Column(String(50), default="INIT", nullable=False)

    summary_headline = Column(String(255), nullable=True)
    checkpoint_state = Column(JSON, nullable=True)  # LangGraph serialized checkpoint snapshot
    error_message = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    machine = relationship("Machine")
    component = relationship("MachineComponent")
    executions = relationship("AgentExecution", back_populates="session", cascade="all, delete-orphan", lazy="dynamic")
    recommendations = relationship("MaintenanceRecommendation", back_populates="session", cascade="all, delete-orphan", lazy="dynamic")
    report = relationship("DiagnosticReport", back_populates="session", uselist=False, cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "machine_name": self.machine.equipment_name if self.machine else "Unknown",
            "component_id": self.component_id,
            "trigger_type": self.trigger_type,
            "trigger_event_id": self.trigger_event_id,
            "status": self.status,
            "current_stage": self.current_stage,
            "summary_headline": self.summary_headline,
            "error_message": self.error_message,
            "created_by": self.created_by,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "has_report": self.report is not None,
            "recommendation_count": self.recommendations.count() if hasattr(self.recommendations, "count") else len(self.recommendations or []),
        }


class AgentExecution(db.Model):
    """Discrete trace and audit record for each agent node in the LangGraph workflow."""
    __tablename__ = "agent_executions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    diagnostic_session_id = Column(String(36), ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False, index=True)

    status = Column(String(30), default="STARTED", nullable=False)  # STARTED, SUCCESS, SKIPPED, FAILED
    execution_time_ms = Column(Float, nullable=True)
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    error_details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("DiagnosticSession", back_populates="executions")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "diagnostic_session_id": self.diagnostic_session_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "execution_time_ms": round(self.execution_time_ms, 2) if self.execution_time_ms else None,
            "output_payload": self.output_payload or {},
            "error_details": self.error_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# 2. KNOWLEDGE DOCUMENTS & VECTOR EMBEDDINGS (RAG)
# =============================================================================

class KnowledgeDocument(db.Model):
    """Technical knowledge documents (OEM manuals, SOPs, troubleshooting guides)."""
    __tablename__ = "knowledge_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    category_id = Column(String(36), ForeignKey("equipment_categories.id", ondelete="SET NULL"), nullable=True)

    title = Column(String(255), nullable=False)
    document_type = Column(String(50), default="SOP", nullable=False)  # MANUAL, SOP, TROUBLESHOOTING_GUIDE, ALARM_REF
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    component_type = Column(String(100), nullable=True)
    version = Column(String(50), default="1.0", nullable=False)
    approval_status = Column(String(30), default="APPROVED", nullable=False)  # DRAFT, APPROVED, ARCHIVED

    source_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)
    is_standard = Column(Boolean, default=False, nullable=False)  # True = standard pharmaceutical knowledge shared across orgs

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "category_id": self.category_id,
            "title": self.title,
            "document_type": self.document_type,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "component_type": self.component_type,
            "version": self.version,
            "approval_status": self.approval_status,
            "source_filename": self.source_filename,
            "is_standard": self.is_standard,
            "chunk_count": self.chunks.count() if hasattr(self.chunks, "count") else len(self.chunks or []),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DocumentChunk(db.Model):
    """Chunked passages with metadata and vector embeddings."""
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)

    chunk_index = Column(Integer, nullable=False, default=0)
    content = Column(Text, nullable=False)
    metadata_payload = Column(JSON, nullable=True)  # page_number, section_header, keywords
    embedding = Column(JSON, nullable=True)  # Portable vector float array representation

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunk_doc_index", "document_id", "chunk_index"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "document_title": self.document.title if self.document else None,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "metadata": self.metadata_payload or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# 3. MAINTENANCE RECOMMENDATIONS & HUMAN APPROVAL
# =============================================================================

class MaintenanceRecommendation(db.Model):
    """Actionable, evidence-backed maintenance recommendation requiring human engineer authorization."""
    __tablename__ = "maintenance_recommendations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    diagnostic_session_id = Column(String(36), ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String(36), ForeignKey("machine_components.id", ondelete="SET NULL"), nullable=True)

    title = Column(String(255), nullable=False)
    suspected_issue = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=False)
    priority = Column(String(20), default=RecommendationPriority.MEDIUM, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL

    supporting_evidence = Column(JSON, nullable=True)  # Anomaly scores, sensor slopes, cited documents
    safety_requirements = Column(JSON, nullable=True)  # LOTO, Electrical Isolation, Cleanroom PPE, GMP log
    compliance_state = Column(String(40), default=SafetyComplianceState.ALLOWED_FOR_REVIEW, nullable=False)
    compliance_notes = Column(Text, nullable=True)

    approval_status = Column(String(30), default=RecommendationApprovalStatus.PENDING_REVIEW, nullable=False, index=True)
    engineer_notes = Column(Text, nullable=True)
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("DiagnosticSession", back_populates="recommendations")
    machine = relationship("Machine")
    component = relationship("MachineComponent")
    approvals = relationship("RecommendationApproval", back_populates="recommendation", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "diagnostic_session_id": self.diagnostic_session_id,
            "machine_id": self.machine_id,
            "machine_name": self.machine.equipment_name if self.machine else "Unknown",
            "component_id": self.component_id,
            "title": self.title,
            "suspected_issue": self.suspected_issue,
            "recommended_action": self.recommended_action,
            "priority": self.priority,
            "supporting_evidence": self.supporting_evidence or {},
            "safety_requirements": self.safety_requirements or [],
            "compliance_state": self.compliance_state,
            "compliance_notes": self.compliance_notes,
            "approval_status": self.approval_status,
            "engineer_notes": self.engineer_notes,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RecommendationApproval(db.Model):
    """Immutable audit trail of human maintenance engineer review decisions."""
    __tablename__ = "recommendation_approvals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    recommendation_id = Column(String(36), ForeignKey("maintenance_recommendations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)

    decision = Column(String(30), nullable=False)  # APPROVED, REJECTED, NEEDS_INVESTIGATION
    comments = Column(Text, nullable=True)
    confirmed_root_cause = Column(Text, nullable=True)
    work_order_reference = Column(String(100), nullable=True)  # Reference to external CMMS work order

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    recommendation = relationship("MaintenanceRecommendation", back_populates="approvals")
    user = relationship("User")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "recommendation_id": self.recommendation_id,
            "user_id": self.user_id,
            "user_name": self.user.full_name if self.user else None,
            "decision": self.decision,
            "comments": self.comments,
            "confirmed_root_cause": self.confirmed_root_cause,
            "work_order_reference": self.work_order_reference,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# 4. DIAGNOSTIC REPORTS & EVALUATION
# =============================================================================

class DiagnosticReport(db.Model):
    """Comprehensive diagnostic dossier compiled by Reporting Agent for engineering review."""
    __tablename__ = "diagnostic_reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    diagnostic_session_id = Column(String(36), ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)

    report_title = Column(String(255), nullable=False)
    executive_summary = Column(Text, nullable=False)
    data_quality_assessment = Column(JSON, nullable=True)
    condition_summary = Column(JSON, nullable=True)
    predictive_results = Column(JSON, nullable=True)
    root_cause_analysis = Column(JSON, nullable=True)
    maintenance_recommendations = Column(JSON, nullable=True)
    safety_compliance_notes = Column(JSON, nullable=True)
    technical_limitations = Column(JSON, nullable=True)

    version_number = Column(Integer, default=1, nullable=False)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("DiagnosticSession", back_populates="report")
    machine = relationship("Machine")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "diagnostic_session_id": self.diagnostic_session_id,
            "machine_id": self.machine_id,
            "machine_name": self.machine.equipment_name if self.machine else "Unknown",
            "report_title": self.report_title,
            "title": self.report_title,
            "executive_summary": self.executive_summary,
            "data_quality_assessment": self.data_quality_assessment or {},
            "condition_summary": self.condition_summary or {},
            "predictive_results": self.predictive_results or {},
            "root_cause_analysis": self.root_cause_analysis or {},
            "maintenance_recommendations": self.maintenance_recommendations or [],
            "safety_compliance_notes": self.safety_compliance_notes or [],
            "technical_limitations": self.technical_limitations or [],
            "version_number": self.version_number,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
        }


class AgentEvaluationResult(db.Model):
    """LangSmith and deterministic benchmark evaluation results for AI workflows."""
    __tablename__ = "agent_evaluation_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    diagnostic_session_id = Column(String(36), ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=True, index=True)

    dataset_name = Column(String(100), nullable=False)
    tool_selection_score = Column(Float, nullable=True)  # 0.0 to 1.0
    retrieval_relevance_score = Column(Float, nullable=True)
    safety_rule_compliance_score = Column(Float, nullable=True)
    hallucination_rate = Column(Float, nullable=True)  # 0.0 (no unsupported claims)
    overall_fidelity_score = Column(Float, nullable=True)

    langsmith_run_id = Column(String(100), nullable=True)
    evaluation_metadata = Column(JSON, nullable=True)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "diagnostic_session_id": self.diagnostic_session_id,
            "dataset_name": self.dataset_name,
            "tool_selection_score": round(self.tool_selection_score, 3) if self.tool_selection_score is not None else None,
            "retrieval_relevance_score": round(self.retrieval_relevance_score, 3) if self.retrieval_relevance_score is not None else None,
            "safety_rule_compliance_score": round(self.safety_rule_compliance_score, 3) if self.safety_rule_compliance_score is not None else None,
            "hallucination_rate": round(self.hallucination_rate, 3) if self.hallucination_rate is not None else None,
            "overall_fidelity_score": round(self.overall_fidelity_score, 3) if self.overall_fidelity_score is not None else None,
            "langsmith_run_id": self.langsmith_run_id,
            "evaluation_metadata": self.evaluation_metadata or {},
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
        }

