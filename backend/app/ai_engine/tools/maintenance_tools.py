from typing import Dict, Any, List
from app.models.prediction import FailureRecord, FailureVerificationStatus


class MaintenanceTools:
    """Read-only maintenance and failure history tools for diagnostic agents."""

    @classmethod
    def get_historical_failures(
        cls,
        organization_id: str,
        machine_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieves verified and suspected historical failure logs for equipment."""
        records = (
            FailureRecord.query.filter_by(
                organization_id=organization_id,
                machine_id=machine_id,
            )
            .order_by(FailureRecord.failure_started_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "record_id": r.id,
                "failure_mode": r.failure_mode.name if r.failure_mode else "Unspecified",
                "failure_started_at": r.failure_started_at.isoformat() if r.failure_started_at else None,
                "description": r.failure_description,
                "symptoms": r.observed_symptoms or [],
                "confirmed_root_cause": r.confirmed_root_cause,
                "maintenance_action": r.maintenance_action,
                "downtime_minutes": r.downtime_minutes,
                "verification_status": r.verification_status,
            }
            for r in records
        ]

    @classmethod
    def get_confirmed_root_causes(
        cls,
        organization_id: str,
        machine_id: str,
    ) -> List[Dict[str, str]]:
        """Returns verified failure root causes and corrective maintenance actions."""
        confirmed = (
            FailureRecord.query.filter_by(
                organization_id=organization_id,
                machine_id=machine_id,
                verification_status=FailureVerificationStatus.CONFIRMED,
            )
            .order_by(FailureRecord.failure_started_at.desc())
            .all()
        )
        return [
            {
                "root_cause": c.confirmed_root_cause or "No detailed root cause recorded",
                "action_taken": c.maintenance_action or "Component replacement / repair",
                "failure_mode": c.failure_mode.name if c.failure_mode else "General Degradation",
            }
            for c in confirmed
            if c.confirmed_root_cause
        ]

