from typing import List, Dict, Any, Optional
from app.extensions import db
from app.models.prediction import FailureMode


STANDARD_FAILURE_MODES: List[Dict[str, Any]] = [
    {
        "code": "FM_BEARING_DEGRADATION",
        "name": "Drive Motor Bearing Degradation",
        "component_type": "Bearing",
        "description": "Progressive fatigue, spalling, or lubrication loss in rotary bearings leading to elevated high-frequency vibration and housing heating.",
        "severity_impact": "CRITICAL",
        "evidence_requirements": {
            "primary_signals": ["MOTOR_VIBRATION", "BEARING_VIBRATION"],
            "secondary_signals": ["BEARING_TEMP", "MOTOR_TEMP"],
            "diagnostic_pattern": "Rising vibration RMS accompanied by localized temperature rise",
        },
        "relevant_signals": ["MOTOR_VIBRATION", "BEARING_VIBRATION", "BEARING_TEMP", "MOTOR_TEMP"],
        "applicable_model_families": ["CLASSIFICATION", "RISK_ESTIMATOR", "SURVIVAL_RUL"],
        "is_standard": True,
    },
    {
        "code": "FM_MOTOR_OVERHEATING",
        "name": "Main Motor Thermal Overload",
        "component_type": "Motor",
        "description": "Excessive stator winding or casing temperature caused by sustained electrical overload, cooling airflow blockage, or mechanical binding.",
        "severity_impact": "HIGH",
        "evidence_requirements": {
            "primary_signals": ["MOTOR_TEMP"],
            "secondary_signals": ["MOTOR_CURRENT", "ROTATIONAL_SPEED"],
            "diagnostic_pattern": "Thermal climb beyond 85°C at nominal or reduced operational speed",
        },
        "relevant_signals": ["MOTOR_TEMP", "MOTOR_CURRENT", "ROTATIONAL_SPEED", "LINE_SPEED"],
        "applicable_model_families": ["CLASSIFICATION", "RISK_ESTIMATOR"],
        "is_standard": True,
    },
    {
        "code": "FM_ELECTRICAL_FAULT",
        "name": "Drive Motor Electrical Imbalance",
        "component_type": "Motor",
        "description": "Phase unbalance, winding insulation breakdown, or inverter drive irregularity resulting in erratic current draw.",
        "severity_impact": "HIGH",
        "evidence_requirements": {
            "primary_signals": ["MOTOR_CURRENT"],
            "secondary_signals": ["ROTATIONAL_SPEED", "MOTOR_TEMP"],
            "diagnostic_pattern": "Abnormal current fluctuations not correlated with mechanical speed changes",
        },
        "relevant_signals": ["MOTOR_CURRENT", "ROTATIONAL_SPEED"],
        "applicable_model_families": ["CLASSIFICATION", "RISK_ESTIMATOR"],
        "is_standard": True,
    },
    {
        "code": "FM_MECHANICAL_MISALIGNMENT",
        "name": "Shaft / Turret Mechanical Misalignment",
        "component_type": "Mechanical Assembly",
        "description": "Coupling angular or parallel offset generating characteristic 1X/2X rotational frequency harmonics and vibration.",
        "severity_impact": "MEDIUM",
        "evidence_requirements": {
            "primary_signals": ["MOTOR_VIBRATION"],
            "secondary_signals": ["ROTATIONAL_SPEED"],
            "diagnostic_pattern": "Elevated baseline vibration with consistent speed dependence",
        },
        "relevant_signals": ["MOTOR_VIBRATION", "ROTATIONAL_SPEED"],
        "applicable_model_families": ["CLASSIFICATION", "RISK_ESTIMATOR"],
        "is_standard": True,
    },
    {
        "code": "FM_PNEUMATIC_PRESSURE_LOSS",
        "name": "Pneumatic / Vacuum Supply Failure",
        "component_type": "Pneumatics",
        "description": "Seal wear, valve malfunction, or supply leakage preventing rapid blister cavity formation or vacuum pick-and-place.",
        "severity_impact": "CRITICAL",
        "evidence_requirements": {
            "primary_signals": ["VACUUM_LEVEL"],
            "secondary_signals": ["LINE_SPEED"],
            "diagnostic_pattern": "Sub-threshold vacuum levels and extended pressure recovery time",
        },
        "relevant_signals": ["VACUUM_LEVEL", "LINE_SPEED"],
        "applicable_model_families": ["CLASSIFICATION", "RISK_ESTIMATOR"],
        "is_standard": True,
    },
    {
        "code": "FM_GEARBOX_MALFUNCTION",
        "name": "Speed Reducer Gearbox Degradation",
        "component_type": "Gearbox",
        "description": "Gear tooth pitting, backlash growth, or oil degradation causing speed hunting and low-frequency cyclic shock vibration.",
        "severity_impact": "HIGH",
        "evidence_requirements": {
            "primary_signals": ["MOTOR_VIBRATION", "ROTATIONAL_SPEED"],
            "secondary_signals": ["MOTOR_CURRENT"],
            "diagnostic_pattern": "Periodic vibration modulation and speed instability",
        },
        "relevant_signals": ["MOTOR_VIBRATION", "ROTATIONAL_SPEED", "MOTOR_CURRENT"],
        "applicable_model_families": ["CLASSIFICATION", "RISK_ESTIMATOR", "SURVIVAL_RUL"],
        "is_standard": True,
    },
]


class FailureModeCatalog:
    """Manages seeding and querying standard failure mode definitions."""

    @classmethod
    def seed_standard_modes(cls) -> int:
        """Seeds standard failure modes into database if not present."""
        created = 0
        for item in STANDARD_FAILURE_MODES:
            existing = FailureMode.query.filter_by(code=item["code"]).first()
            if not existing:
                fm = FailureMode(
                    code=item["code"],
                    name=item["name"],
                    component_type=item.get("component_type"),
                    description=item.get("description"),
                    severity_impact=item.get("severity_impact", "HIGH"),
                    evidence_requirements=item.get("evidence_requirements"),
                    relevant_signals=item.get("relevant_signals"),
                    applicable_model_families=item.get("applicable_model_families"),
                    is_standard=True,
                )
                db.session.add(fm)
                created += 1
        if created > 0:
            db.session.commit()
        return created

    @classmethod
    def get_modes_for_machine(cls, organization_id: Optional[str] = None) -> List[FailureMode]:
        """Returns standard failure modes plus organization-specific modes."""
        query = FailureMode.query.filter(
            (FailureMode.is_standard == True) | (FailureMode.organization_id == organization_id)
        )
        return query.order_by(FailureMode.name.asc()).all()

