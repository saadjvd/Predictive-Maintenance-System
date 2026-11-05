"""PharmaPredict AI — Pilot Module Validation Schemas using Pydantic."""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class CreatePilotSchema(BaseModel):
    pilot_name: str = Field(..., min_length=3, max_length=150)
    site_id: str
    description: Optional[str] = None
    objectives: Optional[str] = None
    monitoring_mode: str = "SHADOW"
    planned_start_date: Optional[str] = None
    planned_end_date: Optional[str] = None
    evaluation_criteria: Dict[str, Any] = Field(default_factory=dict)
    target_kpis: Dict[str, Any] = Field(default_factory=dict)
    responsible_engineer_id: Optional[str] = None

    @field_validator("monitoring_mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ("SHADOW", "ADVISORY"):
            raise ValueError("monitoring_mode must be 'SHADOW' or 'ADVISORY'")
        return v


class UpdatePilotSchema(BaseModel):
    pilot_name: Optional[str] = None
    description: Optional[str] = None
    objectives: Optional[str] = None
    monitoring_mode: Optional[str] = None
    planned_start_date: Optional[str] = None
    planned_end_date: Optional[str] = None
    evaluation_criteria: Optional[Dict[str, Any]] = None
    target_kpis: Optional[Dict[str, Any]] = None
    responsible_engineer_id: Optional[str] = None


class AssignEquipmentSchema(BaseModel):
    machine_ids: List[str] = Field(..., min_length=1)
    monitoring_mode: str = "SHADOW"


class SubmitApprovalSchema(BaseModel):
    approval_type: str  # ENGINEERING, IT_OT_SECURITY, QUALITY_ASSURANCE, PLANT_DIRECTOR
    decision: str  # APPROVED, REJECTED, CHANGES_REQUESTED
    comments: Optional[str] = None
    signature_token: Optional[str] = None

    @field_validator("approval_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = ("ENGINEERING", "IT_OT_SECURITY", "QUALITY_ASSURANCE", "PLANT_DIRECTOR")
        if v not in allowed:
            raise ValueError(f"approval_type must be one of {allowed}")
        return v

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        allowed = ("APPROVED", "REJECTED", "CHANGES_REQUESTED")
        if v not in allowed:
            raise ValueError(f"decision must be one of {allowed}")
        return v


class SubmitEngineerFeedbackSchema(BaseModel):
    diagnostic_session_id: str
    anomaly_event_id: Optional[str] = None
    assessment: str  # ACCURATE, PARTIALLY_ACCURATE, INACCURATE, INSUFFICIENT_EVIDENCE, NOT_APPLICABLE
    verified_root_cause: Optional[str] = None
    inspection_findings: Optional[str] = None
    action_taken: Optional[str] = None
    actual_outcome: Optional[str] = None
    comments: Optional[str] = None
    false_alarm_flag: bool = False
    reference_label: str = "UNVERIFIED"


class ModelEvaluationSchema(BaseModel):
    machine_id: str
    model_name: str
    model_version: str
    evaluation_type: str = "OFFLINE_VALIDATION"
    metrics: Dict[str, Any] = Field(default_factory=dict)
    status: str = "CANDIDATE"
    previous_model_version: Optional[str] = None
