import logging
from typing import List, Optional, Dict, Any
from app.extensions import db
from app.models.signal_mapping import (
    SignalDefinition,
    MachineSignal,
    SignalValidationResult,
    SignalGroup,
    ValidationStatus,
)

logger = logging.getLogger(__name__)

STANDARD_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "signal_code": "MOTOR_TEMP",
        "name": "Motor Temperature",
        "signal_group": SignalGroup.TEMPERATURE,
        "expected_data_type": "Double",
        "standard_unit": "°C",
        "measurement_dimension": "temperature",
        "description": "Drive motor stator/casing temperature measurement.",
    },
    {
        "signal_code": "BEARING_TEMP",
        "name": "Bearing Temperature",
        "signal_group": SignalGroup.TEMPERATURE,
        "expected_data_type": "Double",
        "standard_unit": "°C",
        "measurement_dimension": "temperature",
        "description": "Shaft/bearing housing temperature sensor.",
    },
    {
        "signal_code": "SEALING_TEMP",
        "name": "Sealing Temperature",
        "signal_group": SignalGroup.TEMPERATURE,
        "expected_data_type": "Double",
        "standard_unit": "°C",
        "measurement_dimension": "temperature",
        "description": "Blister / pouch thermal sealing station temperature.",
    },
    {
        "signal_code": "MOTOR_VIBRATION",
        "name": "Motor Vibration Velocity",
        "signal_group": SignalGroup.VIBRATION,
        "expected_data_type": "Double",
        "standard_unit": "mm/s",
        "measurement_dimension": "velocity",
        "description": "Motor overall RMS vibration velocity in mm/s.",
    },
    {
        "signal_code": "BEARING_VIBRATION",
        "name": "Bearing Vibration Acceleration",
        "signal_group": SignalGroup.VIBRATION,
        "expected_data_type": "Double",
        "standard_unit": "g",
        "measurement_dimension": "acceleration",
        "description": "High-frequency peak bearing vibration acceleration in g.",
    },
    {
        "signal_code": "MOTOR_CURRENT",
        "name": "Motor Current",
        "signal_group": SignalGroup.MOTOR_CURRENT,
        "expected_data_type": "Double",
        "standard_unit": "A",
        "measurement_dimension": "electric_current",
        "description": "Main drive motor operating current in Amperes.",
    },
    {
        "signal_code": "ROTATIONAL_SPEED",
        "name": "Rotational Speed",
        "signal_group": SignalGroup.SPEED,
        "expected_data_type": "Double",
        "standard_unit": "RPM",
        "measurement_dimension": "rotational_speed",
        "description": "Main turret / shaft rotational speed in revolutions per minute.",
    },
    {
        "signal_code": "LINE_SPEED",
        "name": "Packaging Line Speed",
        "signal_group": SignalGroup.SPEED,
        "expected_data_type": "Double",
        "standard_unit": "m/s",
        "measurement_dimension": "velocity",
        "description": "Conveyor or feed linear speed in meters per second.",
    },
    {
        "signal_code": "VACUUM_LEVEL",
        "name": "Vacuum Level",
        "signal_group": SignalGroup.PRESSURE,
        "expected_data_type": "Double",
        "standard_unit": "bar",
        "measurement_dimension": "pressure",
        "description": "Forming or blister vacuum pressure.",
    },
    {
        "signal_code": "LINE_PRESSURE",
        "name": "Hydraulic / Pneumatic Pressure",
        "signal_group": SignalGroup.PRESSURE,
        "expected_data_type": "Double",
        "standard_unit": "bar",
        "measurement_dimension": "pressure",
        "description": "System air / hydraulic line pressure in bar.",
    },
    {
        "signal_code": "FAULT_ALARM",
        "name": "Machine Fault Alarm",
        "signal_group": SignalGroup.ALARMS,
        "expected_data_type": "Boolean",
        "standard_unit": "Boolean",
        "measurement_dimension": "discrete",
        "description": "General machine error or trip status flag.",
    },
    {
        "signal_code": "EMERGENCY_STOP",
        "name": "Emergency Stop Status",
        "signal_group": SignalGroup.ALARMS,
        "expected_data_type": "Boolean",
        "standard_unit": "Boolean",
        "measurement_dimension": "discrete",
        "description": "Safety E-stop circuit activation flag.",
    },
    {
        "signal_code": "CYCLE_COUNTER",
        "name": "Machine Cycle Counter",
        "signal_group": SignalGroup.CYCLES,
        "expected_data_type": "Int32",
        "standard_unit": "Count",
        "measurement_dimension": "count",
        "description": "Cumulative compression, filling, or packaging cycle strokes.",
    },
    {
        "signal_code": "PRODUCTION_COUNT",
        "name": "Production Batch Count",
        "signal_group": SignalGroup.CYCLES,
        "expected_data_type": "Int32",
        "standard_unit": "Count",
        "measurement_dimension": "count",
        "description": "Units or blisters produced in the current active batch.",
    },
]


