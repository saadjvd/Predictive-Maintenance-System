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


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class QualityState:
    GOOD = "GOOD"
    SUSPECT = "SUSPECT"
    BAD = "BAD"
    MISSING = "MISSING"
    STALE = "STALE"


class OperatingState:
    IDLE = "IDLE"
    STARTUP = "STARTUP"
    RUNNING = "RUNNING"
    HIGH_LOAD = "HIGH_LOAD"
    SHUTDOWN = "SHUTDOWN"
    CLEANING = "CLEANING"
    UNKNOWN = "UNKNOWN"

    ALL_STATES = [IDLE, STARTUP, RUNNING, HIGH_LOAD, SHUTDOWN, CLEANING, UNKNOWN]


class BaselineLifecycle:
    COLLECTING = "COLLECTING"
    CANDIDATE = "CANDIDATE"
    VALIDATING = "VALIDATING"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class ModelLifecycle:
    TRAINING = "TRAINING"
    TRAINED = "TRAINED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


class AnomalySeverity:
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ConditionClassification:
    NORMAL = "NORMAL"
    ATTENTION = "ATTENTION"
    CRITICAL = "CRITICAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MONITORING_UNAVAILABLE = "MONITORING_UNAVAILABLE"


class AlertStatus:
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


# =============================================================================
# DATA QUALITY EVENTS (Requirement 5)
# =============================================================================

