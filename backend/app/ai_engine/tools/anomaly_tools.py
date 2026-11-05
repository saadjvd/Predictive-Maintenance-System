from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from app.models.condition import BaselineProfile, BaselineVersion, AnomalyEvent
from app.models.signal_mapping import MachineSignal
from app.modules.anomalies.services import AnomalyService
from app.modules.condition_monitoring.services import ConditionMonitoringService
from app.modules.operating_context.services import OperatingContextService


class AnomalyTools:
    """Read-only anomaly and equipment condition tools for diagnostic agents."""

    @classmethod
    def get_condition_summary(cls, organization_id: str, machine_id: str) -> Dict[str, Any]:
        """Retrieves verified condition classification, operating state, and abnormal indicators."""
        return ConditionMonitoringService.get_equipment_condition_summary(
            organization_id=organization_id,
            machine_id=machine_id,
        )

    @classmethod
    def get_active_anomalies(
        cls,
        organization_id: str,
        machine_id: str,
        lookback_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Retrieves discrete anomalies detected over the specified historical window."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        anomalies = (
            AnomalyEvent.query.filter(
                AnomalyEvent.machine_id == machine_id,
                AnomalyEvent.organization_id == organization_id,
                AnomalyEvent.first_detected_at >= cutoff,
            )
            .order_by(AnomalyEvent.latest_detected_at.desc())
            .all()
        )
        return [a.to_dict() for a in anomalies]

    @classmethod
    def get_baseline_deviations(cls, organization_id: str, machine_id: str) -> Dict[str, Any]:
        """Calculates current signal deviations from approved baseline envelopes."""
        profiles = BaselineProfile.query.filter_by(
            machine_id=machine_id,
            organization_id=organization_id,
            lifecycle_status="APPROVED",
        ).all()

        deviations = {}
        for p in profiles:
            sig = p.signal
            sig_name = (
                sig.signal_definition.signal_code
                if sig and sig.signal_definition
                else (sig.custom_name if sig else "UNKNOWN")
            )
            if p.active_version_number:
                bv = BaselineVersion.query.filter_by(
                    profile_id=p.id,
                    version_number=p.active_version_number,
                ).first()
                if bv and bv.mean is not None:
                    deviations[sig_name] = {
                        "baseline_mean": round(bv.mean, 2),
                        "baseline_std": round(bv.std or 1.0, 2),
                        "baseline_min": round(bv.min_value, 2) if bv.min_value is not None else None,
                        "baseline_max": round(bv.max_value, 2) if bv.max_value is not None else None,
                    }
        return deviations