class SignalDefinitionRepository:
    """Repository for standard and tenant-specific custom signal definitions."""

    @classmethod
    def seed_standard_definitions(cls) -> None:
        """Seed predefined standard signal definitions into the database if not present."""
        for item in STANDARD_DEFINITIONS:
            existing = SignalDefinition.query.filter_by(
                signal_code=item["signal_code"],
                organization_id=None,
            ).first()

            if not existing:
                definition = SignalDefinition(
                    signal_code=item["signal_code"],
                    name=item["name"],
                    signal_group=item["signal_group"],
                    expected_data_type=item["expected_data_type"],
                    standard_unit=item["standard_unit"],
                    measurement_dimension=item["measurement_dimension"],
                    description=item.get("description"),
                    is_custom=False,
                    organization_id=None,
                )
                db.session.add(definition)
        try:
            db.session.commit()
            logger.info("[SignalMapping] Standard signal definitions seeded successfully.")
        except Exception as e:
            logger.error(f"[SignalMapping] Error seeding standard signal definitions: {e}")
            db.session.rollback()

    @classmethod
    def get_definitions(cls, organization_id: str, group: Optional[str] = None) -> List[SignalDefinition]:
        """Fetch all global standard definitions plus custom definitions for the specified organization."""
        cls.seed_standard_definitions()
        query = SignalDefinition.query.filter(
            db.or_(
                SignalDefinition.organization_id.is_(None),
                SignalDefinition.organization_id == organization_id,
            )
        )
        if group and group in SignalGroup.ALL_GROUPS:
            query = query.filter_by(signal_group=group)

        return query.order_by(SignalDefinition.signal_group, SignalDefinition.name).all()

    @classmethod
    def get_by_id(cls, definition_id: str, organization_id: str) -> Optional[SignalDefinition]:
        """Retrieve a definition if it is standard or belongs to the organization."""
        return SignalDefinition.query.filter(
            SignalDefinition.id == definition_id,
            db.or_(
                SignalDefinition.organization_id.is_(None),
                SignalDefinition.organization_id == organization_id,
            ),
        ).first()

    @classmethod
    def get_by_code(cls, signal_code: str, organization_id: str) -> Optional[SignalDefinition]:
        return SignalDefinition.query.filter(
            SignalDefinition.signal_code == signal_code,
            db.or_(
                SignalDefinition.organization_id.is_(None),
                SignalDefinition.organization_id == organization_id,
            ),
        ).first()

    @classmethod
    def create_custom(cls, organization_id: str, data: Dict[str, Any]) -> SignalDefinition:
        """Create a custom signal definition for a specific organization."""
        code = data.get("signal_code", "").strip().upper()
        existing = cls.get_by_code(code, organization_id)
        if existing:
            raise ValueError(f"Signal code '{code}' already exists.")

        group = data.get("signal_group", SignalGroup.OTHER)
        if group not in SignalGroup.ALL_GROUPS:
            group = SignalGroup.OTHER

        definition = SignalDefinition(
            signal_code=code,
            name=data["name"].strip(),
            signal_group=group,
            expected_data_type=data.get("expected_data_type", "Double"),
            standard_unit=data.get("standard_unit"),
            measurement_dimension=data.get("measurement_dimension"),
            description=data.get("description"),
            is_custom=True,
            organization_id=organization_id,
        )
        db.session.add(definition)
        db.session.commit()
        return definition