class DataQualityEvent(db.Model):
    """Tracks discrete data quality issues (stale, spikes, missing, invalid type, constant signal)."""
    __tablename__ = "data_quality_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_id = Column(String(36), ForeignKey("machine_signals.id", ondelete="CASCADE"), nullable=True, index=True)
    reading_id = Column(String(36), nullable=True)

    quality_state = Column(String(20), nullable=False, default=QualityState.SUSPECT)
    issue_type = Column(String(50), nullable=False)
    details = Column(JSON, nullable=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    machine = relationship("Machine", backref=db.backref("data_quality_events", cascade="all, delete-orphan", lazy="dynamic"))
    signal = relationship("MachineSignal", backref=db.backref("quality_events", cascade="all, delete-orphan", lazy="dynamic"))

    __table_args__ = (
        Index("ix_dqe_org_mach_time", "organization_id", "machine_id", "detected_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "signal_id": self.signal_id,
            "reading_id": self.reading_id,
            "quality_state": self.quality_state,
            "issue_type": self.issue_type,
            "details": self.details or {},
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }


# =============================================================================
# MACHINE OPERATING STATE CONTEXT (Requirement 6)
# =============================================================================

class MachineOperatingStateRecord(db.Model):
    """Tracks machine operational regimes (IDLE, STARTUP, RUNNING, HIGH_LOAD, etc.)."""
    __tablename__ = "machine_operating_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)

    operating_state = Column(String(20), nullable=False, default=OperatingState.UNKNOWN)
    confidence = Column(Float, nullable=False, default=1.0)
    determination_method = Column(String(50), nullable=False, default="RULE_INFERRED")
    supporting_signals = Column(JSON, nullable=True)
    context_metadata = Column(JSON, nullable=True)

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at = Column(DateTime, nullable=True)
    is_current = Column(Boolean, default=True, nullable=False, index=True)

    machine = relationship("Machine", backref=db.backref("operating_states", cascade="all, delete-orphan", lazy="dynamic"))

    __table_args__ = (
        Index("ix_mos_machine_current", "machine_id", "is_current"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "operating_state": self.operating_state,
            "confidence": self.confidence,
            "determination_method": self.determination_method,
            "supporting_signals": self.supporting_signals or {},
            "context_metadata": self.context_metadata or {},
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "is_current": self.is_current,
        }


# =============================================================================
# EQUIPMENT BASELINE PROFILES & VERSIONS (Requirement 7)
# =============================================================================

class BaselineProfile(db.Model):
    """Profiles defining normal operating envelopes per machine, component, signal, and state."""
    __tablename__ = "baseline_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String(36), ForeignKey("machine_components.id", ondelete="SET NULL"), nullable=True)
    signal_id = Column(String(36), ForeignKey("machine_signals.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(100), nullable=False)
    operating_state = Column(String(20), nullable=False, default=OperatingState.RUNNING)
    lifecycle_status = Column(String(20), nullable=False, default=BaselineLifecycle.COLLECTING)
    active_version_number = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    machine = relationship("Machine", backref=db.backref("baseline_profiles", cascade="all, delete-orphan", lazy="dynamic"))
    signal = relationship("MachineSignal", backref=db.backref("baseline_profiles", cascade="all, delete-orphan", lazy="dynamic"))
    component = relationship("MachineComponent", backref=db.backref("baseline_profiles", lazy="dynamic"))
    versions = relationship("BaselineVersion", back_populates="profile", cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        Index("ix_bp_machine_signal_state", "machine_id", "signal_id", "operating_state"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "component_id": self.component_id,
            "signal_id": self.signal_id,
            "name": self.name,
            "operating_state": self.operating_state,
            "lifecycle_status": self.lifecycle_status,
            "active_version_number": self.active_version_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BaselineVersion(db.Model):
    """Immutable versioned baseline statistical envelope."""
    __tablename__ = "baseline_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(36), ForeignKey("baseline_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)

    # Statistical Envelope
    sample_count = Column(Integer, nullable=False, default=0)
    training_start_time = Column(DateTime, nullable=True)
    training_end_time = Column(DateTime, nullable=True)

    mean = Column(Float, nullable=True)
    median = Column(Float, nullable=True)
    std = Column(Float, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    p5 = Column(Float, nullable=True)
    p25 = Column(Float, nullable=True)
    p75 = Column(Float, nullable=True)
    p95 = Column(Float, nullable=True)
    iqr = Column(Float, nullable=True)
    mad = Column(Float, nullable=True)
    variability = Column(Float, nullable=True)

    # Lifecycle & Governance
    validation_status = Column(String(20), nullable=False, default="VALID")
    validation_notes = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    profile = relationship("BaselineProfile", back_populates="versions")

    __table_args__ = (
        Index("ix_bv_profile_version", "profile_id", "version_number", unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "version_number": self.version_number,
            "sample_count": self.sample_count,
            "training_start_time": self.training_start_time.isoformat() if self.training_start_time else None,
            "training_end_time": self.training_end_time.isoformat() if self.training_end_time else None,
            "statistics": {
                "mean": self.mean,
                "median": self.median,
                "std": self.std,
                "min": self.min_value,
                "max": self.max_value,
                "p5": self.p5,
                "p25": self.p25,
                "p75": self.p75,
                "p95": self.p95,
                "iqr": self.iqr,
                "mad": self.mad,
                "variability": self.variability,
            },
            "validation_status": self.validation_status,
            "validation_notes": self.validation_notes,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# ML MODEL REGISTRY & VERSIONS (Requirement 9)
# =============================================================================

class MLModelRegistry(db.Model):
    """Machine-specific ML model container (Isolation Forest)."""
    __tablename__ = "ml_model_registry"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)

    model_type = Column(String(50), nullable=False, default="ISOLATION_FOREST")
    name = Column(String(100), nullable=False)
    lifecycle_status = Column(String(20), nullable=False, default=ModelLifecycle.TRAINING)
    active_version_number = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    machine = relationship("Machine", backref=db.backref("ml_models", cascade="all, delete-orphan", lazy="dynamic"))
    versions = relationship("MLModelVersion", back_populates="registry", cascade="all, delete-orphan", lazy="dynamic")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "model_type": self.model_type,
            "name": self.name,
            "lifecycle_status": self.lifecycle_status,
            "active_version_number": self.active_version_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MLModelVersion(db.Model):
    """Versioned model artifact, hyperparameters, and validation metrics."""
    __tablename__ = "ml_model_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    registry_id = Column(String(36), ForeignKey("ml_model_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)

    feature_schema = Column(JSON, nullable=False)
    hyperparameters = Column(JSON, nullable=False)
    model_artifact_path = Column(String(255), nullable=True)
    training_sample_count = Column(Integer, nullable=False, default=0)
    training_dataset_ref = Column(String(150), nullable=True)
    validation_metrics = Column(JSON, nullable=True)

    status = Column(String(20), nullable=False, default=ModelLifecycle.TRAINED)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    registry = relationship("MLModelRegistry", back_populates="versions")

    __table_args__ = (
        Index("ix_mmv_reg_version", "registry_id", "version_number", unique=True),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "registry_id": self.registry_id,
            "version_number": self.version_number,
            "feature_schema": self.feature_schema,
            "hyperparameters": self.hyperparameters,
            "training_sample_count": self.training_sample_count,
            "training_dataset_ref": self.training_dataset_ref,
            "validation_metrics": self.validation_metrics or {},
            "status": self.status,
            "created_by": self.created_by,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# ANOMALY EVENTS & EXPLAINABLE EVIDENCE (Requirement 10)
# =============================================================================

class AnomalyEvent(db.Model):
    """Explainable anomaly detection events combining statistical and ML evidence."""
    __tablename__ = "anomaly_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String(36), ForeignKey("machine_components.id", ondelete="SET NULL"), nullable=True)

    detection_method = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, default=AnomalySeverity.INFO)
    operating_state = Column(String(20), nullable=False, default=OperatingState.RUNNING)
    status = Column(String(20), nullable=False, default="ACTIVE")

    first_detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    latest_detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    occurrence_count = Column(Integer, nullable=False, default=1)
    anomaly_score = Column(Float, nullable=False, default=0.0)

    affected_signals = Column(JSON, nullable=False)
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    machine = relationship("Machine", backref=db.backref("anomalies", cascade="all, delete-orphan", lazy="dynamic"))
    component = relationship("MachineComponent", backref=db.backref("anomalies", lazy="dynamic"))
    evidence_items = relationship("AnomalyEvidence", back_populates="anomaly", cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        Index("ix_ae_org_mach_time", "organization_id", "machine_id", "latest_detected_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "component_id": self.component_id,
            "detection_method": self.detection_method,
            "severity": self.severity,
            "operating_state": self.operating_state,
            "status": self.status,
            "first_detected_at": self.first_detected_at.isoformat() if self.first_detected_at else None,
            "latest_detected_at": self.latest_detected_at.isoformat() if self.latest_detected_at else None,
            "occurrence_count": self.occurrence_count,
            "anomaly_score": round(self.anomaly_score, 4),
            "affected_signals": self.affected_signals or [],
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AnomalyEvidence(db.Model):
    """Detailed signal-level evidence item linking anomaly to source measurements."""
    __tablename__ = "anomaly_evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    anomaly_id = Column(String(36), ForeignKey("anomaly_events.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_id = Column(String(36), ForeignKey("machine_signals.id", ondelete="CASCADE"), nullable=False)

    source_timestamp = Column(DateTime, nullable=False)
    observed_value = Column(Float, nullable=False)
    baseline_expected_value = Column(Float, nullable=True)
    deviation_magnitude = Column(Float, nullable=True)
    evidence_payload = Column(JSON, nullable=True)

    anomaly = relationship("AnomalyEvent", back_populates="evidence_items")
    signal = relationship("MachineSignal")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "anomaly_id": self.anomaly_id,
            "signal_id": self.signal_id,
            "source_timestamp": self.source_timestamp.isoformat() if self.source_timestamp else None,
            "observed_value": self.observed_value,
            "baseline_expected_value": self.baseline_expected_value,
            "deviation_magnitude": self.deviation_magnitude,
            "evidence_payload": self.evidence_payload or {},
        }


# =============================================================================
# EQUIPMENT CONDITION OBSERVATIONS (Requirement 11)
# =============================================================================

class EquipmentConditionObservation(db.Model):
    """Derived equipment condition classification snapshot."""
    __tablename__ = "condition_observations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)

    condition_state = Column(String(30), nullable=False, default=ConditionClassification.NORMAL)
    active_anomaly_count = Column(Integer, nullable=False, default=0)
    data_quality_issue_count = Column(Integer, nullable=False, default=0)
    summary_reason = Column(Text, nullable=False)
    observed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    machine = relationship("Machine", backref=db.backref("condition_observations", cascade="all, delete-orphan", lazy="dynamic"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "condition_state": self.condition_state,
            "active_anomaly_count": self.active_anomaly_count,
            "data_quality_issue_count": self.data_quality_issue_count,
            "summary_reason": self.summary_reason,
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
        }


# =============================================================================
# ALERTS & ALERT AUDIT HISTORY (Requirement 12)
# =============================================================================

class EquipmentAlert(db.Model):
    """Operational alerts generated from anomalies with acknowledgment workflow."""
    __tablename__ = "equipment_alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    machine_id = Column(String(36), ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    component_id = Column(String(36), ForeignKey("machine_components.id", ondelete="SET NULL"), nullable=True)
    anomaly_id = Column(String(36), ForeignKey("anomaly_events.id", ondelete="CASCADE"), nullable=False, index=True)

    severity = Column(String(20), nullable=False, default=AnomalySeverity.WARNING)
    status = Column(String(30), nullable=False, default=AlertStatus.OPEN, index=True)

    first_detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    cooldown_until = Column(DateTime, nullable=True)

    assigned_to = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledged_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    machine = relationship("Machine", backref=db.backref("alerts", cascade="all, delete-orphan", lazy="dynamic"))
    anomaly = relationship("AnomalyEvent", backref=db.backref("alerts", lazy="dynamic"))
    history = relationship("AlertHistory", back_populates="alert", cascade="all, delete-orphan", lazy="dynamic")

    __table_args__ = (
        Index("ix_ea_org_status_time", "organization_id", "status", "last_detected_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "component_id": self.component_id,
            "anomaly_id": self.anomaly_id,
            "severity": self.severity,
            "status": self.status,
            "first_detected_at": self.first_detected_at.isoformat() if self.first_detected_at else None,
            "last_detected_at": self.last_detected_at.isoformat() if self.last_detected_at else None,
            "assigned_to": self.assigned_to,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AlertHistory(db.Model):
    """Audit trail of status transitions, notes, and actions on alerts."""
    __tablename__ = "alert_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_id = Column(String(36), ForeignKey("equipment_alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    changed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    alert = relationship("EquipmentAlert", back_populates="history")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "changed_by": self.changed_by,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

