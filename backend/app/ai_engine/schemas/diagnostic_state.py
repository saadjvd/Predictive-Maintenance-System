import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class DataQualityAssessment(BaseModel):
    quality_state: str = "GOOD"
    can_continue: bool = True
    is_reliable: bool = True
    overall_quality_score: float = 1.0
    data_quality_status: str = "GOOD"
    affected_signals: List[str] = Field(default_factory=list)
    issues_detected: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


class ConditionAssessment(BaseModel):
    condition_state: str = "NORMAL"
    severity: str = "INFO"
    has_anomaly: bool = False
    health_score: float = 100.0
    anomaly_score: float = 0.0
    operating_state: str = "RUNNING"
    affected_signals: List[str] = Field(default_factory=list)
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    active_anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    baseline_deviations: Dict[str, float] = Field(default_factory=dict)
    summary: str = "Equipment operating within approved baseline envelopes."


class PredictionAssessment(BaseModel):
    model_status: str = "PREDICTION_UNAVAILABLE"
    is_available: bool = False
    is_eligible: bool = False
    calibrated_probability: Optional[float] = None
    risk_category: str = "LOW"
    rul_hours: Optional[float] = None
    estimated_rul_hours: Optional[float] = None
    rul_confidence_lower: Optional[float] = None
    rul_confidence_upper: Optional[float] = None
    rul_confidence_interval: Optional[List[float]] = None
    rul_method: Optional[str] = None
    model_version: Optional[str] = None
    rationale: str = "No calibrated prediction models active for this asset."
    evidence_items: List[Dict[str, Any]] = Field(default_factory=list)


class RetrievedEvidenceItem(BaseModel):
    document_id: str
    title: str
    document_type: str = "SOP"
    section: Optional[str] = None
    page_number: Optional[int] = None
    content_excerpt: str
    relevance_score: float = 0.0
    source_filename: str = ""


class RootCauseHypothesis(BaseModel):
    hypothesis_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    suspected_cause: str
    hypothesis_status: str = "SUPPORTED_HYPOTHESIS"  # CONFIRMED, SUPPORTED_HYPOTHESIS, POSSIBLE_CAUSE, INSUFFICIENT_EVIDENCE
    confidence_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    supporting_observations: List[str] = Field(default_factory=list)
    cited_documents: List[str] = Field(default_factory=list)
    recommended_verification_steps: List[str] = Field(default_factory=list)
    uncertainty_description: str = ""


class MaintenanceRecommendationSchema(BaseModel):
    recommendation_id: str
    title: str
    suspected_issue: str
    recommended_action: str
    priority: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    component_type: Optional[str] = None
    safety_requirements: List[str] = Field(default_factory=list)
    supporting_evidence: Dict[str, Any] = Field(default_factory=dict)
    compliance_state: str = "ALLOWED_FOR_REVIEW"
    requires_engineer_approval: bool = True


class ComplianceSafetyAssessment(BaseModel):
    compliance_state: str = "ALLOWED_FOR_REVIEW"  # ALLOWED_FOR_REVIEW, REQUIRES_ADDITIONAL_APPROVAL, BLOCKED, INSUFFICIENT_INFORMATION
    deterministic_checks_passed: bool = True
    loto_required: bool = False
    electrical_isolation_required: bool = False
    cleanroom_ppe_required: bool = False
    gmp_change_control_required: bool = False
    safety_notes: List[str] = Field(default_factory=list)
    blocked_reasons: List[str] = Field(default_factory=list)


class DiagnosticReportSchema(BaseModel):
    report_id: str
    title: str
    executive_summary: str
    condition_summary: str
    prediction_summary: str
    root_cause_analysis: List[str] = Field(default_factory=list)
    maintenance_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    safety_compliance_notes: List[str] = Field(default_factory=list)
    technical_limitations: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DiagnosticState(BaseModel):
    """Immutable shared state container passed through all LangGraph agent nodes."""
    organization_id: str
    machine_id: str
    component_id: Optional[str] = None
    diagnostic_session_id: str
    trigger_type: str = "MANUAL_ENGINEER"
    trigger_event_id: Optional[str] = None

    # Agent node results
    data_quality: DataQualityAssessment = Field(default_factory=DataQualityAssessment)
    condition: ConditionAssessment = Field(default_factory=ConditionAssessment)
    prediction: PredictionAssessment = Field(default_factory=PredictionAssessment)
    retrieved_documents: List[RetrievedEvidenceItem] = Field(default_factory=list)
    hypotheses: List[RootCauseHypothesis] = Field(default_factory=list)
    recommendations: List[MaintenanceRecommendationSchema] = Field(default_factory=list)
    compliance: ComplianceSafetyAssessment = Field(default_factory=ComplianceSafetyAssessment)
    report: Optional[DiagnosticReportSchema] = None

    # Execution control & telemetry
    current_stage: str = "INITIALIZING"
    should_stop: bool = False
    stop_reason: Optional[str] = None
    agent_errors: List[str] = Field(default_factory=list)
    agent_executions: List[Dict[str, Any]] = Field(default_factory=list)
    execution_metadata: Dict[str, Any] = Field(default_factory=dict)