class MachineSignalRepository:
    """Repository for machine signal mappings."""

    @classmethod
    def get_by_id(cls, signal_id: str, organization_id: str) -> Optional[MachineSignal]:
        return MachineSignal.query.filter_by(id=signal_id, organization_id=organization_id).first()

    @classmethod
    def get_signals_for_machine(
        cls, machine_id: str, organization_id: str, enabled_only: bool = False
    ) -> List[MachineSignal]:
        query = MachineSignal.query.filter_by(machine_id=machine_id, organization_id=organization_id)
        if enabled_only:
            query = query.filter_by(enabled=True)
        return query.order_by(MachineSignal.created_at.asc()).all()

    @classmethod
    def find_duplicate(
        cls, machine_id: str, source_node_id: str, mapping_version: int, exclude_id: Optional[str] = None
    ) -> Optional[MachineSignal]:
        query = MachineSignal.query.filter_by(
            machine_id=machine_id,
            source_node_id=source_node_id,
            mapping_version=mapping_version,
        )
        if exclude_id:
            query = query.filter(MachineSignal.id != exclude_id)
        return query.first()

    @classmethod
    def create_signal(
        cls, organization_id: str, machine_id: str, data: Dict[str, Any], user_id: Optional[str] = None
    ) -> MachineSignal:
        signal = MachineSignal(
            organization_id=organization_id,
            machine_id=machine_id,
            connector_id=data.get("connector_id"),
            component_id=data.get("component_id"),
            signal_definition_id=data["signal_definition_id"],
            custom_name=data.get("custom_name"),
            source_node_id=data["source_node_id"].strip(),
            source_browse_name=data.get("source_browse_name"),
            source_data_type=data.get("source_data_type"),
            source_unit=data.get("source_unit"),
            normalized_unit=data.get("normalized_unit"),
            scaling_factor=float(data.get("scaling_factor", 1.0)),
            offset=float(data.get("offset", 0.0)),
            sampling_interval_ms=int(data.get("sampling_interval_ms", 1000)),
            mapping_version=1,
            validation_status=ValidationStatus.PENDING,
            enabled=data.get("enabled", True),
            created_by=user_id,
        )
        db.session.add(signal)
        db.session.commit()
        return signal

    @classmethod
    def update_signal(
        cls, signal: MachineSignal, data: Dict[str, Any], user_id: Optional[str] = None
    ) -> MachineSignal:
        """Update signal mapping properties. Bumps mapping_version and resets validation_status to PENDING."""
        if "custom_name" in data:
            signal.custom_name = data["custom_name"]
        if "component_id" in data:
            signal.component_id = data["component_id"]
        if "source_node_id" in data:
            signal.source_node_id = data["source_node_id"].strip()
        if "source_browse_name" in data:
            signal.source_browse_name = data["source_browse_name"]
        if "source_data_type" in data:
            signal.source_data_type = data["source_data_type"]
        if "source_unit" in data:
            signal.source_unit = data["source_unit"]
        if "normalized_unit" in data:
            signal.normalized_unit = data["normalized_unit"]
        if "scaling_factor" in data:
            signal.scaling_factor = float(data["scaling_factor"])
        if "offset" in data:
            signal.offset = float(data["offset"])
        if "sampling_interval_ms" in data:
            signal.sampling_interval_ms = int(data["sampling_interval_ms"])
        if "enabled" in data:
            signal.enabled = bool(data["enabled"])

        # Bump version and invalidate previous validation
        signal.mapping_version += 1
        signal.validation_status = ValidationStatus.PENDING

        db.session.commit()
        return signal

    @classmethod
    def delete_signal(cls, signal: MachineSignal) -> None:
        db.session.delete(signal)
        db.session.commit()


class ValidationResultRepository:
    """Repository for signal validation results."""

    @classmethod
    def record_result(
        cls,
        machine_signal_id: str,
        organization_id: str,
        status: str,
        checks: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
        sample_reading: Optional[Dict[str, Any]],
        mapping_version: int,
        user_id: Optional[str] = None,
    ) -> SignalValidationResult:
        result = SignalValidationResult(
            organization_id=organization_id,
            machine_signal_id=machine_signal_id,
            validation_status=status,
            validation_checks=checks,
            error_messages=errors,
            warning_messages=warnings,
            sample_reading=sample_reading,
            mapping_version=mapping_version,
            validated_by=user_id,
        )
        db.session.add(result)
        db.session.commit()
        return result

    @classmethod
    def get_latest_for_signal(
        cls, machine_signal_id: str, organization_id: str
    ) -> Optional[SignalValidationResult]:
        return (
            SignalValidationResult.query.filter_by(
                machine_signal_id=machine_signal_id, organization_id=organization_id
            )
            .order_by(SignalValidationResult.validated_at.desc())
            .first()
        )

    @classmethod
    def get_results_for_machine(
        cls, machine_id: str, organization_id: str
    ) -> List[SignalValidationResult]:
        return (
            SignalValidationResult.query.join(
                MachineSignal, SignalValidationResult.machine_signal_id == MachineSignal.id
            )
            .filter(
                MachineSignal.machine_id == machine_id,
                MachineSignal.organization_id == organization_id,
            )
            .order_by(SignalValidationResult.validated_at.desc())
            .all()
        )

