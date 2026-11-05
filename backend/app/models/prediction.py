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

class FailureVerificationStatus:
    CONFIRMED = "CONFIRMED"
    SUSPECTED = "SUSPECTED"
    PREVENTIVE_MAINTENANCE = "PREVENTIVE_MAINTENANCE"
    INSPECTION = "INSPECTION"
    PLANNED_SHUTDOWN = "PLANNED_SHUTDOWN"
    UNVERIFIED = "UNVERIFIED"

    ALL_STATUSES = [
        CONFIRMED,
        SUSPECTED,
        PREVENTIVE_MAINTENANCE,
        INSPECTION,
        PLANNED_SHUTDOWN,
        UNVERIFIED,
    ]


class PredictiveModelLifecycle:
    DRAFT = "DRAFT"
    TRAINING = "TRAINING"
    TRAINED = "TRAINED"
    UNDER_VALIDATION = "UNDER_VALIDATION"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"

    ALL_STATUSES = [
        DRAFT,
        TRAINING,
        TRAINED,
        UNDER_VALIDATION,
        APPROVED,
        ACTIVE,
        REJECTED,
        RETIRED,
    ]


class PredictionEligibilityState:
    NOT_CONFIGURED = "NOT_CONFIGURED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    TRAINING_ELIGIBLE = "TRAINING_ELIGIBLE"
    UNDER_VALIDATION = "UNDER_VALIDATION"
    PREDICTION_READY = "PREDICTION_READY"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    DATA_QUALITY_BLOCKED = "DATA_QUALITY_BLOCKED"


class PredictiveRiskCategory:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PredictiveAlertStatus:
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


# =============================================================================
# FAILURE MODE CATALOG (Requirement 6)
# =============================================================================

