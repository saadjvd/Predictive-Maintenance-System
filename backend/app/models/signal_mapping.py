import uuid
from datetime import datetime, timezone
from app.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class SignalGroup:
    """Standardized industrial signal groups."""
    TEMPERATURE = "Temperature"
    VIBRATION = "Vibration"
    MOTOR_CURRENT = "Motor Current"
    SPEED = "Speed"
    PRESSURE = "Pressure"
    ALARMS = "Alarms"
    CYCLES = "Cycles"
    OTHER = "Other"

    ALL_GROUPS = [
        TEMPERATURE,
        VIBRATION,
        MOTOR_CURRENT,
        SPEED,
        PRESSURE,
        ALARMS,
        CYCLES,
        OTHER,
    ]


class ValidationStatus:
    PENDING = "PENDING"
    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"

    ALL_STATUSES = [PENDING, VALID, WARNING, INVALID]


class SignalDefinition(db.Model):
    """Catalog of standard and custom pharmaceutical equipment signal types."""
    __tablename__ = "signal_definitions"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    signal_code = db.Column(db.String(100), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    signal_group = db.Column(db.String(50), nullable=False, index=True)
    expected_data_type = db.Column(db.String(50), nullable=False)  # Double, Float, Int32, Boolean, String, etc.
    standard_unit = db.Column(db.String(50), nullable=True)  # °C, mm/s, g, A, RPM, bar, kPa, Count, etc.
    measurement_dimension = db.Column(db.String(50), nullable=True)  # temperature, velocity, acceleration, current, etc.
    description = db.Column(db.Text, nullable=True)
    is_custom = db.Column(db.Boolean, default=False, nullable=False)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    organization = db.relationship("Organization")
    machine_signals = db.relationship("MachineSignal", back_populates="signal_definition", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "signal_code": self.signal_code,
            "name": self.name,
            "signal_group": self.signal_group,
            "expected_data_type": self.expected_data_type,
            "standard_unit": self.standard_unit,
            "measurement_dimension": self.measurement_dimension,
            "description": self.description,
            "is_custom": self.is_custom,
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MachineSignal(db.Model):
    """Mapping between an OPC UA discovered tag and a standardized signal definition."""
    __tablename__ = "machine_signals"
    __table_args__ = (
        db.UniqueConstraint("machine_id", "source_node_id", "mapping_version", name="uq_machine_node_version"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    machine_id = db.Column(
        db.String(36),
        db.ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    connector_id = db.Column(db.String(100), nullable=True)
    component_id = db.Column(
        db.String(36),
        db.ForeignKey("machine_components.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    signal_definition_id = db.Column(
        db.String(36),
        db.ForeignKey("signal_definitions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    custom_name = db.Column(db.String(255), nullable=True)  # Optional override/alias e.g. "Main Motor Temperature"
    source_node_id = db.Column(db.String(255), nullable=False)
    source_browse_name = db.Column(db.String(255), nullable=True)
    source_data_type = db.Column(db.String(50), nullable=True)
    source_unit = db.Column(db.String(50), nullable=True)
    normalized_unit = db.Column(db.String(50), nullable=True)
    scaling_factor = db.Column(db.Float, default=1.0, nullable=False)
    offset = db.Column(db.Float, default=0.0, nullable=False)
    sampling_interval_ms = db.Column(db.Integer, default=1000, nullable=False)
    mapping_version = db.Column(db.Integer, default=1, nullable=False)
    validation_status = db.Column(db.String(50), default=ValidationStatus.PENDING, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    organization = db.relationship("Organization")
    machine = db.relationship("Machine", backref=db.backref("signals", lazy=True, cascade="all, delete-orphan"))
    component = db.relationship("MachineComponent")
    signal_definition = db.relationship("SignalDefinition", back_populates="machine_signals")
    validation_results = db.relationship(
        "SignalValidationResult",
        back_populates="machine_signal",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        latest_val = self.validation_results[-1] if self.validation_results else None
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_id": self.machine_id,
            "connector_id": self.connector_id,
            "component_id": self.component_id,
            "component_name": self.component.component_name if self.component else None,
            "signal_definition_id": self.signal_definition_id,
            "signal_code": self.signal_definition.signal_code if self.signal_definition else None,
            "signal_name": self.custom_name or (self.signal_definition.name if self.signal_definition else None),
            "signal_group": self.signal_definition.signal_group if self.signal_definition else None,
            "source_node_id": self.source_node_id,
            "source_browse_name": self.source_browse_name,
            "source_data_type": self.source_data_type,
            "source_unit": self.source_unit,
            "normalized_unit": self.normalized_unit,
            "scaling_factor": self.scaling_factor,
            "offset": self.offset,
            "sampling_interval_ms": self.sampling_interval_ms,
            "mapping_version": self.mapping_version,
            "validation_status": self.validation_status,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "latest_validation": latest_val.to_dict() if latest_val else None,
        }


class SignalValidationResult(db.Model):
    """Detailed validation audit log for a machine signal configuration."""
    __tablename__ = "signal_validation_results"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    machine_signal_id = db.Column(
        db.String(36),
        db.ForeignKey("machine_signals.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    validation_status = db.Column(db.String(50), nullable=False)  # VALID, WARNING, INVALID
    validation_checks = db.Column(db.JSON, nullable=False, default=dict)  # Individual check status dictionary
    error_messages = db.Column(db.JSON, nullable=False, default=list)
    warning_messages = db.Column(db.JSON, nullable=False, default=list)
    sample_reading = db.Column(db.JSON, nullable=True)  # {raw_value, normalized_value, timestamp, quality}
    validated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    validated_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    mapping_version = db.Column(db.Integer, nullable=False, default=1)
    connector_configuration_version = db.Column(db.String(50), nullable=True, default="1.0")

    # Relationships
    machine_signal = db.relationship("MachineSignal", back_populates="validation_results")

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "machine_signal_id": self.machine_signal_id,
            "validation_status": self.validation_status,
            "validation_checks": self.validation_checks,
            "error_messages": self.error_messages or [],
            "warning_messages": self.warning_messages or [],
            "sample_reading": self.sample_reading,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "mapping_version": self.mapping_version,
            "connector_configuration_version": self.connector_configuration_version,
        }

