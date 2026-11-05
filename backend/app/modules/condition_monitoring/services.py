from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from app.extensions import db
from app.models.condition import (
    EquipmentConditionObservation,
    ConditionClassification,
    AnomalyEvent,
    EquipmentAlert,
    AlertStatus,
    BaselineProfile,
    BaselineLifecycle,
)
from app.models.equipment import Machine
from app.models.signal_mapping import MachineSignal
from app.modules.anomalies.services import AnomalyService
from app.modules.data_quality.services import DataQualityService
from app.modules.operating_context.services import OperatingContextService


class ConditionMonitoringService:
    """Manages condition evaluation snapshots, health indicators, and condition trends."""

    @classmethod
    def get_equipment_condition_summary(
        cls,
        organization_id: str,
        machine_id: str,
    ) -> Dict[str, Any]:
        """Returns the latest condition evaluation summary and operational indicators."""
        machine = Machine.query.filter_by(id=machine_id, organization_id=organization_id).first()
        if not machine:
            raise ValueError(f"Machine {machine_id} not found.")

        # Latest condition observation
        latest_obs = EquipmentConditionObservation.query.filter_by(
            organization_id=organization_id,
            machine_id=machine_id,
        ).order_by(EquipmentConditionObservation.observed_at.desc()).first()

        # If no observation exists yet, trigger an evaluation
        if not latest_obs:
            eval_res = AnomalyService.evaluate_machine_condition(organization_id, machine_id)
            latest_obs = EquipmentConditionObservation.query.filter_by(
                organization_id=organization_id,
                machine_id=machine_id,
            ).order_by(EquipmentConditionObservation.observed_at.desc()).first()

        # Count active open alerts
        open_alerts_count = EquipmentAlert.query.filter(
            EquipmentAlert.organization_id == organization_id,
            EquipmentAlert.machine_id == machine_id,
            EquipmentAlert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED, AlertStatus.UNDER_INVESTIGATION]),
        ).count()

        # Count active anomalies
        active_anomalies = AnomalyEvent.query.filter_by(
            organization_id=organization_id,
            machine_id=machine_id,
            status="ACTIVE",
        ).order_by(AnomalyEvent.latest_detected_at.desc()).limit(10).all()

        # Operating state
        op_context = OperatingContextService.evaluate_current_state(machine_id, organization_id)

        # Baseline coverage
        signals_count = MachineSignal.query.filter_by(machine_id=machine_id, organization_id=organization_id).count()
        active_baselines_count = BaselineProfile.query.filter_by(
            machine_id=machine_id,
            organization_id=organization_id,
            lifecycle_status=BaselineLifecycle.ACTIVE,
        ).count()

        # Latest data quality
        dq_eval = DataQualityService.evaluate_machine_quality(machine_id, organization_id)

        return {
            "machine_id": machine_id,
            "machine_name": machine.equipment_name,
            "condition_state": latest_obs.condition_state if latest_obs else ConditionClassification.INSUFFICIENT_DATA,
            "summary_reason": latest_obs.summary_reason if latest_obs else "No condition observation recorded yet.",
            "observed_at": latest_obs.observed_at.isoformat() if latest_obs else None,
            "operating_state": op_context.get("current_state", "UNKNOWN"),
            "operating_confidence": op_context.get("confidence", 0.0),
            "data_quality_state": dq_eval.get("overall_state", "GOOD"),
            "data_quality_issues": dq_eval.get("issues", []),
            "open_alerts_count": open_alerts_count,
            "active_anomaly_count": len(active_anomalies),
            "active_anomalies": [a.to_dict() for a in active_anomalies],
            "baseline_coverage": {
                "total_signals": signals_count,
                "signals_with_active_baseline": active_baselines_count,
            },
        }

    @classmethod
    def get_condition_history(
        cls,
        organization_id: str,
        machine_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Returns historical sequence of condition observations."""
        observations = EquipmentConditionObservation.query.filter_by(
            organization_id=organization_id,
            machine_id=machine_id,
        ).order_by(EquipmentConditionObservation.observed_at.desc()).limit(limit).all()
        return [obs.to_dict() for obs in observations]