class FailureMode(db.Model):
    """Catalog of equipment and component failure modes in pharmaceutical manufacturing."""
    __tablename__ = "failure_modes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    category_id = Column(String(36), ForeignKey("equipment_categories.id", ondelete="SET NULL"), nullable=True)

    code = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    component_type = Column(String(100), nullable=True)  # Motor, Bearing, Gearbox, Pneumatics, etc.
    description = Column(Text, nullable=True)
    severity_impact = Column(String(20), default="HIGH", nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    evidence_requirements = Column(JSON, nullable=True)  # Required sensors / diagnostic criteria
    relevant_signals = Column(JSON, nullable=True)  # List of relevant standard signal codes
    applicable_model_families = Column(JSON, nullable=True)  # Classification, Survival, RUL
    is_standard = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_fm_org_code", "organization_id", "code"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "category_id": self.category_id,
            "code": self.code,
            "name": self.name,
            "component_type": self.component_type,
            "description": self.description,
            "severity_impact": self.severity_impact,
            "evidence_requirements": self.evidence_requirements or {},
            "relevant_signals": self.relevant_signals or [],
            "applicable_model_families": self.applicable_model_families or [],
            "is_standard": self.is_standard,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# EQUIPMENT FAILURE RECORDS (Requirement 5)
# =============================================================================

class FailureRecord(db.Model):
    """Historical machine and component failure and maintenance records."""
    __tablename__ = "failure_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String(36), ForeignKey("machine_components.id", ondelete="SET NULL"), nullable=True, index=True)
    failure_mode_id = Column(String(36), ForeignKey("failure_modes.id", ondelete="SET NULL"), nullable=True, index=True)

    failure_started_at = Column(DateTime, nullable=False, index=True)
    failure_detected_at = Column(DateTime, nullable=True)
    failure_confirmed_at = Column(DateTime, nullable=True)
    restoration_completed_at = Column(DateTime, nullable=True)

    failure_description = Column(Text, nullable=False)
    observed_symptoms = Column(JSON, nullable=True)
    confirmed_root_cause = Column(Text, nullable=True)
    maintenance_action = Column(Text, nullable=True)
    downtime_minutes = Column(Float, nullable=True, default=0.0)
    record_source = Column(String(50), default="MANUAL", nullable=False)  # MANUAL, CMMS, IOT_DERIVED
    verification_status = Column(String(30), default=FailureVerificationStatus.UNVERIFIED, nullable=False, index=True)
    verified_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    machine = relationship("Machine", backref=db.backref("failure_records", cascade="all, delete-orphan", lazy="dynamic"))
    component = relationship("MachineComponent", backref=db.backref("failure_records", lazy="dynamic"))
    failure_mode = relationship("FailureMode", backref=db.backref("records", lazy="dynamic"))

    __table_args__ = (
        Index("ix_fr_org_mach_time", "organization_id", "machine_id", "failure_started_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "component_id": self.component_id,
            "failure_mode_id": self.failure_mode_id,
            "failure_mode_name": self.failure_mode.name if self.failure_mode else None,
            "failure_mode_code": self.failure_mode.code if self.failure_mode else None,
            "failure_started_at": self.failure_started_at.isoformat() if self.failure_started_at else None,
            "failure_detected_at": self.failure_detected_at.isoformat() if self.failure_detected_at else None,
            "failure_confirmed_at": self.failure_confirmed_at.isoformat() if self.failure_confirmed_at else None,
            "restoration_completed_at": self.restoration_completed_at.isoformat() if self.restoration_completed_at else None,
            "failure_description": self.failure_description,
            "observed_symptoms": self.observed_symptoms or [],
            "confirmed_root_cause": self.confirmed_root_cause,
            "maintenance_action": self.maintenance_action,
            "downtime_minutes": self.downtime_minutes,
            "record_source": self.record_source,
            "verification_status": self.verification_status,
            "verified_by": self.verified_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# PREDICTIVE DATASETS (Requirement 7)
# =============================================================================

class PredictiveDataset(db.Model):
    """Reproducible dataset snapshot for training and validating predictive models."""
    __tablename__ = "predictive_datasets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    version_number = Column(Integer, default=1, nullable=False)
    sample_count = Column(Integer, default=0, nullable=False)
    positive_sample_count = Column(Integer, default=0, nullable=False)
    negative_sample_count = Column(Integer, default=0, nullable=False)

    time_window_start = Column(DateTime, nullable=False)
    time_window_end = Column(DateTime, nullable=False)
    feature_schema = Column(JSON, nullable=False)
    dataset_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "name": self.name,
            "version_number": self.version_number,
            "sample_count": self.sample_count,
            "positive_sample_count": self.positive_sample_count,
            "negative_sample_count": self.negative_sample_count,
            "time_window_start": self.time_window_start.isoformat() if self.time_window_start else None,
            "time_window_end": self.time_window_end.isoformat() if self.time_window_end else None,
            "feature_schema": self.feature_schema or {},
            "dataset_metadata": self.dataset_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# PREDICTIVE MODEL REGISTRY & VERSIONS (Requirement 14)
# =============================================================================

class PredictiveModelRegistry(db.Model):
    """Model family container per machine, component, failure mode, and horizon."""
    __tablename__ = "predictive_model_registry"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String(36), ForeignKey("machine_components.id", ondelete="SET NULL"), nullable=True)
    failure_mode_id = Column(String(36), ForeignKey("failure_modes.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    model_type = Column(String(50), default="FAILURE_CLASSIFICATION", nullable=False)  # CLASSIFICATION, RISK_ESTIMATOR, SURVIVAL_RUL
    prediction_horizon_hours = Column(Integer, default=168, nullable=False)  # e.g., 24h, 168h (7d), 720h (30d)
    lifecycle_status = Column(String(30), default=PredictiveModelLifecycle.DRAFT, nullable=False)
    active_version_number = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    machine = relationship("Machine", backref=db.backref("predictive_models", cascade="all, delete-orphan", lazy="dynamic"))
    failure_mode = relationship("FailureMode")
    versions = relationship("PredictiveModelVersion", back_populates="registry", cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        Index("ix_pmr_mach_mode_horizon", "machine_id", "failure_mode_id", "prediction_horizon_hours"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "component_id": self.component_id,
            "failure_mode_id": self.failure_mode_id,
            "failure_mode_name": self.failure_mode.name if self.failure_mode else None,
            "name": self.name,
            "model_type": self.model_type,
            "prediction_horizon_hours": self.prediction_horizon_hours,
            "lifecycle_status": self.lifecycle_status,
            "active_version_number": self.active_version_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PredictiveModelVersion(db.Model):
    """Immutable trained and calibrated model version artifact."""
    __tablename__ = "predictive_model_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    registry_id = Column(String(36), ForeignKey("predictive_model_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)

    algorithm = Column(String(50), nullable=False)  # RANDOM_FOREST, GRADIENT_BOOSTING, LOGISTIC_REGRESSION, WEIBULL_SURVIVAL
    prediction_horizon_hours = Column(Integer, nullable=False, default=168)
    feature_schema = Column(JSON, nullable=False)
    hyperparameters = Column(JSON, nullable=False)

    model_artifact_path = Column(String(255), nullable=True)
    calibrator_artifact_path = Column(String(255), nullable=True)
    training_sample_count = Column(Integer, nullable=False, default=0)
    positive_sample_count = Column(Integer, nullable=False, default=0)

    # Validation & Calibration
    validation_metrics = Column(JSON, nullable=True)  # precision, recall, f1, pr_auc, roc_auc, brier_score
    calibration_metrics = Column(JSON, nullable=True)  # calibration curve, ece, reliability
    is_calibrated = Column(Boolean, default=False, nullable=False)

    status = Column(String(30), default=PredictiveModelLifecycle.TRAINED, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    registry = relationship("PredictiveModelRegistry", back_populates="versions")

    __table_args__ = (
        Index("ix_pmv_reg_version", "registry_id", "version_number", unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "registry_id": self.registry_id,
            "version_number": self.version_number,
            "algorithm": self.algorithm,
            "prediction_horizon_hours": self.prediction_horizon_hours,
            "feature_schema": self.feature_schema,
            "hyperparameters": self.hyperparameters,
            "training_sample_count": self.training_sample_count,
            "positive_sample_count": self.positive_sample_count,
            "validation_metrics": self.validation_metrics or {},
            "calibration_metrics": self.calibration_metrics or {},
            "is_calibrated": self.is_calibrated,
            "status": self.status,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# EQUIPMENT PREDICTIONS & EVIDENCE (Requirements 10 & 16)
# =============================================================================

class EquipmentPrediction(db.Model):
    """Calibrated failure risk and Remaining Useful Life prediction snapshots."""
    __tablename__ = "equipment_predictions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String(36), ForeignKey("machine_components.id", ondelete="SET NULL"), nullable=True)
    failure_mode_id = Column(String(36), ForeignKey("failure_modes.id", ondelete="CASCADE"), nullable=False, index=True)
    model_version_id = Column(String(36), ForeignKey("predictive_model_versions.id", ondelete="SET NULL"), nullable=True)

    prediction_horizon_hours = Column(Integer, nullable=False, default=168)
    status = Column(String(30), default="PREDICTION_READY", nullable=False)  # PREDICTION_READY, PREDICTION_UNAVAILABLE, DATA_QUALITY_BLOCKED

    # Calibrated Probability & Risk
    calibrated_probability = Column(Float, nullable=True)  # 0.0 to 1.0 (calibrated risk)
    uncalibrated_score = Column(Float, nullable=True)
    risk_category = Column(String(20), default=PredictiveRiskCategory.LOW, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL

    # Conditional RUL (Only populated when verified survival model applies)
    rul_hours = Column(Float, nullable=True)
    rul_confidence_lower = Column(Float, nullable=True)
    rul_confidence_upper = Column(Float, nullable=True)
    rul_method = Column(String(50), nullable=True)

    rationale = Column(Text, nullable=False)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    machine = relationship("Machine", backref=db.backref("predictions", cascade="all, delete-orphan", lazy="dynamic"))
    component = relationship("MachineComponent")
    failure_mode = relationship("FailureMode")
    model_version = relationship("PredictiveModelVersion")
    evidence_items = relationship("PredictionEvidence", back_populates="prediction", cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        Index("ix_ep_org_mach_time", "organization_id", "machine_id", "evaluated_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "component_id": self.component_id,
            "failure_mode_id": self.failure_mode_id,
            "failure_mode_name": self.failure_mode.name if self.failure_mode else None,
            "failure_mode_code": self.failure_mode.code if self.failure_mode else None,
            "model_version_id": self.model_version_id,
            "prediction_horizon_hours": self.prediction_horizon_hours,
            "status": self.status,
            "calibrated_probability": round(self.calibrated_probability, 4) if self.calibrated_probability is not None else None,
            "uncalibrated_score": round(self.uncalibrated_score, 4) if self.uncalibrated_score is not None else None,
            "risk_category": self.risk_category,
            "rul_hours": round(self.rul_hours, 1) if self.rul_hours is not None else None,
            "rul_confidence_lower": round(self.rul_confidence_lower, 1) if self.rul_confidence_lower is not None else None,
            "rul_confidence_upper": round(self.rul_confidence_upper, 1) if self.rul_confidence_upper is not None else None,
            "rul_method": self.rul_method,
            "rationale": self.rationale,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PredictionEvidence(db.Model):
    """Detailed feature contribution and signal evidence backing a failure prediction."""
    __tablename__ = "prediction_evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    prediction_id = Column(String(36), ForeignKey("equipment_predictions.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_id = Column(String(36), ForeignKey("machine_signals.id", ondelete="SET NULL"), nullable=True)

    feature_name = Column(String(100), nullable=False)
    feature_value = Column(Float, nullable=False)
    baseline_expected_value = Column(Float, nullable=True)
    contribution_score = Column(Float, nullable=False, default=0.0)  # Relative weight/attribution
    evidence_details = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    prediction = relationship("EquipmentPrediction", back_populates="evidence_items")
    signal = relationship("MachineSignal")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "prediction_id": self.prediction_id,
            "signal_id": self.signal_id,
            "feature_name": self.feature_name,
            "feature_value": round(self.feature_value, 4),
            "baseline_expected_value": round(self.baseline_expected_value, 4) if self.baseline_expected_value is not None else None,
            "contribution_score": round(self.contribution_score, 4),
            "evidence_details": self.evidence_details or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# PREDICTIVE ALERTS (Requirement 17)
# =============================================================================

class PredictiveAlert(db.Model):
    """Actionable predictive alerts distinct from Phase 5 anomaly alarms."""
    __tablename__ = "predictive_alerts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String(36), ForeignKey("machine_components.id", ondelete="SET NULL"), nullable=True)
    failure_mode_id = Column(String(36), ForeignKey("failure_modes.id", ondelete="CASCADE"), nullable=False)
    prediction_id = Column(String(36), ForeignKey("equipment_predictions.id", ondelete="CASCADE"), nullable=False, index=True)

    prediction_horizon_hours = Column(Integer, nullable=False, default=168)
    calibrated_risk = Column(Float, nullable=False)  # 0.0 to 1.0
    risk_category = Column(String(20), default=PredictiveRiskCategory.HIGH, nullable=False, index=True)
    status = Column(String(30), default=PredictiveAlertStatus.OPEN, nullable=False, index=True)

    first_detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    cooldown_until = Column(DateTime, nullable=True)

    engineer_review_notes = Column(Text, nullable=True)
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    machine = relationship("Machine", backref=db.backref("predictive_alerts", cascade="all, delete-orphan", lazy="dynamic"))
    failure_mode = relationship("FailureMode")
    prediction = relationship("EquipmentPrediction")

    __table_args__ = (
        Index("ix_pa_org_status_risk", "organization_id", "status", "risk_category"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "machine_name": self.machine.equipment_name if self.machine else "Unknown",
            "component_id": self.component_id,
            "failure_mode_id": self.failure_mode_id,
            "failure_mode_name": self.failure_mode.name if self.failure_mode else "Unknown",
            "prediction_id": self.prediction_id,
            "prediction_horizon_hours": self.prediction_horizon_hours,
            "calibrated_risk": round(self.calibrated_risk, 4),
            "risk_category": self.risk_category,
            "status": self.status,
            "engineer_review_notes": self.engineer_review_notes,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "first_detected_at": self.first_detected_at.isoformat() if self.first_detected_at else None,
            "last_detected_at": self.last_detected_at.isoformat() if self.last_detected_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

